"""
Look up and decrypt the current user's GitHub token.

Kept in one place so no route ever reaches into `access_token_enc` directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.github.crypto import TokenEncryptionError, decrypt_token
from app.models.github import GitHubConnection


class GitHubNotConnectedError(AppError):
    code = "github_not_connected"
    status_code = 409


async def get_connection(
    db: AsyncSession, user_id: uuid.UUID
) -> GitHubConnection | None:
    result = await db.execute(
        select(GitHubConnection).where(GitHubConnection.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_access_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    """
    The decrypted GitHub token for `user_id`.

    Raises GitHubNotConnectedError when GitHub has not been connected, or when
    the stored ciphertext can no longer be decrypted (a rotated key) — in both
    cases the fix is the same: connect GitHub again.
    """
    connection = await get_connection(db, user_id)
    if connection is None:
        raise GitHubNotConnectedError(
            "Connect your GitHub account before listing repositories."
        )
    try:
        return decrypt_token(connection.access_token_enc)
    except TokenEncryptionError as exc:
        raise GitHubNotConnectedError(
            "Your stored GitHub token could not be read. Please reconnect GitHub."
        ) from exc
