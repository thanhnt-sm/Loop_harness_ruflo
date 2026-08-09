#!/usr/bin/env python3
"""Shared fixtures cho kiểm thử update-merge scripts."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import update_common  # noqa: E402


@pytest.fixture
def tmp_git_repo(tmp_path: Path):
    """Tạo một git repo tạm thời với marker files để làm REPO_ROOT cho tests."""
    import subprocess

    # Tạo cấu trúc marker
    (tmp_path / ".devin").mkdir()
    (tmp_path / ".devin" / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()

    # init git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

    # initial commit on main
    (tmp_path / "README.md").write_text("# init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, check=True, capture_output=True)

    # Monkeypatch REPO_ROOT
    original = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_path

    import apply_ahd_patch
    apply_ahd_patch.REPO_ROOT = tmp_path

    yield tmp_path

    # restore
    update_common.REPO_ROOT = original
    apply_ahd_patch.REPO_ROOT = original
