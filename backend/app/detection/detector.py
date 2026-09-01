"""
DeployForge — repository detection module.

Pure, dependency-free detection logic. Takes a path to a downloaded repository
and returns a structured DetectionResult describing how it should be deployed.

Design rules (see CLAUDE.md):
  - No FastAPI, no database, no network. Just filesystem reads + parsing.
  - Never executes anything from the repo. Reads and parses files only.
  - Never raises on an unrecognized repo — returns type "unknown" instead.
  - Fully unit-testable: point it at a fixture folder, assert the result.

Usage:
    result = detect_repository("/path/to/cloned/repo")
    # result.type -> "docker" | "framework" | "unknown"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DetectedType(str, Enum):
    DOCKER = "docker"
    FRAMEWORK = "framework"
    UNKNOWN = "unknown"


@dataclass
class DetectionResult:
    """Structured result of analyzing a repository."""
    type: DetectedType
    framework: str | None = None          # set only when type == FRAMEWORK
    compose: bool = False                 # set only when type == DOCKER
    build_method: str | None = None       # "docker" or "buildpack"
    evidence: list[str] = field(default_factory=list)  # which files/keys matched
    reason: str | None = None             # human-readable, esp. for UNKNOWN

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "framework": self.framework,
            "compose": self.compose,
            "build_method": self.build_method,
            "evidence": self.evidence,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Docker detection
# ---------------------------------------------------------------------------

_DOCKERFILE_NAMES = ("Dockerfile", "dockerfile")
_COMPOSE_NAMES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)


def _detect_docker(root: Path) -> DetectionResult | None:
    """Return a DOCKER result if Docker config is present, else None."""
    evidence: list[str] = []

    has_dockerfile = any((root / name).is_file() for name in _DOCKERFILE_NAMES)
    if has_dockerfile:
        evidence.append("Dockerfile")

    compose_present = any((root / name).is_file() for name in _COMPOSE_NAMES)
    if compose_present:
        evidence.append("docker-compose")

    if has_dockerfile or compose_present:
        return DetectionResult(
            type=DetectedType.DOCKER,
            compose=compose_present,
            build_method="docker",
            evidence=evidence,
            reason="Docker configuration found in repository root.",
        )
    return None


# ---------------------------------------------------------------------------
# Framework detection (only runs when no Docker config is present)
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    """Safely read a JSON file; return {} on any problem (never raise)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").lower()
    except Exception:
        return ""


def _detect_node(root: Path) -> DetectionResult | None:
    """Node ecosystem: inspect package.json dependencies to pick the framework."""
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return None

    pkg = _read_json(pkg_path)
    deps = {}
    deps.update(pkg.get("dependencies", {}) or {})
    deps.update(pkg.get("devDependencies", {}) or {})
    dep_names = {name.lower() for name in deps.keys()}

    # Order matters: Next.js also depends on react, so check next first.
    if "next" in dep_names:
        fw = "nextjs"
    elif "express" in dep_names:
        fw = "express"
    elif "react" in dep_names:
        fw = "react"
    elif dep_names:
        fw = "node"  # some other node app
    else:
        fw = "node"

    return DetectionResult(
        type=DetectedType.FRAMEWORK,
        framework=fw,
        build_method="buildpack",
        evidence=["package.json", f"dependency:{fw}"],
        reason=f"Node project detected via package.json (matched {fw}).",
    )


def _detect_python(root: Path) -> DetectionResult | None:
    """Python ecosystem: look at requirements.txt / pyproject for the framework."""
    req = root / "requirements.txt"
    pyproject = root / "pyproject.toml"
    pipfile = root / "Pipfile"

    if not (req.is_file() or pyproject.is_file() or pipfile.is_file()):
        # Django often has manage.py even without requirements
        if not (root / "manage.py").is_file():
            return None

    blob = ""
    for p in (req, pyproject, pipfile):
        if p.is_file():
            blob += _read_text(p)

    manage_py = (root / "manage.py").is_file()

    if "django" in blob or manage_py:
        fw = "django"
    elif "fastapi" in blob:
        fw = "fastapi"
    elif "flask" in blob:
        fw = "flask"
    else:
        fw = "python"

    evidence = [p.name for p in (req, pyproject, pipfile) if p.is_file()]
    if manage_py:
        evidence.append("manage.py")

    return DetectionResult(
        type=DetectedType.FRAMEWORK,
        framework=fw,
        build_method="buildpack",
        evidence=evidence or ["python-markers"],
        reason=f"Python project detected (matched {fw}).",
    )


def _detect_other(root: Path) -> DetectionResult | None:
    """A few more common ecosystems, kept intentionally minimal."""
    checks = [
        ("go.mod", "go"),
        ("pom.xml", "java-maven"),
        ("build.gradle", "java-gradle"),
        ("Gemfile", "ruby"),
        ("composer.json", "php"),
    ]
    for filename, fw in checks:
        if (root / filename).is_file():
            return DetectionResult(
                type=DetectedType.FRAMEWORK,
                framework=fw,
                build_method="buildpack",
                evidence=[filename],
                reason=f"{fw} project detected via {filename}.",
            )
    return None


# Ordered list of framework detectors. First match wins.
_FRAMEWORK_DETECTORS = (_detect_node, _detect_python, _detect_other)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_repository(repo_path: str | Path) -> DetectionResult:
    """
    Analyze a downloaded repository directory.

    Priority:
      1. Docker config present  -> deploy with Docker.
      2. Else identify framework -> deploy with a buildpack.
      3. Else UNKNOWN            -> we can't auto-deploy this yet.

    Never raises on unrecognized input; returns an UNKNOWN result instead.
    """
    root = Path(repo_path)

    if not root.is_dir():
        return DetectionResult(
            type=DetectedType.UNKNOWN,
            reason=f"Path is not a directory: {root}",
        )

    # 1) Docker takes precedence — respect the user's own container setup.
    docker = _detect_docker(root)
    if docker is not None:
        return docker

    # 2) No Docker: try to identify the framework.
    for detector in _FRAMEWORK_DETECTORS:
        result = detector(root)
        if result is not None:
            return result

    # 3) Nothing matched.
    return DetectionResult(
        type=DetectedType.UNKNOWN,
        reason=(
            "No Dockerfile and no recognized framework markers "
            "(package.json, requirements.txt, pyproject.toml, go.mod, etc.)."
        ),
    )


# ---------------------------------------------------------------------------
# Note on monorepos (documented limitation for Phase 1)
# ---------------------------------------------------------------------------
# This module inspects the repository ROOT only. A monorepo with multiple apps
# in subdirectories (e.g. /frontend and /backend each with their own
# package.json) will be detected by whatever markers exist at the root, which
# may be incomplete. For Phase 1 this is an accepted limitation (see CLAUDE.md
# "framework detection is limited to commonly supported technologies"). A future
# enhancement can scan subdirectories and return multiple detected services.
