"""API shapes for the GitHub connection."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ConnectUrlOut(BaseModel):
    """Where to send the browser to start the OAuth flow."""

    authorize_url: str


class ConnectionStatusOut(BaseModel):
    """Whether this user has connected GitHub, and to which account."""

    connected: bool
    github_username: str | None = None
    github_user_id: int | None = None
    scopes: str | None = None
    connected_at: datetime | None = None


class RepoOut(BaseModel):
    """One repository as listed from GitHub (not necessarily connected yet)."""

    github_repo_id: int
    name: str
    full_name: str
    description: str | None = None
    language: str | None = None
    default_branch: str
    clone_url: str
    html_url: str
    private: bool
    updated_at: datetime | None = None

    # --- what this account has already done with it ---
    # A repository can only be connected once per target, so the list marks
    # what is taken rather than letting a student pick it and then fail.
    connected: bool = False
    # Which targets inside it are already connected. `""` means the whole
    # repository; a monorepo can have `frontend` taken and `backend` free.
    connected_paths: list[str] = []
    deployment_id: uuid.UUID | None = None
