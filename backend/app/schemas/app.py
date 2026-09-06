"""
API shapes for apps.

An *app* is a repository target a student has connected — one repository, or
one directory inside it, or several directories that run together. A
*deployment* is one attempt to build and run that app.

The distinction matters to the person using it: they have four apps, not
eleven deployments. Redeploying does not give them a new app, and a failed
build does not take an app away. So the list they see is a list of apps, and
each app carries the one deployment that is current plus a count of the rest.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.repository import DetectedType
from app.schemas.deployment import DeploymentOut


class AppOut(BaseModel):
    """One app, with whichever of its deployments is current."""

    id: uuid.UUID
    name: str
    full_name: str
    target_label: str
    deploy_path: str | None = None
    service_paths: list[str] | None = None
    is_multi_service: bool = False
    detected_type: DetectedType | None = None
    detected_framework: str | None = None
    created_at: datetime
    updated_at: datetime

    # The deployment the app's URL points at: the running one, or the most
    # recent attempt when nothing is up. None only for an app connected but
    # never built.
    current: DeploymentOut | None = None
    deployment_count: int = 0
    # When this app last had a successful build, for "deployed 2 days ago".
    last_deployed_at: datetime | None = None


class AppDetailOut(AppOut):
    """An app together with its full deployment history, newest first."""

    deployments: list[DeploymentOut] = []
