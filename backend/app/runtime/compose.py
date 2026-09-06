"""
Running a repository's own Docker Compose stack.

A compose file describes several services and how they are wired together — a
web app with its database, a queue, a cache. Building "the image" for it is not
a coherent operation, so this module does the thing the file actually asks for:
starts the whole stack, and routes traffic to the one service that serves it.

Docker parses the compose file, not us. `docker compose config --format json`
returns the fully resolved configuration, which means every feature Compose
supports — extends, profiles, variable substitution, multiple files — works
without this module having to understand any of it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from app.config import settings
from app.runtime.docker import CommandResult, _run, _stream

logger = logging.getLogger(__name__)

# Compose file names, in the order Docker itself prefers them.
COMPOSE_FILENAMES = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
)

# Compose loads these automatically alongside the main file, so a port
# removed from one could be put back by the other.
OVERRIDE_FILENAMES = (
    "compose.override.yaml",
    "compose.override.yml",
    "docker-compose.override.yaml",
    "docker-compose.override.yml",
)

# Service names that conventionally mean "this is the one users talk to",
# tried in order when no service publishes a port.
WEB_SERVICE_NAMES = (
    "web", "app", "frontend", "client", "ui", "www",
    "api", "backend", "server",
)

# Images that are plainly infrastructure rather than the thing being deployed.
# A stack whose only published port is Postgres should not be routed to it.
INFRASTRUCTURE_IMAGES = (
    "postgres", "mysql", "mariadb", "mongo", "redis", "memcached",
    "rabbitmq", "elasticsearch", "clickhouse", "minio", "zookeeper", "kafka",
)


def find_compose_file(source: Path) -> Path | None:
    """The compose file in this directory, in Docker's own preference order."""
    for name in COMPOSE_FILENAMES:
        candidate = source / name
        if candidate.is_file():
            return candidate
    return None


def project_name(deployment_id) -> str:
    """
    The compose project name, which namespaces every container it creates.

    Keyed on the deployment id so two students' `docker-compose.yml` files —
    both with a service called `web` — cannot collide.
    """
    return f"{settings.container_prefix}-{str(deployment_id).replace('-', '')[:12]}"


async def resolve_config(compose_file: Path, project: str) -> dict | None:
    """
    Ask Docker to parse and fully resolve the compose file.

    Returns None when the file is invalid — the caller reports that to the
    student rather than attempting to start something Docker cannot read.
    """
    result = await _run(
        "compose",
        "--file", str(compose_file),
        "--project-name", project,
        "config", "--format", "json",
        timeout=60,
    )
    if not result.ok:
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def service_names(config: dict) -> list[str]:
    """Every service the stack defines."""
    return sorted((config.get("services") or {}).keys())


def _is_infrastructure(service: dict) -> bool:
    image = (service.get("image") or "").lower()
    return any(marker in image for marker in INFRASTRUCTURE_IMAGES)


def choose_web_service(config: dict) -> tuple[str | None, int | None]:
    """
    Which service receives traffic, and on which container port.

    In order of confidence:
      1. a non-infrastructure service that publishes a port — publishing a port
         is the author saying "this one is reachable";
      2. a service named like a web service;
      3. the only non-infrastructure service there is.

    Returns (None, None) when the stack has nothing worth routing to, which is
    a legitimate answer for a worker-only stack.
    """
    services: dict[str, dict] = config.get("services") or {}
    if not services:
        return None, None

    app_services = {
        name: svc for name, svc in services.items() if not _is_infrastructure(svc)
    }
    candidates = app_services or services

    # 1. A published port.
    for name, service in candidates.items():
        for published in service.get("ports") or []:
            target = _target_port(published)
            if target:
                return name, target

    # 2. A conventional name.
    for wanted in WEB_SERVICE_NAMES:
        if wanted in candidates:
            return wanted, _exposed_port(candidates[wanted])

    # 3. The only real service.
    if len(candidates) == 1:
        name = next(iter(candidates))
        return name, _exposed_port(candidates[name])

    return None, None


def _target_port(published) -> int | None:
    """
    The *container* port from one `ports:` entry.

    `docker compose config` normalizes these to objects, but a short string
    form can still appear, so both are handled.
    """
    if isinstance(published, dict):
        target = published.get("target")
        try:
            return int(target) if target is not None else None
        except (TypeError, ValueError):
            return None

    if isinstance(published, (str, int)):
        text = str(published).split("/")[0]
        parts = text.split(":")
        try:
            return int(parts[-1])
        except ValueError:
            return None
    return None


def _exposed_port(service: dict) -> int | None:
    """A port from `expose:` when nothing is published."""
    for value in service.get("expose") or []:
        try:
            return int(str(value).split("/")[0])
        except ValueError:
            continue
    return None


