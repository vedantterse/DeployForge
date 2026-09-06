"""
How the repository list is ordered.

This exists because of a real report: a repository forked minutes ago did not
appear near the top of the picker and looked like it had not been noticed at
all. GitHub gives a fork the *parent's* `pushed_at`, so ordering by push date
alone can date a brand-new fork to years ago and sink it below twenty other
repositories.
"""

from __future__ import annotations

from app.github.client import _recency, _repo_summary


def repo(**overrides) -> dict:
    base = {
        "id": 1,
        "name": "demo",
        "full_name": "octocat/demo",
        "default_branch": "main",
        "clone_url": "https://github.com/octocat/demo.git",
        "html_url": "https://github.com/octocat/demo",
        "private": False,
        "fork": False,
        "pushed_at": "2024-01-01T00:00:00Z",
        "created_at": "2023-01-01T00:00:00Z",
    }
    return {**base, **overrides}


# --- Ordering ---------------------------------------------------------------

def test_a_fresh_fork_outranks_an_older_push():
    """The reported bug: a fork made today carried a 2022 push date."""
    fork = _repo_summary(
        repo(pushed_at="2022-11-07T00:00:00Z", created_at="2026-09-06T10:00:00Z")
    )
    older = _repo_summary(
        repo(pushed_at="2026-07-16T00:00:00Z", created_at="2020-01-01T00:00:00Z")
    )
    assert _recency(fork) > _recency(older)


def test_an_actively_pushed_repository_still_outranks_an_old_fork():
    """Fixing forks must not bury the repositories someone actually works on."""
    active = _repo_summary(
        repo(pushed_at="2026-09-05T00:00:00Z", created_at="2020-01-01T00:00:00Z")
    )
    old_fork = _repo_summary(
        repo(pushed_at="2019-01-01T00:00:00Z", created_at="2024-01-01T00:00:00Z")
    )
    assert _recency(active) > _recency(old_fork)


def test_ordering_survives_a_missing_date():
    """GitHub omits `pushed_at` on a repository that has never been pushed to."""
    never_pushed = _repo_summary(repo(pushed_at=None, created_at="2026-01-01T00:00:00Z"))
    assert _recency(never_pushed) == "2026-01-01T00:00:00Z"


def test_a_repository_with_no_dates_at_all_does_not_crash():
    assert _recency(_repo_summary(repo(pushed_at=None, created_at=None))) == ""


# --- Summary shape ----------------------------------------------------------

def test_the_summary_reports_whether_a_repository_is_a_fork():
    assert _repo_summary(repo(fork=True))["fork"] is True
    assert _repo_summary(repo(fork=False))["fork"] is False


def test_the_summary_keeps_the_creation_date():
    """Without it the list cannot tell "added today" from "pushed today"."""
    assert _repo_summary(repo())["created_at"] == "2023-01-01T00:00:00Z"


def test_a_repository_with_no_branch_falls_back_to_main():
    assert _repo_summary(repo(default_branch=None))["default_branch"] == "main"
