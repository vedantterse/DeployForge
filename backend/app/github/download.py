"""
Download a repository to a temporary working directory.

**Tarball, not `git clone`.** The archive endpoint was chosen because:

  - it needs no `git` binary and no credential helper on the host;
  - the token travels in an Authorization header, never in a URL or a command
    line where it would show up in process listings and shell history;
  - it carries no history and no submodules — just the tree at one ref;
  - extracting an archive is inert, whereas `git clone` runs configured
    helpers/filters. Nothing from the repository is ever executed here. This
    module only writes bytes to disk.

Extraction is hardened three ways: Python 3.12's `filter="data"` rejects
absolute paths, `..` traversal, symlinks, hardlinks and device files; a total
byte cap and a file-count cap stop an archive from filling the disk; and
everything lands under a fresh `mkdtemp` directory that the caller removes.
"""

from __future__ import annotations

import shutil
import tarfile
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import settings
from app.core.errors import AppError
from app.github.client import GITHUB_API_URL, GitHubApiError, api_headers

# Guard rails for a hostile or merely enormous repository.
MAX_ARCHIVE_BYTES = 250 * 1024 * 1024   # 250 MB compressed download
MAX_EXTRACTED_BYTES = 500 * 1024 * 1024  # 500 MB on disk
MAX_FILE_COUNT = 50_000
DOWNLOAD_TIMEOUT = 120.0


class RepositoryDownloadError(AppError):
    code = "repository_download_failed"
    status_code = 502


@dataclass
class DownloadedRepository:
    """Where the repo landed, and what came out of the archive."""

    path: Path          # repository root — what detection is pointed at
    workdir: Path       # temp directory to remove when finished
    file_count: int
    total_bytes: int

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
        }


def _make_workdir(full_name: str) -> Path:
    """A fresh temp directory, under REPO_WORKDIR when one is configured."""
    parent = settings.repo_workdir.strip() or None
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)
    slug = full_name.replace("/", "-")
    return Path(tempfile.mkdtemp(prefix=f"deployforge-{slug}-", dir=parent))


async def _fetch_tarball(access_token: str, full_name: str, ref: str, dest: Path) -> None:
    """Stream the tarball to `dest`, refusing anything over the size cap."""
    url = f"{GITHUB_API_URL}/repos/{full_name}/tarball/{ref}"
    written = 0
    try:
        async with httpx.AsyncClient(
            timeout=DOWNLOAD_TIMEOUT, follow_redirects=True
        ) as client:
            async with client.stream("GET", url, headers=api_headers(access_token)) as response:
                if response.status_code == 404:
                    raise RepositoryDownloadError(
                        f"GitHub could not find {full_name} at ref {ref}."
                    )
                if response.status_code >= 400:
                    raise RepositoryDownloadError(
                        f"GitHub refused the download (HTTP {response.status_code})."
                    )
                with dest.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        written += len(chunk)
                        if written > MAX_ARCHIVE_BYTES:
                            raise RepositoryDownloadError(
                                "Repository archive exceeds "
                                f"{MAX_ARCHIVE_BYTES // (1024 * 1024)} MB."
                            )
                        handle.write(chunk)
    except httpx.HTTPError as exc:
        raise RepositoryDownloadError(
            f"Could not download the repository: {type(exc).__name__}"
        ) from exc

    if written == 0:
        raise RepositoryDownloadError("GitHub returned an empty archive.")


def _check_archive_limits(archive: tarfile.TarFile) -> None:
    """Reject an archive that would write too many or too-large files."""
    total = 0
    count = 0
    for member in archive.getmembers():
        if member.isfile():
            count += 1
            total += member.size
            if count > MAX_FILE_COUNT:
                raise RepositoryDownloadError(
                    f"Repository contains more than {MAX_FILE_COUNT} files."
                )
            if total > MAX_EXTRACTED_BYTES:
                raise RepositoryDownloadError(
                    "Repository contents exceed "
                    f"{MAX_EXTRACTED_BYTES // (1024 * 1024)} MB."
                )


def _extract(tarball: Path, into: Path) -> Path:
    """
    Extract the archive and return the repository root.

    GitHub wraps everything in a single `owner-repo-<sha>/` directory; that
    wrapper is stripped so the returned path is the repository root itself.
    """
    into.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(tarball, mode="r:gz") as archive:
            _check_archive_limits(archive)
            # PEP 706 data filter: no absolute paths, no "..", no links,
            # no device files, no setuid bits.
            archive.extractall(path=into, filter="data")
    except tarfile.TarError as exc:
        raise RepositoryDownloadError(
            f"Could not read the repository archive: {exc}"
        ) from exc

    entries = [p for p in into.iterdir() if not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return into


def _measure(root: Path) -> tuple[int, int]:
    """(file_count, total_bytes) of the extracted tree."""
    count = 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            count += 1
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return count, total


async def download_repository(
    access_token: str, full_name: str, ref: str
) -> DownloadedRepository:
    """
    Fetch `full_name` at `ref` into a fresh temp directory.

    The caller owns the returned directory and must remove it — or use
    `downloaded_repository()`, which does that automatically.
    """
    workdir = _make_workdir(full_name)
    tarball = workdir / "repo.tar.gz"
    extracted = workdir / "src"
    try:
        await _fetch_tarball(access_token, full_name, ref, tarball)
        root = _extract(tarball, extracted)
    except (GitHubApiError, RepositoryDownloadError):
        cleanup(workdir)
        raise
    except Exception as exc:  # never leave a temp directory behind
        cleanup(workdir)
        raise RepositoryDownloadError(
            f"Unexpected error downloading the repository: {type(exc).__name__}"
        ) from exc
    finally:
        tarball.unlink(missing_ok=True)  # the archive itself is not needed once extracted

    file_count, total_bytes = _measure(root)
    return DownloadedRepository(
        path=root,
        workdir=workdir,
        file_count=file_count,
        total_bytes=total_bytes,
    )


def cleanup(path: Path | str) -> None:
    """Remove a working directory. Never raises."""
    shutil.rmtree(Path(path), ignore_errors=True)


@asynccontextmanager
async def downloaded_repository(access_token: str, full_name: str, ref: str):
    """
    Download a repo for the duration of the block, then delete it.

        async with downloaded_repository(token, "octocat/hello", "main") as repo:
            result = detect_repository(repo.path)
    """
    result = await download_repository(access_token, full_name, ref)
    try:
        yield result
    finally:
        cleanup(result.workdir)
