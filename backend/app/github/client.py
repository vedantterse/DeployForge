"""
GitHub REST API client.

Every call takes a decrypted access token and talks to api.github.com over
httpx. Nothing here touches the database or FastAPI.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.errors import AppError

GITHUB_API_URL = "https://api.github.com"
_API_VERSION = "2022-11-28"
_TIMEOUT = 15.0


class GitHubApiError(AppError):
    code = "github_api_error"
    status_code = 502


def api_headers(access_token: str) -> dict[str, str]:
    """Standard headers for an authenticated GitHub API request."""
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {access_token}",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "DeployForge",
    }


async def _get(access_token: str, path: str, **params: Any) -> Any:
    """GET a GitHub API path, raising GitHubApiError with a useful message."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{GITHUB_API_URL}{path}",
                headers=api_headers(access_token),
                params=params or None,
            )
    except httpx.HTTPError as exc:
        raise GitHubApiError(f"Could not reach GitHub: {type(exc).__name__}") from exc

    if response.status_code == 401:
        raise GitHubApiError(
            "GitHub rejected the stored token. Please reconnect your GitHub account.",
        )
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise GitHubApiError("GitHub API rate limit exceeded. Try again later.")
    if response.status_code >= 400:
        raise GitHubApiError(f"GitHub API error (HTTP {response.status_code}).")

    try:
        return response.json()
    except ValueError as exc:
        raise GitHubApiError("GitHub returned an unreadable response.") from exc


async def get_authenticated_user(access_token: str) -> dict[str, Any]:
    """The GitHub account the token belongs to (`GET /user`)."""
    user = await _get(access_token, "/user")
    if not isinstance(user, dict) or "login" not in user:
        raise GitHubApiError("Unexpected response from GitHub for the current user.")
    return user


# How many pages of 100 repos to walk. A bound, so one very large account
# cannot make a single request unbounded in time or memory.
_MAX_REPO_PAGES = 5
_PER_PAGE = 100


def _repo_summary(repo: dict[str, Any]) -> dict[str, Any]:
    """Trim GitHub's very large repo object down to the fields we use."""
    return {
        "github_repo_id": repo["id"],
        "name": repo["name"],
        "full_name": repo["full_name"],
        "description": repo.get("description"),
        "language": repo.get("language"),
        "default_branch": repo.get("default_branch") or "main",
        "clone_url": repo.get("clone_url") or "",
        "html_url": repo.get("html_url") or "",
        "private": bool(repo.get("private")),
        "fork": bool(repo.get("fork")),
        "updated_at": repo.get("pushed_at") or repo.get("updated_at"),
        # When the repository appeared on this account. For a fork that is the
        # moment it was forked, which is the only date that reflects the user
        # actually doing something.
        "created_at": repo.get("created_at"),
    }


def _recency(repo: dict[str, Any]) -> str:
    """
    The date to order a repository by: the later of pushed and created.

    Pushed alone is wrong for forks. A fork inherits the parent's `pushed_at`,
    so a repository forked seconds ago can carry a date from years back and
    sink to the bottom of the list — which looks exactly like the platform
    failing to notice it. Taking whichever date is later puts both a fresh fork
    and an actively developed repository where the user expects them.
    """
    return max(
        str(repo.get("updated_at") or ""),
        str(repo.get("created_at") or ""),
    )


async def list_repositories(access_token: str) -> list[dict[str, Any]]:
    """
    Every repository the token can see, most recently *touched* first.

    Walks pages until GitHub returns a short page or the page cap is reached.
    GitHub is asked for `sort=pushed` so the page cap keeps the liveliest
    repositories; the final order is decided here (see `_recency`).
    """
    repos: list[dict[str, Any]] = []
    for page in range(1, _MAX_REPO_PAGES + 1):
        batch = await _get(
            access_token,
            "/user/repos",
            per_page=_PER_PAGE,
            page=page,
            sort="pushed",
            direction="desc",
            affiliation="owner,collaborator,organization_member",
        )
        if not isinstance(batch, list):
            raise GitHubApiError("Unexpected response from GitHub for repositories.")
        repos.extend(_repo_summary(r) for r in batch if isinstance(r, dict))
        if len(batch) < _PER_PAGE:
            break

    repos.sort(key=_recency, reverse=True)
    return repos


async def get_repository(access_token: str, full_name: str) -> dict[str, Any]:
    """
    Canonical metadata for one repo (`GET /repos/{owner}/{repo}`).

    Called before a download so the stored row reflects what GitHub says, not
    what the browser claimed.
    """
    if full_name.count("/") != 1 or not all(part.strip() for part in full_name.split("/")):
        raise GitHubApiError(f"Not a valid repository name: {full_name!r}")

    repo = await _get(access_token, f"/repos/{full_name}")
    if not isinstance(repo, dict) or "full_name" not in repo:
        raise GitHubApiError(f"Repository not found: {full_name}")
    return _repo_summary(repo)


async def get_head_commit(access_token: str, full_name: str, ref: str) -> str | None:
    """
    The commit SHA at the tip of `ref`, or None if it cannot be determined.

    Best-effort: a missing SHA is recorded as null rather than failing the
    whole analysis.
    """
    try:
        commit = await _get(access_token, f"/repos/{full_name}/commits/{ref}")
    except GitHubApiError:
        return None
    if isinstance(commit, dict) and isinstance(commit.get("sha"), str):
        return commit["sha"]
    return None
