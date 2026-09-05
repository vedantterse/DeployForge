"""
A thin async wrapper over the `docker` CLI.

The CLI rather than a Docker SDK, for the same reason the rest of the platform
shells out to `pack`: one dependency fewer, and the exact command that ran can
be printed into a build log the student reads. Every call goes through `_run`,
so timeouts, argument handling and error shaping stay uniform.

Nothing here interpolates user input into a shell string — commands are passed
as argument lists, so a repository named `; rm -rf /` is just an odd name.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.core.errors import AppError

# Docker operations here are local; anything slower is a stuck daemon.
DEFAULT_TIMEOUT = 120.0


class DockerError(AppError):
    """A docker command failed, or the daemon is unreachable."""

    code = "docker_error"
    status_code = 503


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def message(self) -> str:
        """The most useful single line to show a human."""
        text = (self.stderr or self.stdout).strip()
        return text.splitlines()[-1] if text else f"exit code {self.exit_code}"


async def _run(*args: str, timeout: float = DEFAULT_TIMEOUT) -> CommandResult:
    """
    Run `docker <args>` and capture its output. Never raises on failure.

    Blocking `subprocess` on a worker thread, deliberately, rather than
    `asyncio.create_subprocess_exec`: on Windows the asyncio subprocess API
    raises NotImplementedError unless the loop is a Proactor loop, and a server
    does not get to choose the loop its host picked. Running the process in a
    thread works under every event loop on every platform.
    """
    if shutil.which(settings.docker_binary) is None:
        raise DockerError(
            f"The `{settings.docker_binary}` CLI was not found on the server."
        )

    def call() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [settings.docker_binary, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    try:
        completed = await asyncio.to_thread(call)
    except subprocess.TimeoutExpired as exc:
        raise DockerError(
            f"`docker {args[0]}` did not finish within {timeout:.0f}s."
        ) from exc
    except OSError as exc:
        raise DockerError(f"Could not run docker: {exc}") from exc

    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


async def daemon_available() -> bool:
    """True when the Docker daemon answers."""
    try:
        result = await _run("info", "--format", "{{.ServerVersion}}", timeout=20)
    except DockerError:
        return False
    return result.ok


async def ensure_network(name: str | None = None) -> None:
    """
    Create the app network if it does not exist.

    Idempotent: a concurrent create losing the race is not an error, so an
    "already exists" failure is treated as success.
    """
    network = name or settings.edge_network
    existing = await _run("network", "inspect", network, "--format", "{{.Name}}")
    if existing.ok:
        return

    created = await _run(
        "network", "create", network, "--label", "deployforge.infra=true"
    )
    if not created.ok and "already exists" not in created.stderr.lower():
        raise DockerError(f"Could not create the {network} network: {created.message}")


async def inspect(name: str) -> dict | None:
    """Full `docker inspect` output for a container or image, or None."""
    result = await _run("inspect", name)
    if not result.ok:
        return None
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return None
    return payload[0] if payload else None


async def container_state(name: str) -> dict | None:
    """
    The `.State` of a container: running, exit code, when it started.

    None means no such container, which is a normal answer — a deployment that
    was never started has no container.
    """
    data = await inspect(name)
    return data.get("State") if data else None


async def image_exposed_ports(image_ref: str) -> list[int]:
    """
    TCP ports the image declares with EXPOSE, lowest first.

    This is the only trustworthy statement an image makes about where it
    listens; everything else is a guess.
    """
    data = await inspect(image_ref)
    if not data:
        return []
    exposed = (data.get("Config") or {}).get("ExposedPorts") or {}
    ports: list[int] = []
    for key in exposed:
        port, _, proto = key.partition("/")
        if proto and proto != "tcp":
            continue
        try:
            ports.append(int(port))
        except ValueError:
            continue
    return sorted(ports)


async def run_container(
    *,
    name: str,
    image_ref: str,
    port: int,
    env: dict[str, str] | None = None,
    network: str | None = None,
    labels: dict[str, str] | None = None,
) -> CommandResult:
    """
    Start an app container, detached, on the app network.

    Deliberately *not* published to a host port: the container is reachable
    only from inside the network, so the router is the single front door and
    two students' apps can both listen on 3000 without colliding.
    """
    command = [
        "run",
        "--detach",
        "--name",
        name,
        "--network",
        network or settings.edge_network,
        "--restart",
        "unless-stopped",
        # Resource caps: one runaway app must not take the machine down for
        # the rest of the class.
        "--memory",
        settings.app_memory_limit,
        "--cpus",
        settings.app_cpu_limit,
        "--pids-limit",
        str(settings.app_pids_limit),
        # Nothing a web app needs requires gaining privileges.
        "--security-opt",
        "no-new-privileges",
        "--label",
        "deployforge.managed=true",
        "--expose",
        str(port),
    ]
    for key, value in (labels or {}).items():
        command += ["--label", f"{key}={value}"]
    for key, value in (env or {}).items():
        # A newline would let one value forge a second variable.
        if "\n" in value or "\r" in value:
            continue
        command += ["--env", f"{key}={value}"]

    command.append(image_ref)
    return await _run(*command, timeout=180)


async def stop_container(name: str, *, timeout_seconds: int = 10) -> CommandResult:
    """Stop a container, giving it a chance to shut down cleanly first."""
    return await _run(
        "stop", "--time", str(timeout_seconds), name, timeout=timeout_seconds + 30
    )


async def remove_container(name: str, *, force: bool = True) -> CommandResult:
    """Remove a container. Absence is success — the goal is that it is gone."""
    args = ["rm"]
    if force:
        args.append("--force")
    args.append(name)
    return await _run(*args)


async def start_container(name: str) -> CommandResult:
    """Start an existing, stopped container."""
    return await _run("start", name)


async def container_logs(name: str, *, tail: int = 500) -> str:
    """
    Recent stdout and stderr from a container, in the order Docker holds them.

    Both streams together is what a student needs when their app crashed on
    boot and the reason went to stderr.
    """
    result = await _run("logs", "--tail", str(tail), name, timeout=30)
    return result.stdout + result.stderr


async def build_image(
    *,
    image_ref: str,
    context_path: Path,
    dockerfile: Path | None = None,
    log_path: Path | None = None,
    timeout_seconds: int | None = None,
) -> CommandResult:
    """Build an image from a Dockerfile, appending output to `log_path`."""
    command = [
        settings.docker_binary,
        "build",
        "--tag",
        image_ref,
        "--label",
        "deployforge.managed=true",
    ]
    if dockerfile is not None:
        command += ["--file", str(dockerfile)]
    command.append(str(context_path))

    timeout = timeout_seconds or settings.build_timeout_seconds
    return await _stream(command, log_path, timeout)


async def push_image(
    image_ref: str,
    *,
    log_path: Path | None = None,
    timeout_seconds: int = 600,
) -> CommandResult:
    """Push an image to the registry, streaming progress into the build log."""
    return await _stream(
        [settings.docker_binary, "push", image_ref], log_path, timeout_seconds
    )


async def tag_image(source: str, target: str) -> CommandResult:
    return await _run("tag", source, target)


async def remove_image(image_ref: str) -> CommandResult:
    """Delete a local image. Failure is tolerated — it may still be in use."""
    return await _run("image", "rm", "--force", image_ref)


async def _stream(
    command: list[str], log_path: Path | None, timeout: float
) -> CommandResult:
    """
    Run a long command with its output appended to a log file.

    Output goes straight to the file descriptor rather than through a pipe, so
    a very chatty build cannot fill memory, and the student sees progress while
    it is still running.
    """
    if log_path is None:
        return await _run(*command[1:], timeout=timeout)

    log_path.parent.mkdir(parents=True, exist_ok=True)

    def call() -> CommandResult:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"$ {' '.join(command)}\n\n")
            log.flush()
            try:
                process = subprocess.Popen(
                    command, stdout=log, stderr=subprocess.STDOUT
                )
            except OSError as exc:
                log.write(f"\nCould not start: {exc}\n")
                return CommandResult(exit_code=-1, stdout="", stderr=str(exc))

            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                message = f"Timed out after {timeout:.0f}s."
                log.write(f"\n{message}\n")
                return CommandResult(exit_code=-1, stdout="", stderr=message)

        return CommandResult(exit_code=exit_code, stdout="", stderr="")

    # Same reasoning as `_run`: a thread, not an asyncio subprocess, so this
    # works whichever event loop the server is running on.
    return await asyncio.to_thread(call)
