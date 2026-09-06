"""
Running several directories of one repository together.

A frontend and the backend it calls are one app. Deployed separately they get
two URLs and no way to reach each other, which is the failure this module
exists to prevent — so the tests are mostly about the wiring.
"""

from __future__ import annotations

import json

from app.builder import stack


# --- Naming -----------------------------------------------------------------

def test_a_directory_becomes_a_dns_safe_service_name():
    assert stack.service_name("frontend") == "frontend"
    assert stack.service_name("My_Api Service") == "my-api-service"


def test_the_repository_root_is_named_rather_than_left_blank():
    """Compose needs a name, and "" is not one."""
    assert stack.service_name("") == "app"


def test_a_name_with_nothing_usable_still_produces_one():
    assert stack.service_name("!!!") == "app"


# --- Which service is public ------------------------------------------------

def test_a_conventional_frontend_name_receives_traffic():
    assert stack.choose_web_service(["backend", "frontend"]) == "frontend"


def test_the_first_service_is_used_when_no_name_stands_out():
    """Returning something beats refusing; the user can see and reorder."""
    assert stack.choose_web_service(["alpha", "beta"]) == "alpha"


def test_a_single_service_is_the_public_one():
    assert stack.choose_web_service(["api"]) == "api"


# --- Wiring -----------------------------------------------------------------

def test_every_service_is_addressable_by_an_environment_variable():
    """
    This is what makes a stack useful rather than merely co-located: the
    frontend is handed the backend's address without hardcoding a hostname it
    could not have known.
    """
    urls = stack.service_urls(["frontend", "backend"])
    assert urls["BACKEND_URL"] == "http://backend:8080"
    assert urls["FRONTEND_URL"] == "http://frontend:8080"


def test_variable_names_are_shell_safe():
    assert stack.env_var_for("my-api") == "MY_API_URL"


# --- The generated stack ----------------------------------------------------

def _parsed(**kwargs) -> dict:
    return json.loads(stack.compose_file(**kwargs))


def test_the_stack_runs_the_images_that_were_built():
    """
    It must reference images, not build contexts: the source is gone by the
    time the stack starts.
    """
    config = _parsed(services={"web": "registry/web:abc", "api": "registry/api:abc"})
    assert config["services"]["web"]["image"] == "registry/web:abc"
    assert "build" not in config["services"]["web"]


def test_every_service_can_reach_every_other_one():
    config = _parsed(services={"frontend": "i1", "backend": "i2"})
    frontend = config["services"]["frontend"]["environment"]
    backend = config["services"]["backend"]["environment"]
    assert frontend["BACKEND_URL"] == "http://backend:8080"
    assert backend["FRONTEND_URL"] == "http://frontend:8080"


def test_the_shared_environment_reaches_every_service():
    config = _parsed(services={"a": "i1", "b": "i2"}, env={"API_KEY": "s3cret"})
    for name in ("a", "b"):
        assert config["services"][name]["environment"]["API_KEY"] == "s3cret"


def test_every_service_is_told_which_port_to_listen_on():
    """A buildpack launcher and a framework both read PORT."""
    config = _parsed(services={"web": "i1"})
    assert config["services"]["web"]["environment"]["PORT"] == "8080"
    assert config["services"]["web"]["expose"] == ["8080"]


def test_no_service_publishes_a_host_port():
    """The router is the only way in; a published port would bypass it."""
    config = _parsed(services={"web": "i1", "api": "i2"})
    for service in config["services"].values():
        assert "ports" not in service


def test_the_generated_stack_is_valid_json_and_therefore_valid_yaml():
    """Emitting JSON avoids a whole class of YAML quoting bugs."""
    text = stack.compose_file(services={"web": "registry/web:tag"})
    assert json.loads(text)["services"]["web"]["restart"] == "unless-stopped"


def test_wiring_never_overrules_a_variable_the_student_set():
    """
    A student pointing BACKEND_URL at an external API has already decided.
    Replacing it with an internal address would break their app for a reason
    they cannot see — filling a gap is help, overruling a choice is not.
    """
    config = _parsed(
        services={"frontend": "i1", "backend": "i2"},
        env={"BACKEND_URL": "https://api.example.com"},
    )
    assert (
        config["services"]["frontend"]["environment"]["BACKEND_URL"]
        == "https://api.example.com"
    )
    # The service that was not overridden still gets its generated address.
    assert (
        config["services"]["backend"]["environment"]["FRONTEND_URL"]
        == "http://frontend:8080"
    )
