"""
GitHub connect-account routes.

`/github/connect` and `/github/callback` are the two halves of the OAuth flow;
`/github/status` and `/github/disconnect` let the frontend show and undo it.

Note the asymmetry: `/connect` is called by the authenticated frontend and
requires a Bearer token, while `/callback` is a browser redirect arriving from
github.com with no headers at all. The signed `state` is what carries the
user's identity across that gap.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.config import settings
from app.core.errors import AppError, NotFoundError
from app.db import get_db
from app.github import client as github_client
from app.github import oauth
from app.github.crypto import encrypt_token
from app.github.token import get_access_token
from app.models.deployment import Deployment
from app.models.github import GitHubConnection
from app.models.repository import Repository
from app.schemas.github import ConnectionStatusOut, ConnectUrlOut, RepoOut

router = APIRouter(prefix="/github", tags=["github"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _connection_for(db: AsyncSession, user_id) -> GitHubConnection | None:
    result = await db.execute(
        select(GitHubConnection).where(GitHubConnection.user_id == user_id)
    )
    return result.scalar_one_or_none()


# Where the browser is sent after the OAuth round trip. Connecting GitHub is a
# step inside starting a deployment, so the user lands back in that flow.
CALLBACK_LANDING_PATH = "/dashboard/new"


def _back_to_frontend(**params: str) -> RedirectResponse:
    """Send the browser back to the frontend with the result in the query string."""
    origin = (
        settings.cors_origins[0] if settings.cors_origins else "http://localhost:3000"
    )
    return RedirectResponse(
        url=f"{origin}{CALLBACK_LANDING_PATH}?{urlencode(params)}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/connect", response_model=ConnectUrlOut)
async def connect(current_user: CurrentUser) -> ConnectUrlOut:
    """
    Start the OAuth flow.

    Returns the URL to navigate to rather than issuing a redirect: this route
    is authenticated with a Bearer token, and a browser navigation cannot send
    one. Putting the app JWT in a query string instead would leak it into
    server logs, browser history and the Referer header.
    """
    state = oauth.create_state(current_user.id)
    return ConnectUrlOut(authorize_url=oauth.build_authorize_url(state))


@router.get("/callback", include_in_schema=True)
async def callback(
    db: DbSession,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """
    Finish the OAuth flow and store the encrypted token.

    Always ends in a redirect back to the frontend — this is a browser
    navigation, so a JSON error body would just be shown as raw text. Failures
    come back as `?github=error&reason=...`.
    """
    # The user pressed "Cancel" on GitHub's consent screen.
    if error:
        return _back_to_frontend(
            github="error", reason=error_description or error
        )

    try:
        user_id = oauth.verify_state(state or "")
        access_token, granted_scopes = await oauth.exchange_code_for_token(code or "")
        github_user = await github_client.get_authenticated_user(access_token)
    except AppError as exc:
        return _back_to_frontend(github="error", reason=exc.message)

    connection = await _connection_for(db, user_id)
    if connection is None:
        connection = GitHubConnection(user_id=user_id)
        db.add(connection)

    # Reconnecting overwrites the previous token — one connection per user.
    connection.github_username = github_user["login"]
    connection.github_user_id = int(github_user["id"])
    connection.access_token_enc = encrypt_token(access_token)
    connection.scopes = granted_scopes

    await db.commit()

    return _back_to_frontend(github="connected", username=github_user["login"])


@router.get("/status", response_model=ConnectionStatusOut)
async def connection_status(
    current_user: CurrentUser, db: DbSession
) -> ConnectionStatusOut:
    """Whether the current user has connected GitHub. Never returns the token."""
    connection = await _connection_for(db, current_user.id)
    if connection is None:
        return ConnectionStatusOut(connected=False)
    return ConnectionStatusOut(
        connected=True,
        github_username=connection.github_username,
        github_user_id=connection.github_user_id,
        scopes=connection.scopes,
        connected_at=connection.created_at,
    )


@router.get("/repos", response_model=list[RepoOut])
async def list_repos(current_user: CurrentUser, db: DbSession) -> list[RepoOut]:
    """
    The repositories the connected GitHub account can see.

    Read live from GitHub with the decrypted token — nothing is cached, so the
    list is never stale and no repository metadata is stored until the user
    actually picks one.
    """
    access_token = await get_access_token(db, current_user.id)
    repos = await github_client.list_repositories(access_token)

    # Which of them this account has already connected, and where. Marking the
    # list is the difference between "you cannot deploy this twice" being a
    # visible fact and being an error the user discovers three clicks later.
    rows = (
        await db.execute(
            select(Repository.github_repo_id, Repository.deploy_path, Repository.id)
            .where(Repository.user_id == current_user.id)
        )
    ).all()

    connected: dict[int, list[str]] = {}
    for github_repo_id, deploy_path, _repo_id in rows:
        connected.setdefault(github_repo_id, []).append(deploy_path or "")

    latest_deployment = {
        repo_id: deployment_id
        for repo_id, deployment_id in (
            await db.execute(
                select(Repository.github_repo_id, Deployment.id)
                .join(Deployment, Deployment.repository_id == Repository.id)
                .where(Repository.user_id == current_user.id)
                .order_by(Deployment.created_at.desc())
            )
        ).all()
    }

    out: list[RepoOut] = []
    for repo in repos:
        paths = connected.get(repo["github_repo_id"], [])
        out.append(
            RepoOut.model_validate(
                {
                    **repo,
                    "connected": bool(paths),
                    "connected_paths": sorted(paths),
                    "deployment_id": latest_deployment.get(repo["github_repo_id"]),
                }
            )
        )
    return out


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(current_user: CurrentUser, db: DbSession) -> Response:
    """Forget the stored token. The grant itself is revoked on GitHub's side."""
    connection = await _connection_for(db, current_user.id)
    if connection is None:
        raise NotFoundError("No GitHub connection to disconnect.")
    await db.delete(connection)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
