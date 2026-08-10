#!/usr/bin/env python3
"""Kiểm thử commit behavior — default không auto-commit (T3.7 / REQ-005)."""
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


def test_commit_changes_default_does_not_commit(tmp_git_repo: Path):
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_git_repo
    apply_ahd_patch.REPO_ROOT = tmp_git_repo
    try:
        import subprocess

        f = tmp_git_repo / "change.md"
        f.write_text("changed\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_git_repo, check=True, capture_output=True)

        # default auto_commit=False should NOT create commit
        ok = apply_ahd_patch.commit_changes("abc1234", "test", auto_commit=False)
        assert ok is True

        result = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=tmp_git_repo, capture_output=True, text=True)
        assert result.stdout.strip() == "init"  # no new commit

        # auto_commit=True should create commit
        ok = apply_ahd_patch.commit_changes("abc1234", "test", auto_commit=True)
        assert ok is True
        result = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=tmp_git_repo, capture_output=True, text=True)
        assert "cherry-pick AHD" in result.stdout
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old
