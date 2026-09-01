"""
End-to-end tests for the analyze flow: download -> detect -> persist.

Real tarballs of each repository shape are pushed through the endpoint, and
both the Repository row and the Deployment row are checked. GitHub is mocked;
detection and the database are real.
"""

from __future__ import annotations

import io
import json
import tarfile
import time
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.repository import DetectedType, Repository

TOKEN = "gho_averysecrettoken"
COMMIT = "b" * 40

REPO_JSON = {
    "id": 1296269,
    "name": "hello-world",
    "full_name": "octocat/hello-world",
    "description": None,
    "language": "Python",
    "default_branch": "main",
    "clone_url": "https://github.com/octocat/hello-world.git",
    "html_url": "https://github.com/octocat/hello-world",
    "private": False,
    "pushed_at": "2026-08-01T10:00:00Z",
}


def _tarball(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(f"octocat-hello-world-abc123/{name}")
            info.size = len(data)
            info.mtime = int(time.time())
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


# The handler in force for the current test. Held in a mutable box so a test
# can change what GitHub serves (e.g. "the repo gained a Dockerfile") by
# swapping the entry — patching httpx a second time would stack the patches and
# the first one, applied innermost, would win.
_SERVING: dict = {}


def _mock_github(monkeypatch, files: dict[str, str]) -> None:
    """Serve repo metadata, the head commit, and a tarball of `files`."""
    tarball = _tarball(files)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/tarball/main"):
            return httpx.Response(200, content=tarball)
        if "/commits/" in path:
            return httpx.Response(200, json={"sha": COMMIT})
        return httpx.Response(200, json=REPO_JSON)

    _SERVING["handler"] = handler

    if getattr(httpx.AsyncClient.__init__, "_deployforge_mock", False):
        return  # already patched for this test; the swap above is enough

    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda request: _SERVING["handler"](request)
        )
        real_init(self, *args, **kwargs)

    patched_init._deployforge_mock = True
    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def _connected(client, db_session, credentials, monkeypatch, tmp_path, files):
    """Sign up, connect GitHub, and start serving `files` as the repository."""
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

    _mock_github(monkeypatch, files)
    monkeypatch.setattr(settings, "repo_workdir", str(tmp_path))
    return headers, user_id


async def _analyze(
    client, db_session, credentials, monkeypatch, tmp_path, files, deploy_path=""
):
    """
    The full flow: sign up, connect GitHub, scan the repo, pick a target.

    Returns (response, headers, repository_id, user_id).
    """
    headers, user_id = await _connected(
        client, db_session, credentials, monkeypatch, tmp_path, files
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    assert scan.status_code == 200, scan.text
    response = await client.post(
        "/repos/select",
        json={"scan_token": scan.json()["scan_token"], "deploy_path": deploy_path},
        headers=headers,
    )
    repo_id = (
        uuid.UUID(response.json()["repository_id"])
        if response.status_code == 201
        else None
    )
    return response, headers, repo_id, user_id


# --- Docker beats everything ------------------------------------------------

@pytest.mark.asyncio
async def test_dockerfile_repo_is_detected_as_docker(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"Dockerfile": "FROM python:3.12\n", "app.py": "print('hi')\n"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["type"] == "docker"
    assert body["compose"] is False
    assert body["build_method"] == "docker"
    assert body["framework"] is None

    repo = await db_session.get(Repository, repo_id)
    await db_session.refresh(repo)
    assert repo.detected_type == DetectedType.DOCKER
    assert repo.detected_framework is None
    assert repo.last_analyzed_at is not None


@pytest.mark.asyncio
async def test_compose_repo_sets_the_compose_flag(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"docker-compose.yml": "services:\n  web:\n"},
    )
    body = res.json()
    assert body["type"] == "docker"
    assert body["compose"] is True
    assert body["build_method"] == "docker"

    repo = await db_session.get(Repository, repo_id)
    await db_session.refresh(repo)
    assert repo.detection_meta["compose"] is True


@pytest.mark.asyncio
async def test_docker_wins_over_a_framework(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """A repo with both a Dockerfile and package.json is a Docker repo."""
    res, _, _, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {
            "Dockerfile": "FROM node:20\n",
            "package.json": json.dumps({"dependencies": {"next": "14"}}),
        },
    )
    assert res.json()["type"] == "docker"
    assert res.json()["build_method"] == "docker"


# --- No Docker: framework + buildpack ---------------------------------------

@pytest.mark.asyncio
async def test_django_repo_is_detected_as_a_buildpack_framework(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"requirements.txt": "Django==5.0\ngunicorn\n", "manage.py": "# django\n"},
    )
    body = res.json()
    assert body["type"] == "framework"
    assert body["framework"] == "django"
    assert body["build_method"] == "buildpack"
    assert body["compose"] is False
    assert "requirements.txt" in body["evidence"]

    repo = await db_session.get(Repository, repo_id)
    await db_session.refresh(repo)
    assert repo.detected_type == DetectedType.FRAMEWORK
    assert repo.detected_framework == "django"


