"""
Tests for the runtime layer: naming, port choice, routing config, lifecycle.

Docker is never actually invoked — the wrapper is stubbed — so what is
exercised here is the decision-making: which port an app is routed to, what its
URL is, what the router is told, and how status and quota behave. The parts
that genuinely need a daemon are covered by starting a real container by hand.
"""

from __future__ import annotations

import uuid

import pytest

from app.api import internal_routes
from app.config import settings
from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.event import DeploymentEvent
from app.models.repository import DetectedType, Repository
from app.models.user import User
from app.runtime import naming, ports
from app.runtime import service as runtime

DEPLOYMENT_ID = uuid.UUID("4ac9b729-f76e-4a11-9e77-0000000000ff")
REPOSITORY_ID = uuid.UUID("4ac9b729-f76e-4a11-9e77-0000000000ff")


# --- Naming -----------------------------------------------------------------

def test_subdomain_combines_repo_path_and_a_unique_suffix():
    name = naming.subdomain_for(
        repository_id=REPOSITORY_ID, repository_name="Todo App",
        deploy_path="frontend",
    )
    assert name == "todo-app-frontend-4ac9b7"


def test_subdomain_omits_the_path_for_a_root_target():
    name = naming.subdomain_for(
        repository_id=REPOSITORY_ID, repository_name="todo", deploy_path=None
    )
    assert name == "todo-4ac9b7"


def test_two_students_deploying_the_same_repo_get_different_subdomains():
    """Two students both deploying "todo" must each get a working URL."""
    a = naming.subdomain_for(repository_id=uuid.uuid4(), repository_name="todo")
    b = naming.subdomain_for(repository_id=uuid.uuid4(), repository_name="todo")
    assert a != b


def test_every_build_of_one_app_answers_on_the_same_host():
    """
    The URL is the app's, not the build's.

    A student shares their link; redeploying must not silently move the app
    somewhere else.
    """
    first = naming.subdomain_for(
        repository_id=REPOSITORY_ID, repository_name="todo"
    )
    later = naming.subdomain_for(
        repository_id=REPOSITORY_ID, repository_name="todo"
    )
    assert first == later


def test_subdomain_is_a_valid_dns_label():
    name = naming.subdomain_for(
        repository_id=REPOSITORY_ID, repository_name="My_Weird/Repo!!",
    )
    assert name.replace("-", "").isalnum()
    assert name.islower()
    assert not name.startswith("-") and not name.endswith("-")
    assert len(name) <= naming.MAX_LABEL_LENGTH


def test_a_repo_name_with_nothing_usable_still_produces_a_label():
    name = naming.subdomain_for(repository_id=REPOSITORY_ID, repository_name="!!!")
    assert name.startswith("app-")


def test_container_name_is_keyed_on_the_deployment_not_the_repo():
    """Renaming a repository must not orphan its running container."""
    assert naming.container_name_for(DEPLOYMENT_ID) == "df-4ac9b729f76e"


# --- Port choice ------------------------------------------------------------

def test_the_images_own_expose_wins():
    assert ports.choose_port(exposed_ports=[3000], framework="django") == 3000


def test_a_port_environment_variable_is_used_when_the_image_says_nothing():
    assert ports.choose_port(env={"PORT": "4321"}, framework="django") == 4321


def test_the_framework_default_is_the_next_fallback():
    assert ports.choose_port(framework="django") == 8000
    assert ports.choose_port(framework="nextjs") == 3000


def test_buildpack_builds_fall_back_to_8080():
    assert ports.choose_port(build_method="buildpack") == 8080


def test_database_ports_from_a_base_image_are_ignored():
    """A Postgres port inherited from a base image is never the web app."""
    assert ports.choose_port(exposed_ports=[5432, 8000]) == 8000


def test_a_malformed_port_variable_falls_through():
    assert ports.choose_port(env={"PORT": "not-a-number"}, framework="flask") == 5000


