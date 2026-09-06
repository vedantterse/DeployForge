"""
Turn a failed build log into something a student can act on.

A build that fails prints hundreds of lines and ends with `exit status 1`. The
line that matters is usually one of a small number of known failures, and it is
rarely near the end. Recording "pack exited with code 1" on the deployment and
leaving the student to find it is how a platform meant to lower the barrier
raises it instead.

This is deliberately a lookup table, not a parser. Each entry pairs a signature
that appears in real build output with a plain explanation and the fix. When
nothing matches, the caller keeps the original message — a wrong guess would be
worse than none.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnosis:
    """A recognized build failure and what to do about it."""

    #: Short label for the cause, e.g. "Turbopack cannot run under buildpacks".
    summary: str
    #: What the student should change, in one or two sentences.
    fix: str

    def message(self) -> str:
        return f"{self.summary} {self.fix}"


# Ordered most specific first: the first signature to match wins, so a narrow
# cause is never masked by a broad one.
_SIGNATURES: list[tuple[re.Pattern[str], Diagnosis]] = [
    (
        re.compile(r"Symlink node_modules is invalid", re.I),
        Diagnosis(
            summary=(
                "Next.js could not build with Turbopack under buildpacks: "
                "dependencies are installed outside the project directory and "
                "linked in, which Turbopack refuses to follow."
            ),
            fix=(
                'Change the build script in package.json from "next build '
                '--turbopack" to "next build" and deploy again. The standard '
                "compiler handles this correctly. Adding a Dockerfile also "
                "avoids it entirely."
            ),
        ),
    ),
    (
        re.compile(r"could not find app in /workspace: expected one of", re.I),
        Diagnosis(
            summary=(
                "The buildpack could not find a file to start your app with."
            ),
            fix=(
                'Add a "start" script to package.json (for example "next '
                'start" or "node server.js"), or name your entry point '
                "server.js, app.js, main.js or index.js."
            ),
        ),
    ),
    (
        re.compile(r"libatomic\.so\.1|error while loading shared libraries", re.I),
        Diagnosis(
            summary=(
                "The app was built against a Node version whose binaries the "
                "run image does not support."
            ),
            fix=(
                'Pin a supported version in package.json — "engines": '
                '{"node": "22.x"} — and deploy again.'
            ),
        ),
    ),
    (
        re.compile(r"No buildpack groups passed detection", re.I),
        Diagnosis(
            summary="No buildpack recognized this project.",
            fix=(
                "Buildpacks need a manifest they understand — package.json, "
                "requirements.txt, pyproject.toml, go.mod and similar. Add a "
                "Dockerfile if your project does not have one."
            ),
        ),
    ),
    (
        re.compile(r"npm ERR!.*(ERESOLVE|peer dep)", re.I | re.S),
        Diagnosis(
            summary="npm could not resolve your dependency tree.",
            fix=(
                "The conflict is in the build log above. Fix the versions in "
                "package.json, or commit a package-lock.json that installs "
                "cleanly with `npm ci`."
            ),
        ),
    ),
    (
        re.compile(r"npm ERR!.*(ENOENT|Missing script)", re.I | re.S),
        Diagnosis(
            summary="An npm script the build expected does not exist.",
            fix=(
                "Check the scripts block in package.json — the build ran a "
                "script name that is not defined there."
            ),
        ),
    ),
    (
        re.compile(r"Cannot find module ['\"]", re.I),
        Diagnosis(
            summary="The build failed on a module that is not installed.",
            fix=(
                "The missing module is named in the log above. Add it to "
                "dependencies in package.json — a package listed only in "
                "devDependencies is not installed for a production build."
            ),
        ),
    ),
    (
        re.compile(r"ModuleNotFoundError: No module named", re.I),
        Diagnosis(
            summary="A Python import failed because the package is not declared.",
            fix=(
                "Add the missing package to requirements.txt (or pyproject.toml) "
                "and deploy again."
            ),
        ),
    ),
    (
        re.compile(r"(?:^|\n)\s*(?:ERROR|error):?\s*failed to fetch|manifest unknown|pull access denied", re.I),
        Diagnosis(
            summary="A base image in your Dockerfile could not be pulled.",
            fix=(
                "Check the image name and tag in your FROM line. A private "
                "image cannot be pulled here."
            ),
        ),
    ),
    (
        re.compile(r"returned a non-zero code|did not complete successfully", re.I),
        Diagnosis(
            summary="A command in your Dockerfile exited with an error.",
            fix=(
                "The failing RUN step and its output are in the log above; fix "
                "that command and deploy again."
            ),
        ),
    ),
    (
        re.compile(r"no space left on device", re.I),
        Diagnosis(
            summary="The build ran out of disk space on the server.",
            fix="Tell an administrator — this one is not something you can fix.",
        ),
    ),
]

# Why a container that was built successfully will not stay up.
#
# Kept apart from the build signatures because the two answer different
# questions and a build cause would be a confusing thing to show for a crash
# on boot. Ordered most specific first, same as above.
_RUNTIME_SIGNATURES: list[tuple[re.Pattern[str], Diagnosis]] = [
    (
        re.compile(r"querySrv\s+ENOTFOUND\s+_mongodb\._tcp\.(\S+)", re.I),
        Diagnosis(
            summary=(
                "Your app could not find its MongoDB cluster: the address in "
                "the connection string does not exist in DNS."
            ),
            fix=(
                "The cluster was most likely deleted or renamed — a paused "
                "Atlas cluster still resolves, a deleted one does not. Check "
                "it in Atlas, then set the current connection string as an "
                "environment variable on this app rather than committing it."
            ),
        ),
    ),
    (
        re.compile(r"(ENOTFOUND|EAI_AGAIN|Name or service not known|"
                   r"getaddrinfo failed|nodename nor servname)", re.I),
        Diagnosis(
            summary="Your app could not resolve a hostname it tried to connect to.",
            fix=(
                "Usually a database or API address that is wrong, or one that "
                "only exists on your own machine — `localhost` inside a "
                "container means the container itself, not your laptop. "
                "Services in the same stack reach each other by service name."
            ),
        ),
    ),
    (
        re.compile(r"(ECONNREFUSED|Connection refused|could not connect to server)", re.I),
        Diagnosis(
            summary="Your app reached the address it wanted, but nothing was listening.",
            fix=(
                "If the database is part of this stack, it may still be "
                "starting — use `depends_on` so your app waits for it. If it "
                "is elsewhere, check the port and that it accepts connections "
                "from outside its own host."
            ),
        ),
    ),
    (
        re.compile(r"(bad auth|Authentication failed|authentication failed|"
                   r"password authentication failed|SASL)", re.I),
        Diagnosis(
            summary="The database rejected your app's username or password.",
            fix=(
                "Check the credentials in the connection string. A password "
                "containing @ : / or ? must be percent-encoded, which is the "
                "usual cause when the same string works elsewhere."
            ),
        ),
    ),
    (
        re.compile(r"EADDRINUSE|address already in use", re.I),
        Diagnosis(
            summary="Your app tried to listen on a port already taken inside its container.",
            fix=(
                "Usually two processes started from one command. Listen on "
                "the port in the PORT environment variable, which DeployForge "
                "sets, instead of a fixed number."
            ),
        ),
    ),
    (
        re.compile(r"(Cannot find module|ModuleNotFoundError|ImportError: No module)", re.I),
        Diagnosis(
            summary="The app started and immediately could not find code it needs.",
            fix=(
                "A dependency is missing from package.json or requirements.txt, "
                "or the start command points at a file that is not in the "
                "built image. Building locally with the same Dockerfile "
                "reproduces this."
            ),
        ),
    ),
    (
        re.compile(r"(exec .*: not found|no such file or directory.*sh|"
                   r"executable file not found)", re.I),
        Diagnosis(
            summary="The container's start command does not exist in the image.",
            fix=(
                "Check the CMD or ENTRYPOINT in your Dockerfile, or the "
                "`start` script the buildpack runs. A command that works "
                "locally may not be installed in the image."
            ),
        ),
    ),
]

# Only the tail of a long log is scanned by default: a signature from a
# previous, unrelated step is not this build's failure.
_TAIL_CHARS = 20_000


def diagnose(log_text: str) -> Diagnosis | None:
    """
    Recognize a known build failure in the log, or return None.

    None is the honest answer for anything unrecognized — the caller keeps the
    original tool message rather than showing a confident wrong explanation.
    """
    if not log_text:
        return None

    window = log_text[-_TAIL_CHARS:]
    for pattern, diagnosis in _SIGNATURES:
        if pattern.search(window):
            return diagnosis
    return None


def explain(log_text: str, fallback: str) -> str:
    """
    The message to record on a failed deployment.

    The recognized cause comes first because it is what the student needs; the
    raw tool error is appended so the underlying failure is never hidden.
    """
    found = diagnose(log_text)
    if found is None:
        return fallback
    return f"{found.message()} ({fallback})"


def diagnose_runtime(log_text: str) -> Diagnosis | None:
    """Recognize why a container died on boot, or return None."""
    if not log_text:
        return None

    window = log_text[-_TAIL_CHARS:]
    for pattern, diagnosis in _RUNTIME_SIGNATURES:
        if pattern.search(window):
            return diagnosis
    return None


def explain_exit(log_text: str, exit_code: int | None) -> str:
    """
    Why the app will not stay up, for the student to read on the deployment.

    The exit code is included only when there is one. A container whose state
    could not be read has no code, and "exit code None" is worse than not
    mentioning it — it reads like the app returned something called None.
    """
    detail = (
        f"The container exited immediately (exit code {exit_code})."
        if exit_code is not None
        else "The container started and then exited immediately."
    )
    found = diagnose_runtime(log_text)
    if found is None:
        return f"{detail} Check the runtime log for what the app printed as it died."
    return f"{found.message()} ({detail})"


def read_tail(path, limit: int = _TAIL_CHARS) -> str:
    """The last `limit` characters of a build log. Never raises."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - limit))
            return handle.read()
    except OSError:
        return ""
