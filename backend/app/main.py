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

from app.api import (
    admin_routes,
    auth_routes,
    deployment_routes,
    github_routes,
    repository_routes,
)
from app.config import settings
from app.core.errors import register_error_handlers
from app.db import AsyncSessionLocal

app = FastAPI(
    title="DeployForge API",
    version="0.1.0",
    description="Phase 1: auth, GitHub connection, repository download and detection.",
    docs_url="/docs" if settings.is_development else None,
    redoc_url=None,
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
app.include_router(deployment_routes.router)
app.include_router(admin_routes.router)


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
