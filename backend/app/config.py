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
    # The run image the built app actually runs on. The base run image omits
    # system libraries that recent Node builds link against (libatomic), so an
    # app builds cleanly and then dies on boot with a missing .so. The full run
    # image carries them, and pairing it with the base builder keeps the 5 GB
    # builder download rather than doubling it.
    pack_run_image: str = ""
    # Node version used when a repository does not pin one itself.
    #
    # Left to its own devices the Node buildpack installs the newest release,
    # and Node 24 links against libatomic, which no Paketo run image ships — so
    # the image builds cleanly and then dies on boot with a missing shared
    # library. Defaulting to the current LTS is the difference between a
    # student's first deploy working and it failing for a reason they have no
    # way to diagnose. A repository that pins its own version still wins.
    default_node_version: str = "22.*"
    # Prefix for image tags, e.g. deployforge/<user>-<repo>:<sha>.
    image_namespace: str = "deployforge"
    # A build that has not finished by now is killed.
    build_timeout_seconds: int = 1800
    # Where build logs are written. Empty = alongside the repo workdir.
    build_log_dir: str = ""

    # --- Image registry ---
    # Where built images are pushed and run from. A build that only tags an
    # image locally cannot be run on another host later; pushing to a registry
    # is what makes the image an artifact rather than a side effect.
    registry_host: str = "localhost:5000"
    registry_push: bool = True

    # --- Runtime ---
    docker_binary: str = "docker"
    # The bridge network app containers and the router share. App containers
    # publish no host ports — the only way in is through the router.
    edge_network: str = "deployforge_edge"
    container_prefix: str = "df"
    # Apps are reachable at <subdomain>.<app_domain>. Browsers resolve any
    # *.localhost name to the loopback address with no DNS or hosts entry,
    # which is what makes per-app URLs work on a laptop.
    app_domain: str = "localhost"
    router_container: str = "deployforge-traefik"
    # Shared secret the router presents when polling for its configuration.
    traefik_provider_token: str = "deployforge-internal"

    # --- Per-app resource limits ---
    # A student's app must not be able to take the machine down.
    app_memory_limit: str = "512m"
    app_cpu_limit: str = "1.0"
    app_pids_limit: int = 256
    # How long to wait for a started container to still be alive.
    app_start_grace_seconds: int = 6

    # --- Quotas ---
    default_max_deployments: int = 3

    # Where compose stacks keep their working copy of the repository. Unlike a
    # single image, a compose stack needs its files at *run* time — the compose
    # file and every build context — so they cannot live in a temp directory
    # that is deleted when the build finishes. Empty = beside the build logs.
    stacks_dir: str = ""

    # --- Misc ---
    # Parent dir for temporary repo downloads. Empty = system temp.
    repo_workdir: str = ""

    @property
    def registry_prefix(self) -> str:
        """Registry host with a trailing separator, or "" when pushing is off."""
        host = self.registry_host.strip().rstrip("/")
        return f"{host}/" if host and self.registry_push else ""

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
