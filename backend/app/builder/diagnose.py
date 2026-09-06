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