@pytest.mark.asyncio
async def test_nextjs_repo_is_detected(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, _, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"package.json": json.dumps({"dependencies": {"next": "14", "react": "18"}})},
    )
    assert res.json()["framework"] == "nextjs"
    assert res.json()["build_method"] == "buildpack"


@pytest.mark.asyncio
async def test_fastapi_repo_is_detected(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, _, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"requirements.txt": "fastapi\nuvicorn\n"},
    )
    assert res.json()["framework"] == "fastapi"


# --- Unknown ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_unrecognized_repo_is_unknown_with_a_reason(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"README.md": "# just docs\n"},
    )
    body = res.json()
    assert body["type"] == "unknown"
    assert body["framework"] is None
    assert body["build_method"] is None
    assert body["reason"]  # explains why nothing matched

    repo = await db_session.get(Repository, repo_id)
    await db_session.refresh(repo)
    assert repo.detected_type == DetectedType.UNKNOWN


# --- What gets persisted ----------------------------------------------------

@pytest.mark.asyncio
async def test_full_detection_result_is_kept_in_detection_meta(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"requirements.txt": "flask\n"},
    )
    repo = await db_session.get(Repository, repo_id)
    await db_session.refresh(repo)

    meta = repo.detection_meta
    assert set(meta) == {"type", "framework", "compose", "build_method", "evidence", "reason"}
    assert meta["framework"] == "flask"
    assert meta["build_method"] == "buildpack"
    assert meta["evidence"]
    # The API response and the stored result agree.
    assert res.json()["reason"] == meta["reason"]


@pytest.mark.asyncio
async def test_a_deployment_row_is_created_with_status_analyzed(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, repo_id, user_id = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"requirements.txt": "Django==5.0\n"},
    )
    deployments = (
        await db_session.execute(
            select(Deployment).where(Deployment.repository_id == repo_id)
        )
    ).scalars().all()

    assert len(deployments) == 1
    deployment = deployments[0]
    assert deployment.status == DeploymentStatus.ANALYZED
    assert deployment.build_method == BuildMethod.BUILDPACK
    assert deployment.commit_sha == COMMIT
    assert deployment.user_id == user_id  # denormalized for querying
    assert str(deployment.id) == res.json()["deployment_id"]

    # Phase 1 fills nothing infrastructure-related.
    assert deployment.subdomain is None
    assert deployment.container_id is None
    assert deployment.target_server_ip is None
    assert deployment.error_message is None


@pytest.mark.asyncio
async def test_docker_repo_records_build_method_docker(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    _, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"Dockerfile": "FROM alpine\n"},
    )
    deployment = (
        await db_session.execute(
            select(Deployment).where(Deployment.repository_id == repo_id)
        )
    ).scalar_one()
    assert deployment.build_method == BuildMethod.DOCKER


@pytest.mark.asyncio
async def test_unknown_repo_records_no_build_method(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    _, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"README.md": "# docs\n"},
    )
    deployment = (
        await db_session.execute(
            select(Deployment).where(Deployment.repository_id == repo_id)
        )
    ).scalar_one()
    assert deployment.build_method is None
    assert deployment.status == DeploymentStatus.ANALYZED


