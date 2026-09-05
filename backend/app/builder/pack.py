"""
Run a Cloud Native Buildpacks build via the `pack` CLI.

This is where DeployForge stops only *reading* a repository and starts building
it. A buildpack build runs the project's own dependency installation, which can
execute `setup.py`, `postinstall` scripts and other code from the repo — that is
inherent to building anyone's source, not a flaw in buildpacks, but it is a real
change from Phase 1's "nothing is executed" guarantee. Mitigations here: a hard
timeout, the process killed as a group, and secrets kept out of the command line.

Requires `pack` and a reachable Docker daemon on the same host.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.core.errors import AppError

# Docker repository names allow lowercase alphanumerics and . _ - separators;
# tags additionally allow uppercase, up to 128 characters.
_INVALID_NAME_CHARS = re.compile(r"[^a-z0-9._-]+")
_INVALID_TAG_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class BuildToolError(AppError):
    """The build could not be attempted — missing tool, unreachable daemon."""

    code = "build_tool_unavailable"
    status_code = 503


@dataclass
class BuildOutcome:
    """How a build ended. A failed build is a result, not an exception."""

    succeeded: bool
    exit_code: int
    duration_seconds: float
    timed_out: bool = False
    error: str | None = None


def _slug(value: str, limit: int = 40) -> str:
    slug = _INVALID_NAME_CHARS.sub("-", value.strip().lower()).strip("-._")
    return slug[:limit] or "app"


def build_image_ref(
    *,
    user_id,
    repository_name: str,
    deploy_path: str | None,
    commit_sha: str | None,
) -> str:
    """
    A deterministic, valid Docker image reference for a build.

    Shape: `<namespace>/<user-prefix>-<repo>[-<path>]:<commit7|latest>`. The
    user prefix keeps two people's identically-named repositories apart in a
    shared local image store.
    """
    parts = [_slug(str(user_id).split("-")[0], 8), _slug(repository_name)]
    if deploy_path:
        parts.append(_slug(deploy_path.replace("/", "-"), 24))
    name = "-".join(p for p in parts if p)

    tag = _INVALID_TAG_CHARS.sub("-", (commit_sha or "latest")[:7]) or "latest"
    return f"{_slug(settings.image_namespace)}/{name}:{tag}"


def write_env_file(env: dict[str, str], destination: Path) -> Path:
    """
    Write `KEY=VALUE` lines for `pack --env-file`.

    A file rather than repeated `--env` flags: command-line arguments are
    visible to every process on the host via `ps`, and these values include
    secrets. The file is created 0600 and deleted by the caller.

    Values containing newlines are skipped — the env-file format cannot
    represent them, and silently truncating a secret would be worse.
    """
    lines = []
    for key, value in sorted(env.items()):
        if "\n" in value or "\r" in value:
            continue
        lines.append(f"{key}={value}")

    destination.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    destination.chmod(0o600)
    return destination


def preflight() -> None:
    """Fail early, with a fixable message, when the tooling is not usable."""
    if shutil.which(settings.pack_binary) is None:
        raise BuildToolError(
            f"The `{settings.pack_binary}` CLI was not found on the server. "
            "Install Cloud Native Buildpacks (https://buildpacks.io) — version "
            "0.40 or newer is required for Docker 29."
        )
    if shutil.which("docker") is None:
        raise BuildToolError(
            "Docker was not found on the server. A buildpack build needs a "
            "reachable Docker daemon."
        )


# pack older than this uses a Docker API version that Docker 29 rejects with
# "client version 1.38 is too old", which surfaces as a confusing mid-build
# failure. Catching it up front turns that into a fixable message.
MIN_PACK_VERSION = (0, 40)


def _parse_version(output: str) -> tuple[int, ...] | None:
    """Pull `0.40.9` out of `pack version` output like `0.40.9+git-8210eb1`."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    return tuple(int(part) for part in match.groups()) if match else None


