"""
DeployForge API — application entry point.

Creates the FastAPI app, configures CORS for the frontend, registers error
handlers and feature routers, and exposes the /health endpoint used to verify
that the API and database are reachable.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import logging
from contextlib import asynccontextmanager

from app.api import (
    admin_routes,
    auth_routes,
    deployment_routes,
    environment_routes,
    github_routes,
    internal_routes,
    repository_routes,
)
from app.config import settings
from app.core.errors import register_error_handlers
from app.db import AsyncSessionLocal, engine
from app.runtime import docker as docker_runtime
from app.runtime import service as runtime_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Make the world match the database before serving the first request.

    Deployment rows outlive the process that wrote them: Docker Desktop
    restarts, the machine reboots, someone stops a container by hand. Without
    this, the dashboard shows apps as running that are not, and the router is
    handed routes to containers that no longer exist. Neither failure is
    allowed to stop the API from starting.
    """
    try:
        await docker_runtime.ensure_network()
    except Exception:  # noqa: BLE001 — the API is still useful without Docker
        logger.warning("Could not ensure the app network exists", exc_info=True)

    try:
        async with AsyncSessionLocal() as session:
            corrected = await runtime_service.reconcile(session)
            if corrected:
                logger.info("Reconciled %d deployment(s) at startup", corrected)
    except Exception:  # noqa: BLE001 — never block startup on this
        logger.warning("Startup reconciliation failed", exc_info=True)
    finally:
        # Empty the pool before serving. The connections opened above belong to
        # whichever event loop ran startup, which is not always the loop that
        # serves requests; handing one of those to a request handler surfaces as
        # `MissingGreenlet` on the first query and kills the worker. Disposing
        # here costs one reconnect and removes the whole class of problem.
        await engine.dispose()

    yield

    await engine.dispose()

app = FastAPI(
    title="DeployForge API",
    version="0.1.0",
    description=(
        "Connect a GitHub repository, detect how it should be built, build it "
        "into an image, and run it behind a per-app URL."
    ),
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(auth_routes.router)
app.include_router(github_routes.router)
app.include_router(repository_routes.router)
app.include_router(environment_routes.router)
app.include_router(deployment_routes.router)
app.include_router(admin_routes.router)
app.include_router(internal_routes.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """
    Liveness/readiness probe.

    Returns "ok" when the API is up and the database answers, "degraded" when
    the API is up but the database is unreachable. Never raises — the point is
    to report the problem, not to become one.
    """
    database = "ok"
    detail: str | None = None
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any failure, don't crash
        database = "unavailable"
        detail = f"{type(exc).__name__}: {exc}"

    return {
        "status": "ok" if database == "ok" else "degraded",
        "service": "deployforge-api",
        "version": app.version,
        "environment": settings.app_env,
        "database": database,
        "detail": detail,
    }