@pytest.mark.asyncio
async def test_re_analyzing_updates_the_repo_and_appends_a_deployment(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """One Repository row, one Deployment row per analysis attempt."""
    _, headers, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"requirements.txt": "Django==5.0\n"},
    )
    repo = await db_session.get(Repository, repo_id)
    await db_session.refresh(repo)
    first_analyzed_at = repo.last_analyzed_at
    assert repo.detected_framework == "django"

    # The repo gains a Dockerfile and is analyzed again.
    _mock_github(monkeypatch, {"Dockerfile": "FROM python:3.12\n"})
    second = await client.post(f"/repos/{repo_id}/analyze", headers=headers)
    assert second.status_code == 200
    assert second.json()["type"] == "docker"

    await db_session.refresh(repo)
    assert repo.detected_type == DetectedType.DOCKER
    assert repo.detected_framework is None  # cleared, not left stale
    assert repo.last_analyzed_at >= first_analyzed_at

    deployments = (
        await db_session.execute(
            select(Deployment).where(Deployment.repository_id == repo_id)
        )
    ).scalars().all()
    assert len(deployments) == 2
    assert {d.build_method for d in deployments} == {
        BuildMethod.BUILDPACK,
        BuildMethod.DOCKER,
    }


@pytest.mark.asyncio
async def test_the_downloaded_files_are_gone_afterwards(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, _, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"requirements.txt": "Django==5.0\n"},
    )
    assert res.status_code == 201
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_the_repository_row_reports_detection_through_the_api(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    _, headers, _, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"requirements.txt": "Django==5.0\n"},
    )
    listed = (await client.get("/repos", headers=headers)).json()
    assert len(listed) == 1
    assert listed[0]["detected_type"] == "framework"
    assert listed[0]["detected_framework"] == "django"
    assert listed[0]["last_analyzed_at"] is not None


# --- Monorepos: the user chooses the target ---------------------------------

AMVEX = {
    "README.md": "# amvex\n",
    "backend/requirements.txt": "fastapi\nuvicorn\n",
    "backend/main.py": "app = 1\n",
    "frontend/package.json": json.dumps({"dependencies": {"next": "14", "react": "18"}}),
    "frontend/tsconfig.json": "{}",
}


