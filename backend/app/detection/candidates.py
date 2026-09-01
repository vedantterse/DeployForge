"""
Deployable-target discovery for a downloaded repository.

`detector.py` answers "what is *this* directory?" — deliberately root-only, and
left exactly as written. This module answers the question a monorepo raises:
"which directories here could be deployed at all?" It does that by running the
same pure detector against the root and each top-level subdirectory.

It stays pure: filesystem reads only, no FastAPI, no database, no network, and
nothing from the repository is ever executed.

Scanning cannot *decide* for the user — a repo with a Python backend and a
TypeScript frontend has two valid answers, and only the user knows which one
they meant. So this returns candidates; the choice is made in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.detection.detector import DetectedType, DetectionResult, detect_repository

# Directories that are never a deploy target: VCS metadata, editor state,
# dependency and build output. Skipping them keeps the candidate list readable
# and avoids detecting, say, node_modules as a Node app.
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".github",
        ".idea",
        ".vscode",
        ".next",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        "out",
        "target",
        "vendor",
        "coverage",
        ".pytest_cache",
        ".mypy_cache",
    }
)

# A bound on how many subdirectories are inspected, so a repository with a
# thousand top-level folders cannot make one request pathological.
MAX_SUBDIRECTORIES = 50

# The path value meaning "the repository root itself".
ROOT_PATH = ""


@dataclass
class RepositoryCandidate:
    """One directory that could be deployed, and what it looks like."""

    path: str  # "" for the repository root, else a top-level directory name
    result: DetectionResult

    @property
    def is_root(self) -> bool:
        return self.path == ROOT_PATH

    @property
    def is_deployable(self) -> bool:
        """True when the detector recognized something here."""
        return self.result.type is not DetectedType.UNKNOWN

    def to_dict(self) -> dict:
        return {"path": self.path, **self.result.to_dict()}


def scan_candidates(repo_path: str | Path) -> list[RepositoryCandidate]:
    """
    Detect the repository root and each top-level subdirectory.

    The root is always the first entry, even when nothing is found there, so
    the caller can always offer "the whole repository" as a choice. Never
    raises on an odd tree — an unreadable directory is simply skipped.
    """
    root = Path(repo_path)
    candidates = [RepositoryCandidate(ROOT_PATH, detect_repository(root))]

    if not root.is_dir():
        return candidates

    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return candidates

    seen = 0
    for entry in entries:
        if seen >= MAX_SUBDIRECTORIES:
            break
        # Symlinked directories are skipped: following one could lead outside
        # the downloaded tree.
        if entry.is_symlink() or not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name in IGNORED_DIRECTORIES:
            continue
        seen += 1
        candidates.append(RepositoryCandidate(entry.name, detect_repository(entry)))

    return candidates


def deployable_candidates(
    candidates: list[RepositoryCandidate],
) -> list[RepositoryCandidate]:
    """
    The candidates worth showing: the root always, plus recognized subdirectories.

    Unrecognized subdirectories are dropped — offering thirty `unknown` folders
    would bury the real choice.
    """
    return [c for c in candidates if c.is_root or c.is_deployable]


def resolve_path(repo_root: str | Path, deploy_path: str) -> Path:
    """
    Turn a stored `deploy_path` into a real directory under `repo_root`.

    Raises ValueError if the path tries to escape the download, so a tampered
    value can never point detection at the host filesystem.
    """
    root = Path(repo_root).resolve()
    if not deploy_path or deploy_path == ROOT_PATH:
        return root

    candidate = (root / deploy_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"deploy_path escapes the repository: {deploy_path!r}")
    return candidate
