"""
Tests for the detection module.

These build tiny fake repositories in a temp directory and assert the detector
classifies them correctly. Run with:  pytest test_detection.py -v
"""

import json
from pathlib import Path

import pytest

from app.detection.detector import detect_repository, DetectedType


def _write(root: Path, rel: str, content: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# --- Docker cases -----------------------------------------------------------

def test_dockerfile_detected(tmp_path):
    _write(tmp_path, "Dockerfile", "FROM python:3.12\n")
    r = detect_repository(tmp_path)
    assert r.type == DetectedType.DOCKER
    assert r.build_method == "docker"
    assert r.compose is False


def test_compose_detected(tmp_path):
    _write(tmp_path, "docker-compose.yml", "services:\n  web:\n")
    r = detect_repository(tmp_path)
    assert r.type == DetectedType.DOCKER
    assert r.compose is True


def test_docker_takes_precedence_over_framework(tmp_path):
    # Even with a package.json, a Dockerfile wins.
    _write(tmp_path, "Dockerfile", "FROM node:20\n")
    _write(tmp_path, "package.json", json.dumps({"dependencies": {"next": "14"}}))
    r = detect_repository(tmp_path)
    assert r.type == DetectedType.DOCKER


# --- Node framework cases ---------------------------------------------------

def test_nextjs_detected(tmp_path):
    _write(tmp_path, "package.json",
           json.dumps({"dependencies": {"next": "14.0.0", "react": "18"}}))
    r = detect_repository(tmp_path)
    assert r.type == DetectedType.FRAMEWORK
    assert r.framework == "nextjs"
    assert r.build_method == "buildpack"


def test_react_detected_without_next(tmp_path):
    _write(tmp_path, "package.json",
           json.dumps({"dependencies": {"react": "18.0.0"}}))
    r = detect_repository(tmp_path)
    assert r.framework == "react"


def test_express_detected(tmp_path):
    _write(tmp_path, "package.json",
           json.dumps({"dependencies": {"express": "4.18.0"}}))
    r = detect_repository(tmp_path)
    assert r.framework == "express"


# --- Python framework cases -------------------------------------------------

def test_django_via_requirements(tmp_path):
    _write(tmp_path, "requirements.txt", "Django==5.0\ngunicorn\n")
    r = detect_repository(tmp_path)
    assert r.type == DetectedType.FRAMEWORK
    assert r.framework == "django"


def test_django_via_manage_py(tmp_path):
    _write(tmp_path, "manage.py", "# django manage\n")
    r = detect_repository(tmp_path)
    assert r.framework == "django"


def test_fastapi_detected(tmp_path):
    _write(tmp_path, "requirements.txt", "fastapi\nuvicorn\n")
    r = detect_repository(tmp_path)
    assert r.framework == "fastapi"


def test_flask_detected(tmp_path):
    _write(tmp_path, "requirements.txt", "Flask==3.0\n")
    r = detect_repository(tmp_path)
    assert r.framework == "flask"


# --- Other ecosystems -------------------------------------------------------

def test_go_detected(tmp_path):
    _write(tmp_path, "go.mod", "module example.com/app\n")
    r = detect_repository(tmp_path)
    assert r.framework == "go"


# --- Unknown / edge cases ---------------------------------------------------

def test_unknown_repo(tmp_path):
    _write(tmp_path, "README.md", "# just docs\n")
    r = detect_repository(tmp_path)
    assert r.type == DetectedType.UNKNOWN
    assert r.reason  # has an explanation


def test_nonexistent_path_is_unknown(tmp_path):
    r = detect_repository(tmp_path / "does-not-exist")
    assert r.type == DetectedType.UNKNOWN


def test_malformed_package_json_does_not_crash(tmp_path):
    _write(tmp_path, "package.json", "{ this is not valid json ")
    r = detect_repository(tmp_path)
    # Falls back to generic node rather than raising.
    assert r.type == DetectedType.FRAMEWORK
    assert r.framework == "node"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
