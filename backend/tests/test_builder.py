"""
Tests for image building.

`pack` and Docker are never actually invoked: the subprocess is replaced with a
trivial command, and the orchestration is driven with the download and the pack
call stubbed. What is exercised for real: image naming, env-file handling,
timeout behaviour, status transitions, and who is allowed to start a build.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

import pytest

from app.api import repository_routes
from app.builder import pack
from app.builder import service as build_service
from app.builder.pack import BuildOutcome, BuildToolError, build_image_ref, write_env_file
from app.config import settings
from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.repository import DetectedType, Repository

USER_ID = uuid.UUID("a1b2c3d4-0000-0000-0000-000000000000")


# --- Image naming -----------------------------------------------------------

def test_image_ref_includes_user_repo_path_and_commit():
    ref = build_image_ref(
        user_id=USER_ID, repository_name="Amvex", deploy_path="backend",
        commit_sha="3bb876b1c2d3e4",
    )
    assert ref == "deployforge/a1b2c3d4-amvex-backend:3bb876b"


def test_image_ref_omits_the_path_for_a_root_target():
    ref = build_image_ref(
        user_id=USER_ID, repository_name="hello-world", deploy_path=None,
        commit_sha="abcdef1234",
    )
    assert ref == "deployforge/a1b2c3d4-hello-world:abcdef1"


def test_image_ref_sanitizes_characters_docker_rejects():
    """Uppercase and punctuation would make an invalid repository name."""
    ref = build_image_ref(
        user_id=USER_ID, repository_name="My Weird/Repo!", deploy_path="src/api",
        commit_sha=None,
    )
    name, tag = ref.split(":")
    assert name.islower()
    assert all(c.isalnum() or c in "./_-" for c in name)
    assert tag == "latest"  # no commit known


def test_image_ref_is_deterministic():
    args = dict(user_id=USER_ID, repository_name="app", deploy_path=None, commit_sha="a" * 40)
    assert build_image_ref(**args) == build_image_ref(**args)


def test_two_users_get_different_images_for_the_same_repo():
    a = build_image_ref(user_id=uuid.uuid4(), repository_name="app", deploy_path=None, commit_sha="a")
    b = build_image_ref(user_id=uuid.uuid4(), repository_name="app", deploy_path=None, commit_sha="a")
    assert a != b


# --- Env file ---------------------------------------------------------------

def test_env_file_is_written_as_key_value_lines(tmp_path):
    path = write_env_file({"B": "2", "A": "1"}, tmp_path / "build.env")
    assert path.read_text().splitlines() == ["A=1", "B=2"]  # sorted, stable


def test_env_file_is_not_world_readable(tmp_path):
    """It holds secrets, so it must not be readable by other users."""
    path = write_env_file({"SECRET": "s3cret"}, tmp_path / "build.env")
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_env_file_skips_multiline_values(tmp_path):
    """The format cannot represent them; truncating a secret would be worse."""
    path = write_env_file({"OK": "fine", "KEY": "line1\nline2"}, tmp_path / "build.env")
    assert path.read_text() == "OK=fine\n"


def test_empty_env_file_is_valid(tmp_path):
    path = write_env_file({}, tmp_path / "build.env")
    assert path.read_text() == ""


# --- Preflight --------------------------------------------------------------

def test_preflight_reports_a_missing_pack_binary(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(BuildToolError, match="buildpacks.io"):
        pack.preflight()


def test_preflight_reports_a_missing_docker(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "docker" else "/usr/bin/pack")
    with pytest.raises(BuildToolError, match="Docker"):
        pack.preflight()


def test_preflight_passes_when_both_are_present(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    pack.preflight()  # does not raise


# --- Running the build subprocess ------------------------------------------

@pytest.mark.asyncio
async def test_a_successful_build_reports_success(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, "preflight", lambda: None)
    monkeypatch.setattr(settings, "pack_binary", "/bin/true")

    outcome = await pack.run_pack_build(
        image_ref="x/y:z", source_path=tmp_path, log_path=tmp_path / "build.log"
    )
    assert outcome.succeeded is True
    assert outcome.exit_code == 0


@pytest.mark.asyncio
async def test_a_failing_build_reports_the_exit_code(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, "preflight", lambda: None)
    monkeypatch.setattr(settings, "pack_binary", "/bin/false")

    outcome = await pack.run_pack_build(
        image_ref="x/y:z", source_path=tmp_path, log_path=tmp_path / "build.log"
    )
    assert outcome.succeeded is False
    assert outcome.exit_code == 1
    assert "exited with code 1" in outcome.error


@pytest.mark.asyncio
async def test_the_command_is_recorded_in_the_log(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, "preflight", lambda: None)
    monkeypatch.setattr(settings, "pack_binary", "/bin/true")
    monkeypatch.setattr(settings, "pack_builder", "paketobuildpacks/builder-jammy-base")

    log = tmp_path / "build.log"
    await pack.run_pack_build(image_ref="x/y:z", source_path=tmp_path, log_path=log)

    text = log.read_text()
    assert "build" in text and "x/y:z" in text
    assert "paketobuildpacks/builder-jammy-base" in text


@pytest.mark.asyncio
async def test_a_build_that_hangs_is_killed(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, "preflight", lambda: None)
    # A stand-in for pack that ignores its arguments and never finishes.
    hanging = tmp_path / "hanging-pack"
    hanging.write_text("#!/bin/sh\nsleep 300\n")
    hanging.chmod(0o755)
    monkeypatch.setattr(settings, "pack_binary", str(hanging))

    outcome = await pack.run_pack_build(
        image_ref="x/y:z", source_path=tmp_path, log_path=tmp_path / "build.log",
        timeout_seconds=1,
    )
    assert outcome.timed_out is True
    assert outcome.succeeded is False
    assert "timeout" in (outcome.error or "")


@pytest.mark.asyncio
async def test_a_missing_binary_is_reported_not_raised(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, "preflight", lambda: None)
    monkeypatch.setattr(settings, "pack_binary", "/nonexistent/pack")

    outcome = await pack.run_pack_build(
        image_ref="x/y:z", source_path=tmp_path, log_path=tmp_path / "build.log"
    )
    assert outcome.succeeded is False
    assert "Could not start the build" in (outcome.error or "")


# --- Orchestration ----------------------------------------------------------

async def _target(db, user_id, **kwargs) -> Repository:
    repository = Repository(
        user_id=user_id,
        github_repo_id=kwargs.pop("github_repo_id", 1296269),
        name="amvex",
        full_name="octocat/amvex",
        default_branch="main",
        clone_url="https://github.com/octocat/amvex.git",
        detected_type=DetectedType.FRAMEWORK,
        detected_framework="fastapi",
        **kwargs,
    )
    db.add(repository)
    await db.commit()
    await db.refresh(repository)
    return repository


def _stub_build_environment(monkeypatch, tmp_path, *, outcome: BuildOutcome, source_files=()):
    """Stub the download and the pack call; leave the orchestration real."""
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    workdir = tmp_path / "workdir"
    src = workdir / "src"
    src.mkdir(parents=True, exist_ok=True)
    for name in source_files:
        (src / name).parent.mkdir(parents=True, exist_ok=True)
        (src / name).write_text("x")

    @asynccontextmanager
    async def fake_download(access_token, full_name, ref):
        yield SimpleNamespace(path=src, workdir=workdir, file_count=3, total_bytes=99)

    async def fake_token(db, user_id):
        return "gho_token"

    async def fake_head(token, full_name, ref):
        return "b" * 40

    calls = {}

    async def fake_run(**kwargs):
        calls.update(kwargs)
        return outcome

    monkeypatch.setattr(build_service, "downloaded_repository", fake_download)
    monkeypatch.setattr(build_service, "get_access_token", fake_token)
    monkeypatch.setattr(build_service.github_client, "get_head_commit", fake_head)
    monkeypatch.setattr(build_service.pack, "run_pack_build", fake_run)
    monkeypatch.setattr(build_service.pack, "docker_available", lambda: _true())
    monkeypatch.setattr(settings, "build_log_dir", str(tmp_path / "logs"))
    return calls


async def _true() -> bool:
    return True


@pytest.mark.asyncio
async def test_a_successful_build_marks_the_deployment_built(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    repository = await _target(db_session, user_id, deploy_path="backend")
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id,
        build_method=BuildMethod.BUILDPACK, status=DeploymentStatus.QUEUED,
    )
    db_session.add(deployment)
    await db_session.commit()

    _stub_build_environment(
        monkeypatch, tmp_path,
        outcome=BuildOutcome(succeeded=True, exit_code=0, duration_seconds=12.0),
        source_files=("backend/requirements.txt",),
    )

    await build_service.run_build(deployment.id, db=db_session)

    await db_session.refresh(deployment)
    assert deployment.status == DeploymentStatus.BUILT
    assert deployment.image_ref.startswith("deployforge/")
    assert deployment.image_ref.endswith(":bbbbbbb")
    assert deployment.error_message is None
    assert deployment.build_started_at is not None
    assert deployment.build_finished_at is not None
    assert Path(deployment.logs_ref).is_file()


@pytest.mark.asyncio
async def test_a_failed_build_records_the_reason(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    repository = await _target(db_session, user_id)
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.QUEUED
    )
    db_session.add(deployment)
    await db_session.commit()

    _stub_build_environment(
        monkeypatch, tmp_path,
        outcome=BuildOutcome(succeeded=False, exit_code=51, duration_seconds=4.0,
                             error="pack exited with code 51."),
    )

    await build_service.run_build(deployment.id, db=db_session)

    await db_session.refresh(deployment)
    assert deployment.status == DeploymentStatus.FAILED
    assert "51" in deployment.error_message
    assert deployment.image_ref is None


@pytest.mark.asyncio
async def test_an_unreachable_docker_daemon_fails_the_build_clearly(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    repository = await _target(db_session, user_id)
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.QUEUED
    )
    db_session.add(deployment)
    await db_session.commit()

    _stub_build_environment(
        monkeypatch, tmp_path,
        outcome=BuildOutcome(succeeded=True, exit_code=0, duration_seconds=1.0),
    )

    async def unavailable() -> bool:
        return False

    monkeypatch.setattr(build_service.pack, "docker_available", unavailable)

    await build_service.run_build(deployment.id, db=db_session)
    await db_session.refresh(deployment)
    assert deployment.status == DeploymentStatus.FAILED
    assert "Docker daemon" in deployment.error_message


@pytest.mark.asyncio
async def test_an_unexpected_error_still_marks_the_build_failed(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    """A crash must not leave a deployment stuck in `building` forever."""
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    repository = await _target(db_session, user_id)
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.QUEUED
    )
    db_session.add(deployment)
    await db_session.commit()

    monkeypatch.setattr(settings, "build_log_dir", str(tmp_path / "logs"))

    async def boom() -> bool:
        raise RuntimeError("docker exploded")

    monkeypatch.setattr(build_service.pack, "docker_available", boom)

    await build_service.run_build(deployment.id, db=db_session)
    await db_session.refresh(deployment)
    assert deployment.status == DeploymentStatus.FAILED
    assert "docker exploded" in deployment.error_message


@pytest.mark.asyncio
async def test_environment_variables_are_passed_to_the_build(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    from app.core.crypto import encrypt_value
    from app.models.environment import EnvironmentVariable

    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    repository = await _target(db_session, user_id)
    db_session.add_all([
        EnvironmentVariable(repository_id=repository.id, key="DEBUG",
                            value_enc=encrypt_value("false"), is_secret=False),
        EnvironmentVariable(repository_id=repository.id, key="API_KEY",
                            value_enc=encrypt_value("sk_live_xyz"), is_secret=True),
    ])
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.QUEUED
    )
    db_session.add(deployment)
    await db_session.commit()

    calls = _stub_build_environment(
        monkeypatch, tmp_path,
        outcome=BuildOutcome(succeeded=True, exit_code=0, duration_seconds=1.0),
    )

    await build_service.run_build(deployment.id, db=db_session)

    env_file = calls.get("env_file")
    assert env_file is not None
    contents = Path(env_file).read_text()
    assert "DEBUG=false" in contents
    assert "API_KEY=sk_live_xyz" in contents  # decrypted only for the build

    # The secret must not have leaked into the build log.
    assert "sk_live_xyz" not in Path(deployment.logs_ref).read_text()


@pytest.mark.asyncio
async def test_no_env_file_is_written_when_there_are_no_variables(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    repository = await _target(db_session, user_id)
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.QUEUED
    )
    db_session.add(deployment)
    await db_session.commit()

    calls = _stub_build_environment(
        monkeypatch, tmp_path,
        outcome=BuildOutcome(succeeded=True, exit_code=0, duration_seconds=1.0),
    )
    await build_service.run_build(deployment.id, db=db_session)
    assert calls.get("env_file") is None


@pytest.mark.asyncio
async def test_the_subdirectory_target_is_what_gets_built(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    repository = await _target(db_session, user_id, deploy_path="backend")
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.QUEUED
    )
    db_session.add(deployment)
    await db_session.commit()

    calls = _stub_build_environment(
        monkeypatch, tmp_path,
        outcome=BuildOutcome(succeeded=True, exit_code=0, duration_seconds=1.0),
        source_files=("backend/requirements.txt",),
    )
    await build_service.run_build(deployment.id, db=db_session)
    assert Path(calls["source_path"]).name == "backend"


# --- The build endpoint -----------------------------------------------------

async def _signed_up(client, credentials):
    res = await client.post("/auth/signup", json=credentials)
    return (
        {"Authorization": f"Bearer {res.json()['access_token']}"},
        uuid.UUID(res.json()["user"]["id"]),
    )


def _no_real_build(monkeypatch) -> list:
    """Keep the endpoint tests from launching an actual build."""
    started: list = []

    async def fake_run(deployment_id):
        started.append(deployment_id)

    async def ok_toolchain():
        return None

    monkeypatch.setattr(repository_routes, "run_build", fake_run)
    monkeypatch.setattr(repository_routes.pack, "check_toolchain", ok_toolchain)
    return started


@pytest.mark.asyncio
async def test_building_requires_login(client):
    assert (await client.post(f"/repos/{uuid.uuid4()}/build")).status_code == 401


@pytest.mark.asyncio
async def test_building_someone_elses_target_is_a_404(
    client, db_session, user_credentials, admin_credentials, monkeypatch
):
    _no_real_build(monkeypatch)
    _, owner_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, owner_id)

    other_headers, _ = await _signed_up(client, admin_credentials)
    res = await client.post(f"/repos/{repository.id}/build", headers=other_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_build_returns_202_and_queues_the_deployment(
    client, db_session, user_credentials, monkeypatch
):
    started = _no_real_build(monkeypatch)
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id, deploy_path="backend")

    res = await client.post(f"/repos/{repository.id}/build", headers=headers)
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "queued"
    assert body["target_label"] == "octocat/amvex (backend/)"

    deployment = await db_session.get(Deployment, uuid.UUID(body["deployment_id"]))
    assert deployment.status == DeploymentStatus.QUEUED
    assert started == [deployment.id]  # handed to the background task


@pytest.mark.asyncio
async def test_the_first_build_reuses_the_analyzed_deployment(
    client, db_session, user_credentials, monkeypatch
):
    _no_real_build(monkeypatch)
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    analyzed = Deployment(
        repository_id=repository.id, user_id=user_id,
        status=DeploymentStatus.ANALYZED, build_method=BuildMethod.BUILDPACK,
    )
    db_session.add(analyzed)
    await db_session.commit()

    res = await client.post(f"/repos/{repository.id}/build", headers=headers)
    assert res.json()["deployment_id"] == str(analyzed.id)


@pytest.mark.asyncio
async def test_a_later_build_appends_a_new_deployment(
    client, db_session, user_credentials, monkeypatch
):
    from sqlalchemy import select

    _no_real_build(monkeypatch)
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    built = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.BUILT,
        image_ref="deployforge/old:aaaaaaa",
    )
    db_session.add(built)
    await db_session.commit()

    res = await client.post(f"/repos/{repository.id}/build", headers=headers)
    assert res.json()["deployment_id"] != str(built.id)

    rows = (
        await db_session.execute(
            select(Deployment).where(Deployment.repository_id == repository.id)
        )
    ).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_a_second_build_while_one_is_running_is_rejected(
    client, db_session, user_credentials, monkeypatch
):
    _no_real_build(monkeypatch)
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    db_session.add(
        Deployment(repository_id=repository.id, user_id=user_id,
                   status=DeploymentStatus.BUILDING)
    )
    await db_session.commit()

    res = await client.post(f"/repos/{repository.id}/build", headers=headers)
    assert res.status_code == 409
    assert "already running" in res.text


@pytest.mark.asyncio
async def test_missing_build_tooling_is_a_503_before_anything_is_queued(
    client, db_session, user_credentials, monkeypatch
):
    from sqlalchemy import select

    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)

    async def missing():
        raise BuildToolError("The `pack` CLI was not found on the server.")

    monkeypatch.setattr(repository_routes.pack, "check_toolchain", missing)

    res = await client.post(f"/repos/{repository.id}/build", headers=headers)
    assert res.status_code == 503
    assert (
        await db_session.execute(
            select(Deployment).where(Deployment.repository_id == repository.id)
        )
    ).first() is None


# --- Reading build state ----------------------------------------------------

@pytest.mark.asyncio
async def test_deployment_detail_reports_build_fields(
    client, db_session, user_credentials
):
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.BUILT,
        image_ref="deployforge/x:abc1234", logs_ref="/tmp/nope.log",
    )
    db_session.add(deployment)
    await db_session.commit()

    body = (await client.get(f"/deployments/{deployment.id}", headers=headers)).json()
    assert body["status"] == "built"
    assert body["image_ref"] == "deployforge/x:abc1234"
    assert body["has_logs"] is True


@pytest.mark.asyncio
async def test_build_logs_are_returned(client, db_session, user_credentials, tmp_path):
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    log = tmp_path / "build.log"
    log.write_text("Successfully built image\n")
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id,
        status=DeploymentStatus.BUILT, logs_ref=str(log),
    )
    db_session.add(deployment)
    await db_session.commit()

    body = (await client.get(f"/deployments/{deployment.id}/logs", headers=headers)).json()
    assert "Successfully built image" in body["logs"]
    assert body["truncated"] is False


@pytest.mark.asyncio
async def test_a_very_long_log_is_truncated_to_the_tail(
    client, db_session, user_credentials, tmp_path
):
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    log = tmp_path / "build.log"
    log.write_text("x" * 300_000 + "\nTHE END\n")
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id,
        status=DeploymentStatus.BUILT, logs_ref=str(log),
    )
    db_session.add(deployment)
    await db_session.commit()

    body = (await client.get(f"/deployments/{deployment.id}/logs", headers=headers)).json()
    assert body["truncated"] is True
    assert "THE END" in body["logs"]
    assert len(body["logs"]) < 300_000


@pytest.mark.asyncio
async def test_a_missing_log_file_is_not_an_error(client, db_session, user_credentials):
    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    deployment = Deployment(
        repository_id=repository.id, user_id=user_id, status=DeploymentStatus.QUEUED
    )
    db_session.add(deployment)
    await db_session.commit()

    res = await client.get(f"/deployments/{deployment.id}/logs", headers=headers)
    assert res.status_code == 200
    assert res.json()["logs"] == ""


@pytest.mark.asyncio
async def test_another_user_cannot_read_your_deployment_or_logs(
    client, db_session, user_credentials, admin_credentials
):
    _, owner_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, owner_id)
    deployment = Deployment(
        repository_id=repository.id, user_id=owner_id, status=DeploymentStatus.BUILT
    )
    db_session.add(deployment)
    await db_session.commit()

    other, _ = await _signed_up(client, admin_credentials)
    assert (await client.get(f"/deployments/{deployment.id}", headers=other)).status_code == 404
    assert (await client.get(f"/deployments/{deployment.id}/logs", headers=other)).status_code == 404


# --- Toolchain version guard ------------------------------------------------

def test_version_is_parsed_from_pack_output():
    assert pack._parse_version("0.40.9+git-8210eb1.build-6996") == (0, 40, 9)
    assert pack._parse_version("0.36.4+git-c7f5b1c.build-6274") == (0, 36, 4)
    assert pack._parse_version("no version here") is None


def _fake_pack_version(monkeypatch, tmp_path, version: str):
    script = tmp_path / "fake-pack"
    script.write_text(f"#!/bin/sh\necho '{version}'\n")
    script.chmod(0o755)
    monkeypatch.setattr(settings, "pack_binary", str(script))
    monkeypatch.setattr(pack, "preflight", lambda: None)


@pytest.mark.asyncio
async def test_an_old_pack_is_rejected_with_an_actionable_message(monkeypatch, tmp_path):
    """0.36 fails mid-build against Docker 29; catch it before queueing."""
    _fake_pack_version(monkeypatch, tmp_path, "0.36.4+git-c7f5b1c.build-6274")
    with pytest.raises(BuildToolError, match="too old"):
        await pack.check_toolchain()


@pytest.mark.asyncio
async def test_a_current_pack_passes(monkeypatch, tmp_path):
    _fake_pack_version(monkeypatch, tmp_path, "0.40.9+git-8210eb1.build-6996")
    await pack.check_toolchain()  # does not raise


@pytest.mark.asyncio
async def test_unparseable_version_output_does_not_block_a_build(monkeypatch, tmp_path):
    """Better to attempt the build than to refuse over an unrecognized banner."""
    _fake_pack_version(monkeypatch, tmp_path, "some unexpected banner")
    await pack.check_toolchain()  # does not raise


@pytest.mark.asyncio
async def test_the_build_endpoint_reports_an_old_toolchain(
    client, db_session, user_credentials, monkeypatch, tmp_path
):
    from sqlalchemy import select

    headers, user_id = await _signed_up(client, user_credentials)
    repository = await _target(db_session, user_id)
    _fake_pack_version(monkeypatch, tmp_path, "0.36.4")

    res = await client.post(f"/repos/{repository.id}/build", headers=headers)
    assert res.status_code == 503
    assert "too old" in res.text
    assert (
        await db_session.execute(
            select(Deployment).where(Deployment.repository_id == repository.id)
        )
    ).first() is None
