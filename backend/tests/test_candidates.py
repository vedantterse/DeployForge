"""
Tests for the pure candidate scanner.

No FastAPI, no database, no network — the same contract detector.py has. These
build small fake monorepos on disk and assert what comes back.
"""

from __future__ import annotations

import json

import pytest

from app.detection.candidates import (
    MAX_SUBDIRECTORIES,
    ROOT_PATH,
    deployable_candidates,
    resolve_path,
    scan_candidates,
)
from app.detection.detector import DetectedType


def _write(root, rel: str, content: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _by_path(candidates) -> dict:
    return {c.path: c for c in candidates}


# --- The monorepo case this exists for -------------------------------------

def test_monorepo_reports_both_halves(tmp_path):
    """The Amvex shape: a Python backend and a TypeScript frontend, no root markers."""
    _write(tmp_path, "README.md", "# amvex\n")
    _write(tmp_path, "backend/requirements.txt", "fastapi\nuvicorn\n")
    _write(tmp_path, "frontend/package.json",
           json.dumps({"dependencies": {"next": "14", "react": "18"}}))

    found = _by_path(scan_candidates(tmp_path))

    assert found[ROOT_PATH].result.type == DetectedType.UNKNOWN
    assert found["backend"].result.framework == "fastapi"
    assert found["backend"].result.build_method == "buildpack"
    assert found["frontend"].result.framework == "nextjs"
    assert found["frontend"].result.build_method == "buildpack"


def test_root_is_always_first_even_when_unknown(tmp_path):
    _write(tmp_path, "frontend/package.json", "{}")
    candidates = scan_candidates(tmp_path)
    assert candidates[0].path == ROOT_PATH
    assert candidates[0].is_root


def test_a_normal_single_app_repo_is_detected_at_the_root(tmp_path):
    _write(tmp_path, "requirements.txt", "Django==5.0\n")
    found = _by_path(scan_candidates(tmp_path))
    assert found[ROOT_PATH].result.framework == "django"


def test_subdirectory_docker_is_reported_as_docker(tmp_path):
    _write(tmp_path, "api/Dockerfile", "FROM python:3.12\n")
    found = _by_path(scan_candidates(tmp_path))
    assert found["api"].result.type == DetectedType.DOCKER
    assert found["api"].result.build_method == "docker"


# --- Noise filtering --------------------------------------------------------

def test_dependency_and_build_directories_are_ignored(tmp_path):
    _write(tmp_path, "node_modules/react/package.json", "{}")
    _write(tmp_path, "dist/package.json", "{}")
    _write(tmp_path, ".venv/pyvenv.cfg", "")
    _write(tmp_path, "app/package.json", json.dumps({"dependencies": {"express": "4"}}))

    paths = {c.path for c in scan_candidates(tmp_path)}
    assert "app" in paths
    assert paths.isdisjoint({"node_modules", "dist", ".venv"})


def test_hidden_directories_are_ignored(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", "on: push\n")
    _write(tmp_path, ".hidden/package.json", "{}")
    paths = {c.path for c in scan_candidates(tmp_path)}
    assert paths.isdisjoint({".github", ".hidden"})


def test_files_at_the_root_are_not_candidates(tmp_path):
    _write(tmp_path, "main.py", "print('hi')\n")
    assert {c.path for c in scan_candidates(tmp_path)} == {ROOT_PATH}


def test_symlinked_directories_are_skipped(tmp_path):
    """Following a symlink could lead outside the downloaded tree."""
    _write(tmp_path, "real/package.json", "{}")
    try:
        (tmp_path / "linked").symlink_to(tmp_path / "real", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        # Windows only allows this to an administrator or with Developer Mode
        # enabled. Without a symlink there is nothing to assert.
        pytest.skip(f"Cannot create a symlink on this system: {exc}")
    assert "linked" not in {c.path for c in scan_candidates(tmp_path)}


def test_subdirectory_count_is_bounded(tmp_path):
    for i in range(MAX_SUBDIRECTORIES + 20):
        _write(tmp_path, f"svc{i:03d}/go.mod", "module x\n")
    # root + at most MAX_SUBDIRECTORIES
    assert len(scan_candidates(tmp_path)) == MAX_SUBDIRECTORIES + 1


# --- Never raises -----------------------------------------------------------

def test_empty_repository_yields_only_an_unknown_root(tmp_path):
    candidates = scan_candidates(tmp_path)
    assert len(candidates) == 1
    assert candidates[0].result.type == DetectedType.UNKNOWN


def test_missing_path_does_not_raise(tmp_path):
    candidates = scan_candidates(tmp_path / "nope")
    assert candidates[0].result.type == DetectedType.UNKNOWN


# --- Filtering for display --------------------------------------------------

def test_deployable_keeps_the_root_and_drops_unknown_subdirectories(tmp_path):
    _write(tmp_path, "docs/index.md", "# docs\n")
    _write(tmp_path, "assets/logo.png", "x")
    _write(tmp_path, "web/package.json", json.dumps({"dependencies": {"react": "18"}}))

    shown = {c.path for c in deployable_candidates(scan_candidates(tmp_path))}
    assert shown == {ROOT_PATH, "web"}


# --- Path resolution --------------------------------------------------------

def test_resolve_path_returns_the_root_for_an_empty_path(tmp_path):
    assert resolve_path(tmp_path, "") == tmp_path.resolve()


def test_resolve_path_returns_the_subdirectory(tmp_path):
    (tmp_path / "backend").mkdir()
    assert resolve_path(tmp_path, "backend") == (tmp_path / "backend").resolve()


@pytest.mark.parametrize("evil", ["..", "../..", "backend/../../etc", "/etc"])
def test_resolve_path_refuses_to_escape_the_repository(tmp_path, evil):
    """A tampered deploy_path must never point detection at the host filesystem."""
    with pytest.raises(ValueError):
        resolve_path(tmp_path, evil)
