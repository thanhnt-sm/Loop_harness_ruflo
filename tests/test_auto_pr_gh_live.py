"""Tests cho auto_pr_gh với mock subprocess (cross-platform safe).

Thay vì tạo fake gh binary (khó cross-platform), mock _run trực tiếp.
Verify preflight, create_pr, merge_pr, check_ci, live_auto_merge logic.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import auto_pr_gh  # noqa: E402
from auto_pr_gh import GHResult  # noqa: E402


# --- check_gh_installed ---


def test_check_gh_installed_true():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(True, "gh version 2.40.0", "", 0)
        assert auto_pr_gh.check_gh_installed("gh") is True


def test_check_gh_installed_false():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(False, "", "command not found", -1)
        assert auto_pr_gh.check_gh_installed("nonexistent-gh-xyz") is False


# --- check_auth_status ---


def test_check_auth_status_logged_in():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(True, "Logged in to github.com", "", 0)
        assert auto_pr_gh.check_auth_status("gh") is True


def test_check_auth_status_not_logged_in():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(False, "You are not logged in", "", 1)
        assert auto_pr_gh.check_auth_status("gh") is False


# --- check_repo ---


def test_check_repo_in_repo():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(True, "user/repo", "", 0)
        assert auto_pr_gh.check_repo("gh") is True


def test_check_repo_not_in_repo():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(False, "not a git repo", "", 1)
        assert auto_pr_gh.check_repo("gh") is False


# --- preflight ---


def test_preflight_all_ok():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.side_effect = [
            GHResult(True, "gh 2.40", "", 0),
            GHResult(True, "OK", "", 0),
            GHResult(True, "user/repo", "", 0),
        ]
        ok, msg = auto_pr_gh.preflight("gh")
        assert ok is True
        assert msg == "OK"
        assert mock_run.call_count == 3


def test_preflight_gh_not_installed():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(False, "", "command not found", -1)
        ok, msg = auto_pr_gh.preflight("nonexistent")
        assert ok is False
        assert "not found" in msg.lower()


def test_preflight_not_authed():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.side_effect = [
            GHResult(True, "gh 2.40", "", 0),
            GHResult(False, "Not logged in", "", 1),
        ]
        ok, msg = auto_pr_gh.preflight("gh")
        assert ok is False
        assert "auth" in msg.lower()


def test_preflight_no_repo():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.side_effect = [
            GHResult(True, "gh 2.40", "", 0),
            GHResult(True, "OK", "", 0),
            GHResult(False, "not a repo", "", 1),
        ]
        ok, msg = auto_pr_gh.preflight("gh")
        assert ok is False
        assert "repo" in msg.lower()


# --- create_pr ---


def test_create_pr_success():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(
            True, "https://github.com/user/repo/pull/42 created", "", 0
        )
        r = auto_pr_gh.create_pr(
            title="feat: x", body="body", base="main", head="feat/x", gh_bin="gh",
        )
        assert r.success is True
        assert r.data["url"] == "https://github.com/user/repo/pull/42"
        assert r.data["number"] == 42
        cmd = mock_run.call_args[0][0]
        assert "gh" in cmd and "pr" in cmd and "create" in cmd
        assert "--title" in cmd and "feat: x" in cmd
        assert "--body" in cmd
        assert "--base" in cmd and "main" in cmd
        assert "--head" in cmd and "feat/x" in cmd


def test_create_pr_draft():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(
            True, "https://github.com/user/repo/pull/1 created", "", 0
        )
        auto_pr_gh.create_pr("t", "b", gh_bin="gh", draft=True)
        cmd = mock_run.call_args[0][0]
        assert "--draft" in cmd


def test_create_pr_failure():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(False, "", "auth required", 1)
        r = auto_pr_gh.create_pr("t", "b", gh_bin="gh")
        assert r.success is False
        assert r.data is None


# --- merge_pr ---


def test_merge_pr_squash():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(True, "", "", 0)
        r = auto_pr_gh.merge_pr("https://github.com/x/y/pull/1", method="squash", gh_bin="gh")
        assert r.success is True
        cmd = mock_run.call_args[0][0]
        assert "merge" in cmd
        assert "--squash" in cmd


def test_merge_pr_rebase():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(True, "", "", 0)
        auto_pr_gh.merge_pr("https://github.com/x/y/pull/1", method="rebase", gh_bin="gh")
        cmd = mock_run.call_args[0][0]
        assert "--rebase" in cmd


# --- check_ci ---


def test_check_ci_all_pass():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(
            True,
            '[{"name": "ci/build", "state": "SUCCESS"}, {"name": "ci/test", "state": "SUCCESS"}]',
            "", 0,
        )
        passed, failed = auto_pr_gh.check_ci("https://x/y/pull/1", ["ci/build", "ci/test"], "gh")
        assert passed is True
        assert failed == []


def test_check_ci_some_fail():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(
            True,
            '[{"name": "ci/build", "state": "SUCCESS"}, {"name": "ci/test", "state": "FAILURE"}]',
            "", 0,
        )
        passed, failed = auto_pr_gh.check_ci("https://x/y/pull/1", ["ci/build", "ci/test"], "gh")
        assert passed is False
        assert any("ci/test" in f and "FAILURE" in f for f in failed)


# --- live_auto_merge end-to-end ---


def test_live_auto_merge_secret_detected_blocks():
    """Khi body chứa AWS key → return fail trước khi gọi gh."""
    result = auto_pr_gh.live_auto_merge(
        title="t", body="config: AKIAIOSFODNN7EXAMPLE", branch_prefix="verify-first/",
    )
    assert result["success"] is False
    assert "secret" in result["reason"].lower()


def test_live_auto_merge_preflight_fails():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.return_value = GHResult(False, "", "command not found", -1)
        result = auto_pr_gh.live_auto_merge(
            title="t", body="b", branch_prefix="verify-first/",
            gh_bin="nonexistent-gh",
        )
        assert result["success"] is False
        assert "preflight" in result["reason"].lower() or "not found" in result["reason"].lower()


def test_live_auto_merge_success_no_ci():
    """Khi preflight OK + create PR OK + no required_ci → merge thành công."""
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.side_effect = [
            GHResult(True, "gh 2.40", "", 0),
            GHResult(True, "OK", "", 0),
            GHResult(True, "user/repo", "", 0),
            GHResult(True, "https://github.com/user/repo/pull/1 created", "", 0),
            GHResult(True, "", "", 0),
        ]
        result = auto_pr_gh.live_auto_merge(
            title="t", body="b", branch_prefix="verify-first/",
        )
        assert result["success"] is True
        assert result["pr_url"] == "https://github.com/user/repo/pull/1"


def test_live_auto_merge_with_required_ci_pass():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.side_effect = [
            GHResult(True, "gh 2.40", "", 0),
            GHResult(True, "OK", "", 0),
            GHResult(True, "user/repo", "", 0),
            GHResult(True, "https://github.com/user/repo/pull/1 created", "", 0),
            GHResult(True, '[{"name": "ci/build", "state": "SUCCESS"}]', "", 0),
            GHResult(True, "", "", 0),
        ]
        result = auto_pr_gh.live_auto_merge(
            title="t", body="b", branch_prefix="verify-first/",
            required_ci=["ci/build"],
            ci_max_wait=10,
        )
        assert result["success"] is True


def test_live_auto_merge_with_required_ci_fail():
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.side_effect = [
            GHResult(True, "gh 2.40", "", 0),
            GHResult(True, "OK", "", 0),
            GHResult(True, "user/repo", "", 0),
            GHResult(True, "https://github.com/user/repo/pull/1 created", "", 0),
            GHResult(True, '[{"name": "ci/build", "state": "FAILURE"}]', "", 0),
        ]
        result = auto_pr_gh.live_auto_merge(
            title="t", body="b", branch_prefix="verify-first/",
            required_ci=["ci/build"],
            ci_max_wait=10,
        )
        assert result["success"] is False


def test_live_auto_merge_draft_pr():
    """Khi branch_prefix chứa 'draft' → tạo draft PR, không merge."""
    with mock.patch("auto_pr_gh._run") as mock_run:
        mock_run.side_effect = [
            GHResult(True, "gh 2.40", "", 0),
            GHResult(True, "OK", "", 0),
            GHResult(True, "user/repo", "", 0),
            GHResult(True, "https://github.com/user/repo/pull/1 created", "", 0),
        ]
        result = auto_pr_gh.live_auto_merge(
            title="t", body="b", branch_prefix="verify-first-draft/",
        )
        assert result["success"] is True
        assert "draft" in result["reason"].lower()
        pr_create_call = mock_run.call_args_list[3]
        assert "--draft" in pr_create_call[0][0]