def test_an_out_of_range_port_is_rejected():
    assert ports.choose_port(env={"PORT": "99999"}, framework="flask") == 5000


# --- Routing configuration --------------------------------------------------

async def _running_deployment(
    db, user_id, *, github_repo_id: int = 4242, subdomain: str = "todo-abc123"
) -> tuple[Deployment, Repository]:
    """A running app. `subdomain` differs per app: two may not share one."""
    repository = Repository(
        user_id=user_id, github_repo_id=github_repo_id, name="todo",
        full_name="octocat/todo", default_branch="main",
        clone_url="https://github.com/octocat/todo.git",
        detected_type=DetectedType.DOCKER,
    )
    db.add(repository)
    await db.commit()
    await db.refresh(repository)

    deployment = Deployment(
        repository_id=repository.id, user_id=user_id,
        build_method=BuildMethod.DOCKER, status=DeploymentStatus.RUNNING,
        image_ref="localhost:5000/deployforge/x-todo:abc1234",
        subdomain=subdomain, container_name=f"df-{subdomain}", app_port=3000,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    return deployment, repository


@pytest.mark.asyncio
async def test_the_router_is_told_about_running_apps(client, db_session, user_credentials):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    await _running_deployment(db_session, user_id)

    res = await client.get(
        "/internal/traefik/config", params={"token": settings.traefik_provider_token}
    )
    config = res.json()["http"]

    assert "todo-abc123" in config["routers"]
    assert config["routers"]["todo-abc123"]["rule"] == "Host(`todo-abc123.localhost`)"
    server = config["services"]["todo-abc123"]["loadBalancer"]["servers"][0]
    # Routed by container name over the shared network, not by IP: a restarted
    # container keeps its name but not its address.
    assert server["url"] == "http://df-todo-abc123:3000"


@pytest.mark.asyncio
async def test_a_stopped_app_is_removed_from_the_routing_table(
    client, db_session, user_credentials
):
    """Its URL must stop resolving, not point at whatever reuses the name."""
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    deployment.status = DeploymentStatus.STOPPED
    await db_session.commit()

    res = await client.get(
        "/internal/traefik/config", params={"token": settings.traefik_provider_token}
    )
    routers = res.json()["http"]["routers"]
    assert "todo-abc123" not in routers


@pytest.mark.asyncio
async def test_the_routing_table_is_never_returned_empty(client, db_session):
    """
    Traefik keeps its previous configuration when handed an empty one, so an
    empty payload would leave a stopped app's route live, pointing at a
    container that no longer exists. A sentinel entry keeps removals working.
    """
    res = await client.get(
        "/internal/traefik/config", params={"token": settings.traefik_provider_token}
    )
    config = res.json()["http"]

    assert config["routers"], "an empty routers map would not clear stale routes"
    assert config["services"]
    # The sentinel must never be able to serve a real request.
    assert ".invalid" in config["routers"][internal_routes.SENTINEL_NAME]["rule"]


@pytest.mark.asyncio
async def test_the_routing_table_requires_the_shared_token(client):
    res = await client.get("/internal/traefik/config", params={"token": "wrong"})
    assert res.status_code == 403


# --- Quota ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_blocks_starting_more_apps_than_allowed(
    client, db_session, user_credentials
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    user = await db_session.get(User, user_id)
    user.max_deployments = 1
    await db_session.commit()

    with pytest.raises(runtime.QuotaExceededError):
        await runtime.check_quota(db_session, user)


@pytest.mark.asyncio
async def test_a_restart_does_not_count_against_its_own_quota(
    client, db_session, user_credentials
):
    """Restarting an app already holding a slot must not be blocked by it."""
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    user = await db_session.get(User, user_id)
    user.max_deployments = 1
    await db_session.commit()

    await runtime.check_quota(db_session, user, excluding=deployment.id)


# --- Lifecycle --------------------------------------------------------------

@pytest.mark.asyncio
async def test_stopping_records_an_event_and_clears_the_container(
    client, db_session, user_credentials, monkeypatch
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(runtime.docker, "stop_container", noop)
    monkeypatch.setattr(runtime.docker, "remove_container", noop)

    await runtime.stop(db_session, deployment)

    assert deployment.status is DeploymentStatus.STOPPED
    assert deployment.container_id is None
    assert deployment.runtime_stopped_at is not None
    assert deployment.suspended_by_admin is False


@pytest.mark.asyncio
async def test_an_admin_suspension_is_recorded_as_such(
    client, db_session, user_credentials, monkeypatch
):
    """A suspended app must not be restartable by its owner."""
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, repository = await _running_deployment(db_session, user_id)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(runtime.docker, "stop_container", noop)
    monkeypatch.setattr(runtime.docker, "remove_container", noop)

    await runtime.stop(db_session, deployment, actor="admin", suspend=True)
    assert deployment.suspended_by_admin is True

    user = await db_session.get(User, user_id)
    with pytest.raises(runtime.RuntimeError_, match="suspended"):
        await runtime.start(db_session, deployment, repository, user)


def _docker_that_starts_cleanly(monkeypatch):
    """
    Stub Docker so `start()` can run end to end.

    Everything it touches is replaced with the successful answer, so the test
    is about what the platform decides rather than what Docker does.
    """
    from types import SimpleNamespace

    async def ok(*args, **kwargs):
        return None

    async def daemon_available(*args, **kwargs):
        return True

    async def exposed(*args, **kwargs):
        return [3000]

    async def run_container(*args, **kwargs):
        return SimpleNamespace(ok=True, stdout="deadbeef", message="")

    async def container_state(*args, **kwargs):
        return {"Running": True, "ExitCode": 0}

    monkeypatch.setattr(runtime.docker, "daemon_available", daemon_available)
    monkeypatch.setattr(runtime.docker, "ensure_network", ok)
    monkeypatch.setattr(runtime.docker, "image_exposed_ports", exposed)
    monkeypatch.setattr(runtime.docker, "run_container", run_container)
    monkeypatch.setattr(runtime.docker, "container_state", container_state)
    monkeypatch.setattr(runtime.docker, "stop_container", ok)
    monkeypatch.setattr(runtime.docker, "remove_container", ok)
    # The boot grace period is real time; nothing here needs to wait it out.
    monkeypatch.setattr(runtime.settings, "app_start_grace_seconds", 0)


@pytest.mark.asyncio
async def test_a_new_deployment_retires_the_one_it_replaces(
    client, db_session, user_credentials, monkeypatch
):
    """
    An app is one thing with one URL.

    Without this, redeploying leaves the old container running and two of them
    claim the same hostname.
    """
    _docker_that_starts_cleanly(monkeypatch)
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    old, repository = await _running_deployment(db_session, user_id)

    new = Deployment(
        repository_id=repository.id, user_id=user_id,
        build_method=BuildMethod.DOCKER, status=DeploymentStatus.BUILT,
        image_ref="localhost:5000/deployforge/x-todo:def5678",
    )
    db_session.add(new)
    await db_session.commit()

    user = await db_session.get(User, user_id)
    await runtime.start(db_session, new, repository, user)

    await db_session.refresh(old)
    assert new.status is DeploymentStatus.RUNNING
    assert old.status is DeploymentStatus.STOPPED, "the old container is still up"
    assert old.runtime_stopped_at is not None


@pytest.mark.asyncio
async def test_redeploying_keeps_the_url_the_student_shared(
    client, db_session, user_credentials, monkeypatch
):
    """The URL belongs to the app, so a new build answers at the same address."""
    _docker_that_starts_cleanly(monkeypatch)
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    old, repository = await _running_deployment(db_session, user_id)

    user = await db_session.get(User, user_id)
    await runtime.start(db_session, old, repository, user)
    first_url = old.subdomain

    new = Deployment(
        repository_id=repository.id, user_id=user_id,
        build_method=BuildMethod.DOCKER, status=DeploymentStatus.BUILT,
        image_ref="localhost:5000/deployforge/x-todo:def5678",
    )
    db_session.add(new)
    await db_session.commit()
    await runtime.start(db_session, new, repository, user)

    assert new.subdomain == first_url


@pytest.mark.asyncio
async def test_a_redeploy_is_not_refused_by_the_app_s_own_quota_slot(
    client, db_session, user_credentials, monkeypatch
):
    """
    A redeploy briefly runs beside the deployment it replaces. Counting both
    would refuse a student the slot their app already occupies.
    """
    _docker_that_starts_cleanly(monkeypatch)
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    old, repository = await _running_deployment(db_session, user_id)

    user = await db_session.get(User, user_id)
    user.max_deployments = 1
    await db_session.commit()

    new = Deployment(
        repository_id=repository.id, user_id=user_id,
        build_method=BuildMethod.DOCKER, status=DeploymentStatus.BUILT,
        image_ref="localhost:5000/deployforge/x-todo:def5678",
    )
    db_session.add(new)
    await db_session.commit()

    await runtime.start(db_session, new, repository, user)
    assert new.status is DeploymentStatus.RUNNING


@pytest.mark.asyncio
async def test_another_app_still_counts_against_the_quota(
    client, db_session, user_credentials, monkeypatch
):
    """Excluding the app being started must not excuse the rest of them."""
    _docker_that_starts_cleanly(monkeypatch)
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    await _running_deployment(db_session, user_id, github_repo_id=1111)
    other, other_repo = await _running_deployment(
        db_session, user_id, github_repo_id=2222, subdomain="other-def456"
    )
    other.status = DeploymentStatus.BUILT
    user = await db_session.get(User, user_id)
    user.max_deployments = 1
    await db_session.commit()

    with pytest.raises(runtime.QuotaExceededError):
        await runtime.start(db_session, other, other_repo, user)


@pytest.mark.asyncio
async def test_starting_without_an_image_is_refused(
    client, db_session, user_credentials
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, repository = await _running_deployment(db_session, user_id)
    deployment.image_ref = None
    await db_session.commit()

    user = await db_session.get(User, user_id)
    with pytest.raises(runtime.RuntimeError_, match="no image"):
        await runtime.start(db_session, deployment, repository, user)


@pytest.mark.asyncio
async def test_reconcile_marks_vanished_containers_as_stopped(
    client, db_session, user_credentials, monkeypatch
):
    """
    The database must not claim an app is running after Docker restarted.
    """
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    async def available() -> bool:
        return True

    async def no_container(_name):
        return None

    monkeypatch.setattr(runtime.docker, "daemon_available", available)
    monkeypatch.setattr(runtime.docker, "container_state", no_container)

    corrected = await runtime.reconcile(db_session)

    assert corrected >= 1
    await db_session.refresh(deployment)
    assert deployment.status is DeploymentStatus.STOPPED


@pytest.mark.asyncio
async def test_reconcile_leaves_genuinely_running_apps_alone(
    client, db_session, user_credentials, monkeypatch
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    async def available() -> bool:
        return True

    async def running(_name):
        return {"Running": True}

    monkeypatch.setattr(runtime.docker, "daemon_available", available)
    monkeypatch.setattr(runtime.docker, "container_state", running)

    await runtime.reconcile(db_session)

    await db_session.refresh(deployment)
    assert deployment.status is DeploymentStatus.RUNNING


@pytest.mark.asyncio
async def test_events_are_appended_to_the_timeline(
    client, db_session, user_credentials
):
    from sqlalchemy import select

    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    await runtime.record(db_session, deployment.id, "build", "Building.")
    await runtime.record(db_session, deployment.id, "push", "Pushed.")

    rows = (
        await db_session.execute(
            select(DeploymentEvent).where(
                DeploymentEvent.deployment_id == deployment.id
            )
        )
    ).scalars().all()
    assert {r.stage for r in rows} == {"build", "push"}


# --- Server-generated columns ----------------------------------------------

@pytest.mark.asyncio
async def test_timestamps_are_readable_after_an_update(
    client, db_session, user_credentials
):
    """
    Reading `updated_at` after a commit must not emit SQL.

    `updated_at` carries `onupdate=func.now()`, so SQLAlchemy leaves it expired
    after an UPDATE unless server-generated values are fetched eagerly. Building
    a response object is ordinary synchronous attribute access with no greenlet
    context, so a lazy refresh there raises MissingGreenlet and returns a 500 —
    which is exactly what every lifecycle route did until `eager_defaults` was
    turned on. This asserts the attribute is simply present.
    """
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    deployment.status = DeploymentStatus.STOPPED
    await db_session.commit()

    # No await: this is the synchronous read that used to explode.
    assert deployment.updated_at is not None
    assert deployment.created_at is not None


def test_server_generated_values_are_fetched_eagerly():
    """The mapper setting the test above depends on."""
    assert Deployment.__mapper__.eager_defaults is True


# --- Builds interrupted by a restart -----------------------------------------
# A build runs as a background task owning a `docker build` or `pack` child.
# Both die with the server. Without this sweep the row says `building` forever,
# and because the UI refuses a second build while one is in flight, the
# deployment can never be built again — a dead end with no way out.

@pytest.mark.asyncio
async def test_a_build_interrupted_by_a_restart_is_released(
    client, db_session, user_credentials
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)

    deployment.status = DeploymentStatus.BUILDING
    await db_session.commit()

    await runtime.release_interrupted_builds(db_session)

    await db_session.refresh(deployment)
    assert deployment.status is DeploymentStatus.FAILED
    # The message has to say it was not the student's fault, and what to do.
    assert "interrupted" in deployment.error_message.lower()
    assert "rebuild" in deployment.error_message.lower()


@pytest.mark.asyncio
async def test_every_in_flight_build_status_is_released(
    client, db_session, user_credentials
):
    """Queued, building and pushing all die with the process that owned them."""
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])

    stuck = []
    for i, status in enumerate(
        [DeploymentStatus.QUEUED, DeploymentStatus.BUILDING, DeploymentStatus.PUSHING]
    ):
        deployment, _ = await _running_deployment(
            db_session, user_id, github_repo_id=6000 + i
        )
        deployment.status = status
        deployment.subdomain = f"stuck-{i}"
        await db_session.commit()
        stuck.append(deployment)

    await runtime.release_interrupted_builds(db_session)

    for deployment in stuck:
        await db_session.refresh(deployment)
        assert deployment.status is DeploymentStatus.FAILED


@pytest.mark.asyncio
async def test_a_finished_deployment_is_left_alone(
    client, db_session, user_credentials
):
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)  # running

    await runtime.release_interrupted_builds(db_session)

    await db_session.refresh(deployment)
    assert deployment.status is DeploymentStatus.RUNNING


@pytest.mark.asyncio
async def test_reconcile_releases_builds_even_when_docker_is_unreachable(
    client, db_session, user_credentials, monkeypatch
):
    """
    A dead build is dead whatever Docker says, and the student needs the row
    freed so they can try again.
    """
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment, _ = await _running_deployment(db_session, user_id)
    deployment.status = DeploymentStatus.BUILDING
    await db_session.commit()

    async def unavailable() -> bool:
        return False

    monkeypatch.setattr(runtime.docker, "daemon_available", unavailable)

    await runtime.reconcile(db_session)

    await db_session.refresh(deployment)
    assert deployment.status is DeploymentStatus.FAILED
