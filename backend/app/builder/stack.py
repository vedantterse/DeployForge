"""
Running several directories of one repository together.

A repository with `frontend/` and `backend/` is not two apps. The frontend is
useless without the backend it calls, and deploying them separately gives two
URLs, two lifecycles, and no way for one to reach the other. So a multi-service
target is a single deployment: each directory is built on its own — Dockerfile
or buildpacks, whichever suits it — and the resulting images are run together
as one stack on one private network.

The stack is expressed as a Compose file referencing the built images. That is
deliberate: Compose already gives a private network, ordered start-up, combined
logs and clean teardown, and `runtime/compose.py` already knows how to drive
it. Writing a second orchestrator to do the same thing worse would be the
mistake here.

Nothing in this module talks to Docker or the database; it decides names,
ports and wiring, and hands back text.
"""

from __future__ import annotations

import json
import re

# A service name has to be a valid DNS label, because the other services reach
# it by that name over Docker's embedded DNS.
_NOT_LABEL = re.compile(r"[^a-z0-9-]+")

# Directory names that mean "this is the one users open in a browser", most
# specific first. Used when nothing else distinguishes the services.
_WEB_NAMES = (
    "frontend", "web", "client", "ui", "www", "site", "app", "dashboard",
)

# Every service listens here inside its own container. They are separate
# containers, so sharing a port number costs nothing and means the wiring is
# predictable rather than discovered.
DEFAULT_PORT = 8080

# An environment variable naming rule: `backend/` becomes BACKEND_URL.
_ENV_SAFE = re.compile(r"[^A-Z0-9]+")


def service_name(path: str) -> str:
    """
    The service name for a directory.

    The repository root is "app" — Compose needs a name, and "" is not one.
    """
    slug = _NOT_LABEL.sub("-", (path or "app").lower()).strip("-")
    return slug or "app"


def choose_web_service(names: list[str]) -> str:
    """
    Which service receives public traffic.

    A conventional frontend name wins; otherwise the first service, which is
    the order the user picked them in. Returning something is always better
    than refusing — the user can see which one was chosen and reorder.
    """
    for wanted in _WEB_NAMES:
        if wanted in names:
            return wanted
    return names[0]


def env_var_for(name: str) -> str:
    """`backend` -> `BACKEND_URL`."""
    return f"{_ENV_SAFE.sub('_', name.upper()).strip('_') or 'APP'}_URL"


def service_urls(names: list[str], port: int = DEFAULT_PORT) -> dict[str, str]:
    """
    The address of every service, keyed by the variable that carries it.

    This is what makes the stack useful rather than merely co-located: the
    frontend is handed `BACKEND_URL=http://backend:8080` without the student
    hardcoding a hostname they could not have known.
    """
    return {env_var_for(name): f"http://{name}:{port}" for name in names}


def compose_file(
    *,
    services: dict[str, str],
    env: dict[str, str] | None = None,
    port: int = DEFAULT_PORT,
) -> str:
    """
    A Compose file running pre-built images together.

    `services` maps service name to image reference. Every service is given the
    address of every other service and PORT — so a buildpack launcher and a
    framework reading `process.env.PORT` both land on the same number the
    router expects.

    The student's own environment is applied *last* and therefore wins. Someone
    who sets `BACKEND_URL` to an external API has already decided; silently
    replacing it with an internal address would break their app for a reason
    they could not see. Filling a gap is help, overruling a choice is not.

    Emitted as JSON, which is valid YAML: Compose accepts it, and it removes a
    whole class of quoting and indentation bugs that hand-built YAML invites.
    """
    names = list(services)
    wiring = service_urls(names, port)

    definition = {
        "services": {
            name: {
                "image": image,
                "restart": "unless-stopped",
                "environment": {
                    "PORT": str(port),
                    **wiring,
                    # Last, so an explicit choice is never overruled.
                    **(env or {}),
                },
                "expose": [str(port)],
            }
            for name, image in services.items()
        }
    }
    return json.dumps(definition, indent=2, sort_keys=True)
