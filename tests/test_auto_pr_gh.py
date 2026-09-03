"""Tests cho auto_pr_gh.py — wrap GitHub CLI."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import auto_pr_gh  # noqa: E402
from auto_pr_gh import GHResult, _extract_url, _extract_pr_number, create_pr, preflight  # noqa: E402


def test_extract_url_valid():
    assert _extract_url("https://github.com/foo/bar/pull/1") == "https://github.com/foo/bar/pull/1"


def test_extract_url_invalid():
    assert _extract_url("no url here") is None


def test_extract_pr_number():
    assert _extract_pr_number("https://github.com/foo/bar/pull/42") == 42
    assert _extract_pr_number("https://github.com/foo/bar") is None


def test_create_pr_success():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(
            success=True,
            stdout="https://github.com/foo/bar/pull/123 created",
            stderr="", exit_code=0,
        )
        r = create_pr("title", "body", base="main", head="branch")
        assert r.success is True
        assert r.data["url"] == "https://github.com/foo/bar/pull/123"
        assert r.data["number"] == 123


def test_create_pr_failure():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(
            success=False, stdout="", stderr="auth error", exit_code=1,
        )
        r = create_pr("title", "body")
        assert r.success is False
        assert r.data is None


def test_create_pr_command_construction():
    """Verify command structure: gh pr create --title T --body B --base B --head H --draft."""
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(
            success=True, stdout="https://github.com/x/y/pull/1", stderr="", exit_code=0,
        )
        create_pr("My Title", "My Body", base="develop", head="feature/x", draft=True)
        cmd = mock_run.call_args[0][0]
        assert "gh" in cmd
        assert "pr" in cmd
        assert "create" in cmd
        assert "--title" in cmd
        assert "My Title" in cmd
        assert "--body" in cmd
        assert "My Body" in cmd
        assert "--base" in cmd
        assert "develop" in cmd
        assert "--head" in cmd
        assert "feature/x" in cmd
        assert "--draft" in cmd


def test_preflight_gh_not_installed():
    with mock.patch("auto_pr_gh.check_gh_installed", return_value=False):
        ok, msg = preflight()
        assert ok is False
        assert "not found" in msg.lower()


def test_preflight_not_authed():
    with mock.patch("auto_pr_gh.check_gh_installed", return_value=True), \
         mock.patch("auto_pr_gh.check_auth_status", return_value=False):
        ok, msg = preflight()
        assert ok is False
        assert "auth" in msg.lower()


def test_preflight_no_repo():
    with mock.patch("auto_pr_gh.check_gh_installed", return_value=True), \
         mock.patch("auto_pr_gh.check_auth_status", return_value=True), \
         mock.patch("auto_pr_gh.check_repo", return_value=False):
        ok, msg = preflight()
        assert ok is False
        assert "repo" in msg.lower()


def test_preflight_all_ok():
    with mock.patch("auto_pr_gh.check_gh_installed", return_value=True), \
         mock.patch("auto_pr_gh.check_auth_status", return_value=True), \
         mock.patch("auto_pr_gh.check_repo", return_value=True):
        ok, msg = preflight()
        assert ok is True
        assert msg == "OK"
