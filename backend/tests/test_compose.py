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


# --- Host port bindings ------------------------------------------------------
#
# The failure these came from: two students both deploying a Next.js compose
# file that publishes 3000. The second gets "ports are not available", and on a
# laptop it collides with whatever is already there.

import textwrap  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402


def write_stack(tmp_path, text: str, name: str = "docker-compose.yml") -> Path:
    (tmp_path / name).write_text(textwrap.dedent(text), encoding="utf-8")
    return tmp_path


def test_a_published_port_becomes_an_exposed_one(tmp_path):
    """The port stays reachable in the stack; it stops being claimed on the host."""
    stack = write_stack(
        tmp_path,
        """
        services:
          web:
            image: verde-store:latest
            ports:
              - "3000:3000"
        """,
    )

    removed = compose.strip_published_ports(stack)

    assert removed == {"web": [3000]}
    written = yaml.safe_load((stack / "docker-compose.yml").read_text(encoding="utf-8"))
    assert "ports" not in written["services"]["web"]
    assert written["services"]["web"]["expose"] == ["3000"]


def test_the_long_port_form_is_handled(tmp_path):
    """`docker compose config` normalizes to this shape, and files use it too."""
    stack = write_stack(
        tmp_path,
        """
        services:
          api:
            image: api:latest
            ports:
              - target: 8080
                published: "9000"
                protocol: tcp
        """,
    )

    assert compose.strip_published_ports(stack) == {"api": [8080]}
    written = yaml.safe_load((stack / "docker-compose.yml").read_text(encoding="utf-8"))
    assert written["services"]["api"]["expose"] == ["8080"]


def test_a_database_beside_the_app_is_unpublished_too(tmp_path):
    """
    The isolation point rather than the collision one: a published 5432 puts
    one student's database on the shared machine's network.
    """
    stack = write_stack(
        tmp_path,
        """
        services:
          web:
            image: web:latest
            ports: ["3000:3000"]
          db:
            image: postgres:17
            ports: ["5432:5432"]
        """,
    )

    assert compose.strip_published_ports(stack) == {"web": [3000], "db": [5432]}


def test_an_override_file_cannot_put_the_binding_back(tmp_path):
    """Compose loads the override automatically, so it has to be stripped too."""
    stack = write_stack(
        tmp_path,
        """
        services:
          web:
            image: web:latest
        """,
    )
    write_stack(
        stack,
        """
        services:
          web:
            ports: ["3000:3000"]
        """,
        name="docker-compose.override.yml",
    )

    assert compose.strip_published_ports(stack) == {"web": [3000]}
    override = yaml.safe_load(
        (stack / "docker-compose.override.yml").read_text(encoding="utf-8")
    )
    assert "ports" not in override["services"]["web"]


def test_an_existing_expose_is_kept(tmp_path):
    stack = write_stack(
        tmp_path,
        """
        services:
          web:
            image: web:latest
            expose: ["9229"]
            ports: ["3000:3000"]
        """,
    )

    compose.strip_published_ports(stack)
    written = yaml.safe_load((stack / "docker-compose.yml").read_text(encoding="utf-8"))
    assert written["services"]["web"]["expose"] == ["9229", "3000"]


def test_a_stack_without_bindings_is_left_untouched(tmp_path):
    original = """
        services:
          web:
            image: web:latest
            expose: ["3000"]
        """
    stack = write_stack(tmp_path, original)
    before = (stack / "docker-compose.yml").read_text(encoding="utf-8")

    assert compose.strip_published_ports(stack) == {}
    assert (stack / "docker-compose.yml").read_text(encoding="utf-8") == before


def test_an_unparseable_file_is_left_alone(tmp_path):
    """
    Compose has already accepted the file, so failing to parse it here means
    this function is wrong — and breaking a working deployment over that would
    be worse than leaving a port published.
    """
    stack = tmp_path
    (stack / "docker-compose.yml").write_text("services: [oh: no: :", encoding="utf-8")

    assert compose.strip_published_ports(stack) == {}
    assert (stack / "docker-compose.yml").read_text(encoding="utf-8")


def test_nothing_happens_without_a_compose_file(tmp_path):
    assert compose.strip_published_ports(tmp_path) == {}
