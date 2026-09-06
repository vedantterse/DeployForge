"""
Names for the things a deployment creates.

Three names have to be derived from one deployment, and each has different
rules: a DNS label for the URL, a Docker container name, and an image
reference. Deriving them in one place keeps them consistent and keeps the
sanitizing rules out of the calling code.

Everything here is pure and deterministic.
"""

from __future__ import annotations

import re
import uuid

from app.config import settings

# A DNS label: lowercase alphanumerics and hyphens, no leading/trailing hyphen.
_NOT_LABEL = re.compile(r"[^a-z0-9-]+")
_DASHES = re.compile(r"-{2,}")

# Long enough that two students' "todo-app" do not collide, short enough to
# stay readable in a URL.
_SUFFIX_LENGTH = 6
MAX_LABEL_LENGTH = 63  # RFC 1035 limit for a single DNS label


def slugify(value: str, limit: int = 30) -> str:
    """A DNS-safe fragment of `value`, or "app" when nothing survives."""
    slug = _NOT_LABEL.sub("-", value.strip().lower())
    slug = _DASHES.sub("-", slug).strip("-")
    return slug[:limit].strip("-") or "app"


def subdomain_for(
    *,
    repository_id: uuid.UUID,
    repository_name: str,
    deploy_path: str | None = None,
) -> str:
    """
    The host label the app answers on.

    Shape: `<repo>[-<path>]-<id6>`. The suffix comes from the repository — the
    *app* — and not from one build of it, so redeploying keeps the URL the
    student has already shared. Two students may both deploy a repo called
    "todo", and the suffix is what keeps both of their URLs working.
    """
    parts = [slugify(repository_name)]
    if deploy_path:
        parts.append(slugify(deploy_path.replace("/", "-"), 16))
    parts.append(repository_id.hex[:_SUFFIX_LENGTH])

    label = _DASHES.sub("-", "-".join(p for p in parts if p)).strip("-")
    return label[:MAX_LABEL_LENGTH].strip("-")


def container_name_for(deployment_id: uuid.UUID) -> str:
    """
    The Docker container name.

    Keyed on the deployment id alone, not the repo name: it is the handle used
    to stop and remove the container, so it must be stable and unambiguous even
    if the repository is renamed.
    """
    return f"{slugify(settings.container_prefix, 12)}-{deployment_id.hex[:12]}"


def url_for(subdomain: str) -> str:
    """The browser-facing URL for a subdomain."""
    return f"http://{subdomain}.{settings.app_domain}"
