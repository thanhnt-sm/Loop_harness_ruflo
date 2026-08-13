#!/usr/bin/env python3
"""Kiểm thử update_common.py — shared utils cho update-merge scripts (R-05)."""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import update_common  # noqa: E402


# --- is_protected ---

def test_is_protected_exact():
    assert update_common.is_protected(".env", [".env"]) is True
    assert update_common.is_protected("src/foo.py", [".env"]) is False


def test_is_protected_directory_suffix():
    # "secrets/**" khớp mọi thứ bên trong secrets/
    assert update_common.is_protected("secrets/a/b.txt", ["secrets/**"]) is True
    assert update_common.is_protected("secrets", ["secrets/**"]) is True
    assert update_common.is_protected("src/secrets.txt", ["secrets/**"]) is False


def test_is_protected_prefix():
    assert update_common.is_protected(".devin/hooks/pre_tool_use.py", [".devin/hooks/**"]) is True


def test_is_protected_glob():
    assert update_common.is_protected("cert.pem", ["*.pem"]) is True
    assert update_common.is_protected("deep/nested/cert.pem", ["*.pem"]) is True
    assert update_common.is_protected("cert.txt", ["*.pem"]) is False


def test_is_protected_default_list_covers_sensitive():
    for p in (".env", "secrets/x", "HLK/config/x.json", ".devin/config.json", ".gitignore"):
        assert update_common.is_protected(p, update_common.DEFAULT_PROTECTED_PATTERNS) is True, p


# --- run_cmd ---

def test_run_cmd_ok():
    code, out, _ = update_common.run_cmd([sys.executable, "-c", "print('hi')"])
    assert code == 0
    assert "hi" in out


def test_run_cmd_missing_binary():
    code, _, err = update_common.run_cmd(["/nonexistent/binary-xyz"])
    assert code == 127
    assert "not found" in err


def test_run_cmd_timeout():
    code, _, err = update_common.run_cmd(
        [sys.executable, "-c", "import time; time.sleep(5)"], timeout=1
    )
    assert code == 1
    assert "Timeout" in err


# --- validate_git_url ---

def test_validate_git_url_https_github_ok():
    ok, err = update_common.validate_git_url("https://github.com/org/repo.git")
    assert ok is True and err == ""


@pytest.mark.parametrize("bad", [
    "git@github.com:org/repo.git",   # ssh scheme
    "file:///etc/passwd",            # file scheme
    "http://github.com/org/repo",    # http not allowed
    "https://user:pass@github.com/org/repo.git",  # embedded credentials
    "https://evil.com/org/repo.git", # untrusted host
])
def test_validate_git_url_rejects(bad):
    ok, err = update_common.validate_git_url(bad)
    assert ok is False
    assert err != ""


# --- tracker load/save ---

def test_load_tracker_missing_exits(tmp_path):
    with pytest.raises(SystemExit):
        update_common.load_tracker(tmp_path / "missing.json")


def test_load_tracker_invalid_json_exits(tmp_path):
    p = tmp_path / "tracker.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        update_common.load_tracker(p)


def test_save_and_load_tracker_roundtrip(tmp_path):
    p = tmp_path / "tracker.json"
    update_common.save_tracker(p, {"a": 1})
    assert update_common.load_tracker(p) == {"a": 1}


def test_file_hash_missing_and_consistent(tmp_path):
    assert update_common.file_hash(tmp_path / "nope") == ""
    p = tmp_path / "f.bin"
    p.write_bytes(b"x" * 70000)  # >1 chunk
    h = update_common.file_hash(p)
    assert len(h) == 64
    assert h == update_common.file_hash(p)


# --- git state guards ---

def test_get_current_branch(tmp_git_repo):
    assert update_common.get_current_branch() == "main"


def test_is_dirty_workspace_clean(tmp_git_repo):
    assert update_common.is_dirty_workspace() is False


def test_is_dirty_workspace_dirty(tmp_git_repo):
    (tmp_git_repo / "dirty.txt").write_text("x", encoding="utf-8")
    assert update_common.is_dirty_workspace() is True


def test_guard_main_branch_blocks_without_force(tmp_git_repo):
    assert update_common.guard_main_branch(force=False) is False


def test_guard_main_branch_ok_with_force(tmp_git_repo):
    assert update_common.guard_main_branch(force=True) is True


def test_guard_clean_workspace_dirty_blocks(tmp_git_repo):
    (tmp_git_repo / "dirty.txt").write_text("x", encoding="utf-8")
    assert update_common.guard_clean_workspace(force=False) is False
    assert update_common.guard_clean_workspace(force=True) is True


def test_guard_clean_workspace_clean_ok(tmp_git_repo):
    assert update_common.guard_clean_workspace(force=False) is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
