"""
Tests for compose support: which service gets traffic, and on which port.

Docker parses the compose file, so what is tested here is the decision made
*from* that parsed config — the part DeployForge owns and the part that goes
wrong silently. Routing a stack to its Postgres container produces a container
that is up, a URL that resolves, and a page that never loads; catching that
needs a test, not a smoke check.
"""

from __future__ import annotations

import uuid

from app.runtime import compose


def config(services: dict) -> dict:
    """A resolved compose configuration, shaped as `docker compose config` emits."""
    return {"services": services}


# --- Choosing the routed service --------------------------------------------

def test_a_published_port_marks_the_web_service():
    """Publishing a port is the author saying "this one is reachable"."""
    service, port = compose.choose_web_service(
        config(
            {
                "web": {"build": ".", "ports": [{"target": 3000, "published": "8080"}]},
                "worker": {"build": "."},
            }
        )
    )
    assert service == "web"
    assert port == 3000


def test_the_container_port_is_used_not_the_published_one():
    """Traffic is routed inside the network, where only the target port exists."""
    _, port = compose.choose_web_service(
        config({"api": {"ports": [{"target": 8000, "published": "9999"}]}})
    )
    assert port == 8000


def test_short_form_ports_are_understood():
    """`ports: ["8080:80"]` is still legal and appears in real repositories."""
    service, port = compose.choose_web_service(
        config({"web": {"ports": ["8080:80"]}})
    )
    assert (service, port) == ("web", 80)


def test_a_database_is_never_chosen_as_the_web_service():
    """
    The classic failure: Postgres publishes 5432, the app publishes nothing,
    and the stack routes to the database.
    """
    service, _ = compose.choose_web_service(
        config(
            {
                "db": {
                    "image": "postgres:17-alpine",
                    "ports": [{"target": 5432, "published": "5432"}],
                },
                "web": {"build": ".", "expose": [8000]},
            }
        )
    )
    assert service == "web"


def test_infrastructure_images_are_recognized_by_name():
    for image in ("redis:7", "mongo:7", "rabbitmq:3-management", "mysql:8"):
        service, _ = compose.choose_web_service(
            config(
                {
                    "cache": {"image": image, "ports": [{"target": 6379}]},
                    "app": {"build": ".", "expose": [3000]},
                }
            )
        )
        assert service == "app", f"{image} was chosen as the web service"


def test_a_conventional_name_wins_when_nothing_publishes_a_port():
    service, port = compose.choose_web_service(
        config({"db": {"image": "postgres:17"}, "frontend": {"build": ".", "expose": [3000]}})
    )
    assert (service, port) == ("frontend", 3000)


def test_a_single_service_stack_routes_to_it():
    service, _ = compose.choose_web_service(config({"anything": {"build": "."}}))
    assert service == "anything"


def test_a_stack_with_nothing_routable_says_so():
    """A worker-only stack has no web service, and that is a real answer."""
    service, port = compose.choose_web_service(
        config({"worker": {"build": "."}, "scheduler": {"build": "."}})
    )
    assert service is None and port is None


def test_an_empty_stack_is_handled():
    assert compose.choose_web_service(config({})) == (None, None)


# --- Naming ------------------------------------------------------------------

def test_the_project_name_is_unique_per_deployment():
    """Two students' `web` services must not collide."""
    a = compose.project_name(uuid.uuid4())
    b = compose.project_name(uuid.uuid4())
    assert a != b
    assert a.startswith("df-")


def test_container_names_follow_composes_own_convention():
    project = "df-abc123"
    assert compose.container_name_for(project, "web") == "df-abc123-web-1"


def test_service_names_are_sorted_for_stable_display():
    assert compose.service_names(config({"web": {}, "db": {}, "cache": {}})) == [
        "cache",
        "db",
        "web",
    ]


# --- Compose file discovery --------------------------------------------------

def test_compose_files_are_found_in_dockers_preference_order(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text("services: {}", encoding="utf-8")

    # Docker prefers compose.yaml over the older docker-compose.yml.
    assert compose.find_compose_file(tmp_path).name == "compose.yaml"


def test_no_compose_file_is_not_an_error(tmp_path):
    assert compose.find_compose_file(tmp_path) is None


# --- Stack working copy ------------------------------------------------------

def test_the_stack_directory_replaces_rather_than_merges(tmp_path):
    """
    A redeploy must not leave deleted files behind for the build to pick up.
    """
    deployment_id = uuid.uuid4()

    first = tmp_path / "first"
    first.mkdir()
    (first / "keep.txt").write_text("a", encoding="utf-8")
    (first / "removed-later.txt").write_text("b", encoding="utf-8")
    compose.replace_stack_dir(deployment_id, first)

    second = tmp_path / "second"
    second.mkdir()
    (second / "keep.txt").write_text("c", encoding="utf-8")
    destination = compose.replace_stack_dir(deployment_id, second)

    names = {p.name for p in destination.iterdir()}
    assert names == {"keep.txt"}
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "c"

    compose.remove_stack_dir(deployment_id)
    assert not any(compose.stack_dir_for(deployment_id).iterdir())
