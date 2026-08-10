#!/usr/bin/env python3
"""Kiểm thử branch/worktree isolation (T3.4 / REQ-010)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import apply_ahd_patch  # noqa: E402
import update_common  # noqa: E402


def test_setup_feature_branch_creates_branch(tmp_git_repo: Path):
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_git_repo
    apply_ahd_patch.REPO_ROOT = tmp_git_repo
    try:
        branch = apply_ahd_patch.setup_feature_branch()
        assert branch is not None
        assert branch.startswith("feat/ahd-update-")
        # branch exists
        import subprocess
        result = subprocess.run(["git", "branch", "--list", branch], cwd=tmp_git_repo, capture_output=True, text=True)
        assert branch in result.stdout
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old


def test_setup_worktree_creates_worktree(tmp_git_repo: Path):
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_git_repo
    apply_ahd_patch.REPO_ROOT = tmp_git_repo
    try:
        wt = tmp_git_repo / "wt-ahd"
        result = apply_ahd_patch.setup_worktree(wt)
        assert result == wt
        assert (wt / ".git").exists() or (wt / ".git").is_file()
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old
