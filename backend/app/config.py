"""
Application configuration.

Every setting comes from the environment (or a local `.env` file). Nothing is
hardcoded, and no secret has a usable default — see `.env.example` for the
documented list of variables.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend package root, so `.env` is found no matter which directory the
# app, alembic, or pytest happens to be invoked from.
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Settings loaded from environment variables (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    database_url: str = (
        "postgresql+asyncpg://deployforge:deployforge@localhost:5432/deployforge"
    )

    # --- Auth (used from Task 2) ---
    jwt_secret: str = "change-me-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # --- Token encryption (used from Task 3) ---
    token_encryption_key: str = ""

    # --- GitHub OAuth (used from Task 3) ---
    github_client_id: str = ""
    github_client_secret: str = ""
    github_callback_url: str = "http://localhost:8000/github/callback"
    github_oauth_scopes: str = "repo,admin:repo_hook"

    # --- Frontend ---
    frontend_origin: str = "http://localhost:3000"

    # --- Builds ---
    # The pack CLI (Cloud Native Buildpacks). Needs Docker on the same host.
    pack_binary: str = "pack"
    pack_builder: str = "paketobuildpacks/builder-jammy-base"
    # Prefix for image tags, e.g. deployforge/<user>-<repo>:<sha>.
    image_namespace: str = "deployforge"
    # A build that has not finished by now is killed.
    build_timeout_seconds: int = 1800
    # Where build logs are written. Empty = alongside the repo workdir.
    build_log_dir: str = ""

    # --- Misc ---
    # Parent dir for temporary repo downloads. Empty = system temp.
    repo_workdir: str = ""

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def cors_origins(self) -> list[str]:
        """Allowed browser origins, comma-separated in FRONTEND_ORIGIN."""
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — read the environment once per process."""
    return Settings()


settings = get_settings()
