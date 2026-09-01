"""
Environment variables for a deploy target.

Values are encrypted before they are stored and decrypted only when a build
needs them. A variable marked secret is never sent back to the browser.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.crypto import decrypt_value, encrypt_value
from app.core.errors import AppError, NotFoundError
from app.db import get_db
from app.models.environment import EnvironmentVariable
from app.models.repository import Repository
from app.schemas.environment import EnvVarOut, EnvVarsIn

router = APIRouter(prefix="/repos/{repo_id}/env", tags=["environment"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class MissingValueError(AppError):
    code = "missing_value"


async def _owned_repository(
    db: AsyncSession, repo_id: uuid.UUID, user_id: uuid.UUID
) -> Repository:
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id, Repository.user_id == user_id
        )
    )
    repository = result.scalar_one_or_none()
    if repository is None:
        raise NotFoundError("Repository not found.")
    return repository


async def _variables_for(
    db: AsyncSession, repo_id: uuid.UUID
) -> list[EnvironmentVariable]:
    result = await db.execute(
        select(EnvironmentVariable)
        .where(EnvironmentVariable.repository_id == repo_id)
        .order_by(EnvironmentVariable.key)
    )
    return list(result.scalars().all())


def _to_out(variable: EnvironmentVariable) -> EnvVarOut:
    """Reveal the plaintext only for variables not marked secret."""
    value: str | None = None
    if not variable.is_secret:
        try:
            value = decrypt_value(variable.value_enc)
        except Exception:  # noqa: BLE001 — a rotated key must not break the page
            value = None
    return EnvVarOut(
        id=variable.id,
        key=variable.key,
        value=value,
        is_secret=variable.is_secret,
        has_value=True,
        created_at=variable.created_at,
        updated_at=variable.updated_at,
    )


@router.get("", response_model=list[EnvVarOut])
async def list_env_vars(
    repo_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[EnvVarOut]:
    """The target's environment variables. Secret values come back as null."""
    await _owned_repository(db, repo_id, current_user.id)
    return [_to_out(v) for v in await _variables_for(db, repo_id)]


@router.put("", response_model=list[EnvVarOut])
async def replace_env_vars(
    repo_id: uuid.UUID,
    payload: EnvVarsIn,
    current_user: CurrentUser,
    db: DbSession,
) -> list[EnvVarOut]:
    """
    Replace the whole set — this is a form's Save button.

    A variable sent with a null value keeps whatever is stored, which is how a
    secret survives a round trip it was never shown in. A null value for a key
    that does not exist yet is an error, not an empty variable.
    """
    await _owned_repository(db, repo_id, current_user.id)
    existing = {v.key: v for v in await _variables_for(db, repo_id)}
    submitted = {v.key: v for v in payload.variables}

    for key, incoming in submitted.items():
        current = existing.get(key)
        if incoming.value is None:
            if current is None:
                raise MissingValueError(f"No value provided for {key}.")
            current.is_secret = incoming.is_secret
            continue

        if current is None:
            db.add(
                EnvironmentVariable(
                    repository_id=repo_id,
                    key=key,
                    value_enc=encrypt_value(incoming.value),
                    is_secret=incoming.is_secret,
                )
            )
        else:
            current.value_enc = encrypt_value(incoming.value)
            current.is_secret = incoming.is_secret

    # Anything absent from the submission was removed in the form.
    for key, current in existing.items():
        if key not in submitted:
            await db.delete(current)

    await db.commit()
    return [_to_out(v) for v in await _variables_for(db, repo_id)]


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_env_var(
    repo_id: uuid.UUID, key: str, current_user: CurrentUser, db: DbSession
) -> Response:
    """Remove one variable."""
    await _owned_repository(db, repo_id, current_user.id)
    result = await db.execute(
        select(EnvironmentVariable).where(
            EnvironmentVariable.repository_id == repo_id,
            EnvironmentVariable.key == key,
        )
    )
    variable = result.scalar_one_or_none()
    if variable is None:
        raise NotFoundError(f"No environment variable named {key}.")
    await db.delete(variable)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
