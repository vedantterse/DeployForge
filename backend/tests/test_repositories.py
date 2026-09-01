"""
Tests for listing repositories and downloading one.

GitHub is mocked throughout — the listing calls return canned JSON, and the
download tests build real .tar.gz archives (including malicious ones) and serve
them through a mock transport, so the extraction guards are genuinely exercised.
"""

from __future__ import annotations

import io
import json
import tarfile
import time
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.github import client as github_client
from app.github import download as download_mod
from app.github.download import RepositoryDownloadError, download_repository
from app.models.repository import Repository

TOKEN = "gho_averysecrettoken"

REPO_JSON = {
    "id": 1296269,
    "name": "hello-world",
    "full_name": "octocat/hello-world",
    "description": "My first repository",
    "language": "Python",
    "default_branch": "main",
    "clone_url": "https://github.com/octocat/hello-world.git",
    "html_url": "https://github.com/octocat/hello-world",
    "private": False,
    "pushed_at": "2026-08-01T10:00:00Z",
}


def _patch_httpx(monkeypatch, handler) -> None:
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _make_tarball(files: dict[str, str], wrapper: str = "octocat-hello-world-abc123") -> bytes:
    """Build a GitHub-style tarball: everything inside one top-level directory."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(f"{wrapper}/{name}")
            info.size = len(data)
            info.mtime = int(time.time())
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


# --- Listing ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_repositories_normalizes_the_fields(monkeypatch):
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, json=[REPO_JSON]))
    repos = await github_client.list_repositories(TOKEN)
    assert len(repos) == 1
    assert repos[0]["github_repo_id"] == 1296269
    assert repos[0]["full_name"] == "octocat/hello-world"
    assert repos[0]["language"] == "Python"
    assert repos[0]["default_branch"] == "main"


@pytest.mark.asyncio
async def test_list_repositories_sends_the_token(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[])

    _patch_httpx(monkeypatch, handler)
    await github_client.list_repositories(TOKEN)
    assert seen["auth"] == f"Bearer {TOKEN}"


@pytest.mark.asyncio
async def test_list_repositories_follows_pagination(monkeypatch):
    """A full page means there may be more; a short page ends the walk."""
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        pages.append(page)
        if page == 1:
            return httpx.Response(200, json=[REPO_JSON] * 100)
        return httpx.Response(200, json=[REPO_JSON])

    _patch_httpx(monkeypatch, handler)
    repos = await github_client.list_repositories(TOKEN)
    assert pages == [1, 2]
    assert len(repos) == 101


@pytest.mark.asyncio
async def test_expired_token_gives_a_reconnect_message(monkeypatch):
    _patch_httpx(monkeypatch, lambda request: httpx.Response(401, json={}))
    with pytest.raises(github_client.GitHubApiError, match="reconnect"):
        await github_client.list_repositories(TOKEN)


@pytest.mark.asyncio
async def test_get_repository_rejects_a_malformed_name():
    with pytest.raises(github_client.GitHubApiError):
        await github_client.get_repository(TOKEN, "not-a-full-name")


@pytest.mark.asyncio
async def test_head_commit_failure_is_not_fatal(monkeypatch):
    _patch_httpx(monkeypatch, lambda request: httpx.Response(404, json={}))
    assert await github_client.get_head_commit(TOKEN, "octocat/hello-world", "main") is None


# --- Download ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_extracts_and_strips_the_wrapper_directory(monkeypatch, tmp_path):
    tarball = _make_tarball(
        {"README.md": "# hello\n", "app/main.py": "print('hi')\n"}
    )
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=tarball))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    result = await download_repository(TOKEN, "octocat/hello-world", "main")
    try:
        # The returned path is the repo root, not GitHub's wrapper directory.
        assert (result.path / "README.md").read_text() == "# hello\n"
        assert (result.path / "app" / "main.py").is_file()
        assert result.file_count == 2
        assert result.total_bytes > 0
    finally:
        download_mod.cleanup(result.workdir)


@pytest.mark.asyncio
async def test_downloaded_files_are_never_executed_only_read(monkeypatch, tmp_path):
    """A file marked executable in the archive lands as inert data on disk."""
    canary = tmp_path / "canary.txt"
    tarball = _make_tarball({"evil.sh": f"#!/bin/sh\ntouch {canary}\n"})
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=tarball))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    result = await download_repository(TOKEN, "octocat/hello-world", "main")
    try:
        assert (result.path / "evil.sh").is_file()
        assert not canary.exists()  # nothing ran
    finally:
        download_mod.cleanup(result.workdir)


@pytest.mark.asyncio
async def test_path_traversal_member_cannot_escape_the_workdir(monkeypatch, tmp_path):
    """A `../../` member must not write outside the extraction directory."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        data = b"pwned"
        info = tarfile.TarInfo("wrapper/../../../escaped.txt")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=buffer.getvalue()))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    with pytest.raises(RepositoryDownloadError):
        await download_repository(TOKEN, "octocat/hello-world", "main")
    assert not (tmp_path.parent / "escaped.txt").exists()
    assert not Path("/tmp/escaped.txt").exists()


