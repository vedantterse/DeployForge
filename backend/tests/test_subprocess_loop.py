"""
Every external command must run on any event loop, not just a Proactor one.

This exists because of a real failure: the runtime and builder originally used
`asyncio.create_subprocess_exec`, which raises NotImplementedError on a Windows
SelectorEventLoop. Unit tests passed — `asyncio.run()` gives a Proactor loop on
Windows — but the server, which runs on whichever loop its host chose, could
not invoke Docker at all. Every build and every start failed with a 500.

So these tests deliberately run on a Selector loop, which is the strictest of
the two, and assert the commands still work.
"""

from __future__ import annotations

import asyncio
import selectors
import sys

import pytest

from app.builder import pack
from app.runtime import docker


def run_on_selector_loop(coro_factory):
    """
    Run a coroutine on a SelectorEventLoop.

    A fresh loop is created and closed here rather than reusing pytest-asyncio's,
    because the whole point is to control which loop implementation is used.
    """
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()


def test_docker_commands_work_on_a_selector_loop():
    """`docker --version` is harmless and proves a subprocess can be spawned."""
    result = run_on_selector_loop(lambda: docker._run("--version", timeout=30))
    assert result.ok
    assert "docker" in result.stdout.lower()


def test_daemon_availability_check_works_on_a_selector_loop():
    """Must return a bool either way — never raise NotImplementedError."""
    available = run_on_selector_loop(docker.daemon_available)
    assert isinstance(available, bool)


def test_the_builders_docker_check_works_on_a_selector_loop():
    available = run_on_selector_loop(pack.docker_available)
    assert isinstance(available, bool)


def test_streamed_commands_work_on_a_selector_loop(tmp_path):
    """The build path writes output straight to a log file as it runs."""
    log = tmp_path / "build.log"

    result = run_on_selector_loop(
        lambda: docker._stream([docker.settings.docker_binary, "--version"], log, 30)
    )

    assert result.ok
    assert "docker" in log.read_text(encoding="utf-8").lower()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="The failure this guards against is specific to Windows event loops.",
)
def test_the_asyncio_subprocess_api_is_genuinely_unusable_here():
    """
    Confirms the hazard is real rather than hypothetical.

    If this ever starts passing, Python has changed and the thread-based
    workaround could be revisited — but not before.
    """

    async def spawn():
        await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")

    with pytest.raises(NotImplementedError):
        run_on_selector_loop(lambda: spawn())
