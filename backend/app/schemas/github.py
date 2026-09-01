"""API shapes for the GitHub connection."""

from __future__ import annotations

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