def strip_published_ports(stack_dir: Path) -> dict[str, list[int]]:
    """
    Take host port bindings out of the stack's own compose files.

    Every `ports:` entry becomes an `expose:` of the same container port. The
    service stays reachable by name from inside the stack and from the router,
    and stops competing for a port on the machine everyone shares.

    Returns the container ports removed, per service, so the build log can say
    what was changed rather than quietly rewriting someone's file.

    Operates on the stack's working copy, never on anything the student can
    see, and leaves a file it cannot parse alone: Compose has already accepted
    it, so a parse failure here means this function is wrong, not the file, and
    breaking a working deployment over it would be the worse outcome.
    """
    removed: dict[str, list[int]] = {}

    for name in (*COMPOSE_FILENAMES, *OVERRIDE_FILENAMES):
        path = stack_dir / name
        if not path.is_file():
            continue
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Leaving %s alone, could not parse it: %s", name, exc)
            continue
        if not isinstance(document, dict):
            continue

        services = document.get("services")
        if not isinstance(services, dict):
            continue

        changed = False
        for service_name, service in services.items():
            if not isinstance(service, dict) or not service.get("ports"):
                continue

            targets = [
                target
                for target in (_target_port(p) for p in service["ports"])
                if target is not None
            ]
            del service["ports"]
            changed = True

            # Keep the port reachable inside the stack, just not on the host.
            exposed = [str(v) for v in service.get("expose") or []]
            for target in targets:
                if str(target) not in exposed:
                    exposed.append(str(target))
            if exposed:
                service["expose"] = exposed

            removed.setdefault(service_name, []).extend(targets)

        if changed:
            path.write_text(
                yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
            )

    return removed


def container_name_for(project: str, service: str) -> str:
    """
    The container Compose creates for a service.

    Compose v2 names containers `<project>-<service>-<index>`; the first
    replica is always index 1, and DeployForge never scales a service beyond
    one, so this is exact rather than a guess.
    """
    return f"{project}-{service}-1"


async def up(
    *,
    compose_file: Path,
    project: str,
    log_path: Path,
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
) -> CommandResult:
    """
    Build and start the whole stack, streaming output into the build log.

    `--build` because a compose file that builds from source must not silently
    run a stale image from a previous deploy.
    """
    command = [
        settings.docker_binary,
        "compose",
        "--file", str(compose_file),
        "--project-name", project,
        "up", "--detach", "--build", "--remove-orphans",
    ]
    return await _stream(
        command, log_path, timeout_seconds or settings.build_timeout_seconds
    )


async def down(project: str, *, remove_volumes: bool = False) -> CommandResult:
    """
    Stop and remove the stack.

    Volumes are kept by default: they hold the database a student has been
    filling in, and losing that to a restart would be its own bug.
    """
    args = ["compose", "--project-name", project, "down", "--remove-orphans"]
    if remove_volumes:
        args.append("--volumes")
    return await _run(*args, timeout=180)


async def running_services(project: str) -> list[str]:
    """The services currently up, by container name."""
    result = await _run(
        "compose", "--project-name", project, "ps",
        "--format", "json", "--status", "running",
        timeout=60,
    )
    if not result.ok:
        return []

    names: list[str] = []
    # `compose ps --format json` emits one JSON object per line.
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, list):
            names.extend(e.get("Name", "") for e in entry if isinstance(e, dict))
        elif isinstance(entry, dict):
            names.append(entry.get("Name", ""))
    return [n for n in names if n]


async def attach_to_edge(container: str) -> CommandResult:
    """
    Put the routed container on the shared network so the router can reach it.

    Compose creates a private network per project, which is what keeps one
    student's database away from another's. The web service needs a second
    connection — to the edge network — and only the web service gets one.
    """
    return await _run("network", "connect", settings.edge_network, container)


async def logs(project: str, *, tail: int = 500) -> str:
    """Combined output from every service in the stack."""
    result = await _run(
        "compose", "--project-name", project, "logs", "--tail", str(tail),
        timeout=60,
    )
    return result.stdout + result.stderr


def stack_dir_for(deployment_id) -> Path:
    """
    Where a compose stack's working copy of the repository lives.

    A single-image build can throw its source away the moment the image exists.
    A compose stack cannot: `docker compose up` re-reads the compose file and
    every build context, so the files have to outlive the build.
    """
    import tempfile

    base = (
        settings.stacks_dir.strip()
        or settings.build_log_dir.strip()
        or settings.repo_workdir.strip()
        or tempfile.gettempdir()
    )
    directory = Path(base) / "deployforge-stacks" / str(deployment_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def replace_stack_dir(deployment_id, source: Path) -> Path:
    """
    Copy a freshly downloaded repository into the stack directory.

    Replaces whatever was there: a redeploy must not merge new files into an
    old tree, leaving deleted files behind to be picked up by the build.
    """
    import shutil

    destination = stack_dir_for(deployment_id)
    shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(source, destination)
    return destination


def remove_stack_dir(deployment_id) -> None:
    """Delete a stack's working copy. Never raises."""
    import shutil

    shutil.rmtree(stack_dir_for(deployment_id), ignore_errors=True)