@pytest.mark.asyncio
async def test_absolute_path_member_stays_inside_the_workdir(monkeypatch, tmp_path):
    """
    An absolute member path must not write to that absolute location.

    Python's data filter sanitizes `/tmp/x` into a relative path inside the
    destination rather than raising, so the check here is containment: the file
    exists under our temp directory and nowhere else.
    """
    escape_target = Path("/tmp/deployforge-absolute-escape.txt")
    escape_target.unlink(missing_ok=True)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        data = b"pwned"
        info = tarfile.TarInfo(str(escape_target))
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=buffer.getvalue()))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    result = await download_repository(TOKEN, "octocat/hello-world", "main")
    try:
        assert not escape_target.exists()
        written = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert written and all(tmp_path in p.parents for p in written)
    finally:
        download_mod.cleanup(result.workdir)


@pytest.mark.asyncio
async def test_symlink_member_is_rejected(monkeypatch, tmp_path):
    """A symlink to /etc/passwd must not be created during extraction."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("wrapper/passwd-link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        archive.addfile(info)
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=buffer.getvalue()))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    with pytest.raises(RepositoryDownloadError):
        await download_repository(TOKEN, "octocat/hello-world", "main")


@pytest.mark.asyncio
async def test_too_many_files_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(download_mod, "MAX_FILE_COUNT", 3)
    tarball = _make_tarball({f"file{i}.txt": "x" for i in range(10)})
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=tarball))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    with pytest.raises(RepositoryDownloadError, match="more than 3 files"):
        await download_repository(TOKEN, "octocat/hello-world", "main")


@pytest.mark.asyncio
async def test_oversized_contents_are_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(download_mod, "MAX_EXTRACTED_BYTES", 100)
    tarball = _make_tarball({"big.txt": "x" * 5000})
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=tarball))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    with pytest.raises(RepositoryDownloadError, match="exceed"):
        await download_repository(TOKEN, "octocat/hello-world", "main")


@pytest.mark.asyncio
async def test_a_failed_download_leaves_no_temp_directory(monkeypatch, tmp_path):
    _patch_httpx(monkeypatch, lambda request: httpx.Response(404, content=b""))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    with pytest.raises(RepositoryDownloadError):
        await download_repository(TOKEN, "octocat/hello-world", "main")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_context_manager_removes_the_directory_afterwards(monkeypatch, tmp_path):
    tarball = _make_tarball({"README.md": "# hi\n"})
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=tarball))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    async with download_mod.downloaded_repository(
        TOKEN, "octocat/hello-world", "main"
    ) as repo:
        inside = repo.path
        assert inside.is_dir()
    assert not inside.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_directory_is_removed_even_if_the_caller_raises(monkeypatch, tmp_path):
    tarball = _make_tarball({"README.md": "# hi\n"})
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, content=tarball))
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    with pytest.raises(ValueError):
        async with download_mod.downloaded_repository(
            TOKEN, "octocat/hello-world", "main"
        ):
            raise ValueError("boom")
    assert list(tmp_path.iterdir()) == []


# --- Routes -----------------------------------------------------------------

async def _connected_user(client, db_session, credentials, monkeypatch):
    """
    Sign up, and give the account a GitHub connection with a usable token.

    Returns (headers, user_id). Assertions scope to that user id: these tests
    share a real database that may already contain unrelated rows, so a global
    `select(Repository)` would be wrong.
    """
    from app.github.crypto import encrypt_token
    from app.models.github import GitHubConnection

    res = await client.post("/auth/signup", json=credentials)
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    user_id = uuid.UUID(res.json()["user"]["id"])

    db_session.add(
        GitHubConnection(
            user_id=user_id,
            github_username="octocat",
            github_user_id=583231,
            access_token_enc=encrypt_token(TOKEN),
            scopes="repo",
        )
    )
    await db_session.commit()
    return headers, user_id


def _repos_for(user_id: uuid.UUID):
    return select(Repository).where(Repository.user_id == user_id)


async def _scan(client, headers):
    res = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _scan_and_select(client, headers, deploy_path: str = ""):
    """The two-step flow: scan the repo, then choose a target."""
    scan = await _scan(client, headers)
    return await client.post(
        "/repos/select",
        json={"scan_token": scan["scan_token"], "deploy_path": deploy_path},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_listing_repos_requires_login(client):
    assert (await client.get("/github/repos")).status_code == 401


@pytest.mark.asyncio
async def test_scanning_without_a_github_connection_is_a_clear_409(
    client, user_credentials
):
    res = await client.post("/auth/signup", json=user_credentials)
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    scanned = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    assert scanned.status_code == 409


@pytest.mark.asyncio
async def test_listing_repos_without_a_github_connection_is_a_clear_409(
    client, user_credentials
):
    res = await client.post("/auth/signup", json=user_credentials)
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    listed = await client.get("/github/repos", headers=headers)
    assert listed.status_code == 409
    assert "connect your github account" in listed.text.lower()


@pytest.mark.asyncio
async def test_listing_repos_returns_the_users_repositories(
    client, db_session, user_credentials, monkeypatch
):
    headers, user_id = await _connected_user(client, db_session, user_credentials, monkeypatch)
    _patch_httpx(monkeypatch, lambda request: httpx.Response(200, json=[REPO_JSON]))

    res = await client.get("/github/repos", headers=headers)
    assert res.status_code == 200
    assert res.json()[0]["full_name"] == "octocat/hello-world"
    assert TOKEN not in res.text  # the token never travels to the client


def _github_serving(monkeypatch, files: dict[str, str]):
    """Serve repo metadata, a head commit, and a tarball of `files`."""
    tarball = _make_tarball(files)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/tarball/main"):
            return httpx.Response(200, content=tarball)
        if "/commits/" in path:
            return httpx.Response(200, json={"sha": "a" * 40})
        return httpx.Response(200, json=REPO_JSON)

    _patch_httpx(monkeypatch, handler)


@pytest.mark.asyncio
async def test_selecting_a_repo_persists_a_row(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    headers, user_id = await _connected_user(client, db_session, user_credentials, monkeypatch)
    _github_serving(monkeypatch, {"requirements.txt": "Django==5.0\n"})
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    res = await _scan_and_select(client, headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["full_name"] == "octocat/hello-world"
    assert body["deploy_path"] is None  # the repository root

    row = (await db_session.execute(_repos_for(user_id))).scalar_one()
    assert row.github_repo_id == 1296269
    assert row.default_branch == "main"
    assert row.deploy_path is None


@pytest.mark.asyncio
async def test_selecting_the_same_target_twice_updates_one_row(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    headers, user_id = await _connected_user(client, db_session, user_credentials, monkeypatch)
    _github_serving(monkeypatch, {"requirements.txt": "Django==5.0\n"})
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    first = await _scan_and_select(client, headers)
    second = await _scan_and_select(client, headers)
    assert first.json()["repository_id"] == second.json()["repository_id"]
    assert len((await db_session.execute(_repos_for(user_id))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_repo_metadata_comes_from_the_signed_scan_not_the_request_body(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """A client cannot smuggle in its own repo id, branch or clone URL."""
    headers, user_id = await _connected_user(client, db_session, user_credentials, monkeypatch)
    _github_serving(monkeypatch, {"requirements.txt": "Django==5.0\n"})
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    scan = await _scan(client, headers)
    await client.post(
        "/repos/select",
        json={
            "scan_token": scan["scan_token"],
            "deploy_path": "",
            "github_repo_id": 999999,
            "default_branch": "attacker-branch",
            "clone_url": "https://evil.example.com/x.git",
            "full_name": "attacker/repo",
        },
        headers=headers,
    )
    row = (await db_session.execute(_repos_for(user_id))).scalar_one()
    assert row.github_repo_id == 1296269
    assert row.full_name == "octocat/hello-world"
    assert row.default_branch == "main"
    assert row.clone_url == REPO_JSON["clone_url"]


@pytest.mark.asyncio
async def test_analyze_downloads_and_reports_the_contents(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    headers, user_id = await _connected_user(client, db_session, user_credentials, monkeypatch)
    _github_serving(monkeypatch, {"README.md": "# hi\n", "requirements.txt": "django\n"})
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))

    repo_id = (await _scan_and_select(client, headers)).json()["repository_id"]

    res = await client.post(f"/repos/{repo_id}/analyze", headers=headers)
    assert res.status_code == 200
    assert res.json()["file_count"] == 2
    assert res.json()["commit_sha"] == "a" * 40
    # The working directory does not outlive the request.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_analyzing_someone_elses_repository_is_a_404(
    client, db_session, user_credentials, admin_credentials, monkeypatch, tmp_path
):
    """Repository ids are scoped to their owner."""
    owner_headers, _ = await _connected_user(client, db_session, user_credentials, monkeypatch)
    _github_serving(monkeypatch, {"requirements.txt": "django\n"})
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))
    repo_id = (await _scan_and_select(client, owner_headers)).json()["repository_id"]

    other = await client.post("/auth/signup", json=admin_credentials)
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    res = await client.post(f"/repos/{repo_id}/analyze", headers=other_headers)
    assert res.status_code == 404
