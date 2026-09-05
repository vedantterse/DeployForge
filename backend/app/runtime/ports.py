"""
Deciding which port an app listens on.

The router has to be told where to send traffic, and nothing in a Git
repository reliably states it. This module makes the guess explicit and
ordered, so a wrong answer is a wrong *rule* that can be fixed, rather than a
mystery 502.

Order of confidence:
  1. The image's own EXPOSE — the author said it.
  2. A PORT environment variable the student set — they said it.
  3. The framework's conventional port — the ecosystem says it.
  4. 8080 — buildpack images almost always listen there.
"""

from __future__ import annotations

# What each detected framework listens on by default.
FRAMEWORK_PORTS = {
    "nextjs": 3000,
    "react": 3000,
    "express": 3000,
    "node": 3000,
    "django": 8000,
    "fastapi": 8000,
    "flask": 5000,
    "python": 8000,
    "go": 8080,
    "java-maven": 8080,
    "java-gradle": 8080,
    "ruby": 3000,
    "php": 8080,
}

# Cloud Native Buildpacks set PORT=8080 and their launchers honour it.
BUILDPACK_DEFAULT_PORT = 8080

# Ports that are never the app: a database or cache pulled in as a base image
# may EXPOSE these, and routing HTTP at them produces a confusing failure.
NON_HTTP_PORTS = frozenset({5432, 3306, 6379, 27017, 5672, 9200, 11211})

# Environment variables a student might use to state the port themselves.
PORT_ENV_KEYS = ("PORT", "APP_PORT", "SERVER_PORT", "HTTP_PORT")


def choose_port(
    *,
    exposed_ports: list[int] | None = None,
    env: dict[str, str] | None = None,
    framework: str | None = None,
    build_method: str | None = None,
) -> int:
    """
    The port to route traffic to, and never a nonsense one.

    Every source is filtered through `_valid`, so a malformed PORT or a
    database port inherited from a base image falls through to the next source
    rather than producing an unroutable container.
    """
    for port in exposed_ports or []:
        if _valid(port):
            return port

    for key in PORT_ENV_KEYS:
        raw = (env or {}).get(key)
        if raw is None:
            continue
        try:
            port = int(str(raw).strip())
        except (TypeError, ValueError):
            continue
        if _valid(port):
            return port

    if framework:
        port = FRAMEWORK_PORTS.get(framework.lower())
        if port and _valid(port):
            return port

    if build_method == "buildpack":
        return BUILDPACK_DEFAULT_PORT

    return BUILDPACK_DEFAULT_PORT


def _valid(port: int) -> bool:
    """A plausible HTTP port for a student's app."""
    return 1 <= port <= 65535 and port not in NON_HTTP_PORTS