@pytest.mark.asyncio
async def test_scan_offers_both_halves_of_a_monorepo(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """The Amvex shape: nothing at the root, a Python backend, a TS frontend."""
    headers, _ = await _connected(
        client, db_session, user_credentials, monkeypatch, tmp_path, AMVEX
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    assert scan.status_code == 200
    body = scan.json()

    by_path = {c["path"]: c for c in body["candidates"]}
    assert by_path[""]["type"] == "unknown"
    assert by_path[""]["label"] == "Whole repository"
    assert by_path["backend"]["framework"] == "fastapi"
    assert by_path["backend"]["build_method"] == "buildpack"
    assert by_path["frontend"]["framework"] == "nextjs"
    assert by_path["frontend"]["label"] == "frontend/"

    # Scanning alone writes nothing — the user has not chosen yet.
    assert (
        await db_session.execute(select(Repository).where(Repository.full_name == "octocat/hello-world"))
    ).first() is None


@pytest.mark.asyncio
async def test_selecting_a_subdirectory_stores_its_detection(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res, _, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path, AMVEX,
        deploy_path="frontend",
    )
    assert res.status_code == 201
    body = res.json()
    assert body["deploy_path"] == "frontend"
    assert body["type"] == "framework"
    assert body["framework"] == "nextjs"
    assert body["build_method"] == "buildpack"

    repo = await db_session.get(Repository, repo_id)
    await db_session.refresh(repo)
    assert repo.deploy_path == "frontend"
    assert repo.detected_framework == "nextjs"
    assert repo.target_label == "octocat/hello-world (frontend/)"


@pytest.mark.asyncio
async def test_both_halves_can_be_connected_as_separate_targets(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """(user_id, github_repo_id, deploy_path) is unique, so both fit."""
    headers, user_id = await _connected(
        client, db_session, user_credentials, monkeypatch, tmp_path, AMVEX
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    token = scan.json()["scan_token"]

    for path in ("frontend", "backend"):
        res = await client.post(
            "/repos/select",
            json={"scan_token": token, "deploy_path": path},
            headers=headers,
        )
        assert res.status_code == 201, res.text

    rows = (
        await db_session.execute(
            select(Repository).where(Repository.user_id == user_id)
        )
    ).scalars().all()
    assert {r.deploy_path for r in rows} == {"frontend", "backend"}
    assert {r.detected_framework for r in rows} == {"nextjs", "fastapi"}
    assert len({r.github_repo_id for r in rows}) == 1  # the same repo


@pytest.mark.asyncio
async def test_re_analyzing_a_subdirectory_target_detects_that_subdirectory(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """A later analyze must look at the chosen path, not the repository root."""
    _, headers, repo_id, _ = await _analyze(
        client, db_session, user_credentials, monkeypatch, tmp_path, AMVEX,
        deploy_path="backend",
    )
    res = await client.post(f"/repos/{repo_id}/analyze", headers=headers)
    assert res.status_code == 200
    assert res.json()["deploy_path"] == "backend"
    assert res.json()["framework"] == "fastapi"


@pytest.mark.asyncio
async def test_selecting_a_path_that_was_not_scanned_is_rejected(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    headers, user_id = await _connected(
        client, db_session, user_credentials, monkeypatch, tmp_path, AMVEX
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    res = await client.post(
        "/repos/select",
        json={"scan_token": scan.json()["scan_token"], "deploy_path": "../../etc"},
        headers=headers,
    )
    assert res.status_code == 400
    assert (
        await db_session.execute(select(Repository).where(Repository.user_id == user_id))
    ).first() is None


@pytest.mark.asyncio
async def test_a_tampered_scan_token_is_rejected(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """The client cannot rewrite what was detected."""
    headers, user_id = await _connected(
        client, db_session, user_credentials, monkeypatch, tmp_path, AMVEX
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    tampered = scan.json()["scan_token"][:-3] + "abc"
    res = await client.post(
        "/repos/select",
        json={"scan_token": tampered, "deploy_path": "frontend"},
        headers=headers,
    )
    assert res.status_code == 400
    assert (
        await db_session.execute(select(Repository).where(Repository.user_id == user_id))
    ).first() is None


@pytest.mark.asyncio
async def test_another_users_scan_token_cannot_be_used(
    client, db_session, user_credentials, admin_credentials, monkeypatch, tmp_path
):
    headers, _ = await _connected(
        client, db_session, user_credentials, monkeypatch, tmp_path, AMVEX
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )

    other = await client.post("/auth/signup", json=admin_credentials)
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    res = await client.post(
        "/repos/select",
        json={"scan_token": scan.json()["scan_token"], "deploy_path": "frontend"},
        headers=other_headers,
    )
    assert res.status_code == 400
    assert "different account" in res.text


@pytest.mark.asyncio
async def test_scan_hides_unrecognized_subdirectories(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """Docs and asset folders would bury the real choice."""
    headers, _ = await _connected(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {
            "docs/index.md": "# docs\n",
            "assets/logo.txt": "x",
            "web/package.json": json.dumps({"dependencies": {"react": "18"}}),
        },
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    assert {c["path"] for c in scan.json()["candidates"]} == {"", "web"}


@pytest.mark.asyncio
async def test_a_single_app_repo_still_offers_just_the_root(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    headers, _ = await _connected(
        client, db_session, user_credentials, monkeypatch, tmp_path,
        {"Dockerfile": "FROM python:3.12\n", "app.py": "x\n"},
    )
    scan = await client.post(
        "/repos/scan", json={"full_name": "octocat/hello-world"}, headers=headers
    )
    candidates = scan.json()["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["path"] == ""
    assert candidates[0]["type"] == "docker"