async def check_toolchain() -> None:
    """
    Presence *and* usability of the build tooling.

    Called before a build is queued, so a broken toolchain is reported to the
    user immediately instead of failing the deployment a minute later.
    """
    preflight()

    def call() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [settings.pack_binary, "version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )

    try:
        completed = await asyncio.to_thread(call)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BuildToolError(
            f"Could not run `{settings.pack_binary} version`: {exc}"
        ) from exc

    version = _parse_version((completed.stdout or "") + (completed.stderr or ""))
    if version is not None and version < MIN_PACK_VERSION:
        readable = ".".join(str(p) for p in version)
        minimum = ".".join(str(p) for p in MIN_PACK_VERSION)
        raise BuildToolError(
            f"pack {readable} is too old — it uses a Docker API version modern "
            f"daemons reject. Install pack {minimum} or newer from "
            "https://buildpacks.io/docs/install-pack/."
        )


async def docker_available() -> bool:
    """True when the Docker daemon answers."""

    def call() -> int:
        return subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        ).returncode

    try:
        return await asyncio.to_thread(call) == 0
    except (OSError, subprocess.SubprocessError):
        return False


async def run_pack_build(
    *,
    image_ref: str,
    source_path: Path,
    log_path: Path,
    env_file: Path | None = None,
    builder: str | None = None,
    timeout_seconds: int | None = None,
) -> BuildOutcome:
    """
    Build `source_path` into `image_ref`, appending all output to `log_path`.

    Returns a BuildOutcome rather than raising on a failed build: a build that
    fails is an expected result the user needs to see logs for.
    """
    preflight()

    command = [
        settings.pack_binary,
        "build",
        image_ref,
        "--path",
        str(source_path),
        "--builder",
        builder or settings.pack_builder,
        # Reuse a builder already on the host; the first build pulls it.
        "--pull-policy",
        "if-not-present",
    ]
    if settings.pack_run_image.strip():
        command += ["--run-image", settings.pack_run_image.strip()]
    if env_file is not None:
        command += ["--env-file", str(env_file)]

    timeout = timeout_seconds or settings.build_timeout_seconds
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    def call() -> BuildOutcome:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"$ {' '.join(command)}\n\n")
            log.flush()
            try:
                process = subprocess.Popen(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=str(source_path),
                    # Own process group, so a timeout can kill the whole build
                    # tree rather than leaving orphaned children behind.
                    start_new_session=True,
                )
            except OSError as exc:
                message = f"Could not start the build: {exc}"
                log.write(f"\n{message}\n")
                return BuildOutcome(
                    succeeded=False,
                    exit_code=-1,
                    duration_seconds=time.monotonic() - started,
                    error=message,
                )

            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_process_group(process.pid)
                process.wait()
                message = f"Build exceeded the {timeout}s timeout and was stopped."
                log.write(f"\n{message}\n")
                return BuildOutcome(
                    succeeded=False,
                    exit_code=-1,
                    duration_seconds=time.monotonic() - started,
                    timed_out=True,
                    error=message,
                )

        return BuildOutcome(
            succeeded=exit_code == 0,
            exit_code=exit_code,
            duration_seconds=time.monotonic() - started,
            error=None if exit_code == 0 else f"pack exited with code {exit_code}.",
        )

    # On a worker thread rather than an asyncio subprocess: the asyncio
    # subprocess API is unavailable on a Windows Selector loop, which is what a
    # server may well be running on. See `runtime/docker.py`.
    return await asyncio.to_thread(call)


def _kill_process_group(pid: int) -> None:
    """
    Terminate a build and everything it started. Never raises.

    POSIX kills the process group directly. Windows has neither `os.killpg`
    nor `SIGKILL`, so `taskkill /T` is used to walk and kill the process tree
    instead — without this branch a timed-out build raises AttributeError and
    leaves the `pack` process and its children running.
    """
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
        return

    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
