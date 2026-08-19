#!/usr/bin/env python3
"""Kiểm thử show_diff.py — diff local vs upstream cho một source.

Bao phủ: parse_repo_url, clone_repo (mock), main().
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import show_diff  # noqa: E402


def _write_tracker(tmp_path, source):
    tracker = tmp_path / "REPOS_TRACKER.json"
    tracker.write_text(json.dumps({"sources": [source]}), encoding="utf-8")
    return tracker


# --- parse_repo_url ---

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/owner/repo.git", ("owner", "repo")),
    ("https://github.com/owner/repo", ("owner", "repo")),
    ("https://github.com/owner/repo/", ("owner", "repo")),
    ("https://gitlab.com/owner/repo.git", ("owner", "repo")),
    ("not-a-url", None),
    ("https://github.com/owner", ("github.com", "owner")),
])
def test_parse_repo_url(url, expected):
    assert show_diff.parse_repo_url(url) == expected


# --- clone_repo ---

def test_clone_repo_rejects_non_https(tmp_path):
    """URL file:// phải bị chặn bởi validate_git_url."""
    dest = tmp_path / "clone-dest"
    result = show_diff.clone_repo("file:///etc/passwd", dest)
    assert result is False


def test_clone_repo_rejects_untrusted_host(tmp_path):
    dest = tmp_path / "clone-dest"
    result = show_diff.clone_repo("https://evil.com/repo.git", dest)
    assert result is False


def test_clone_repo_success_mock(tmp_path):
    dest = tmp_path / "clone-dest"
    with patch.object(show_diff, "run_cmd", return_value=(0, "", "")):
        result = show_diff.clone_repo(
            "https://github.com/owner/repo.git", dest, "main", depth=1
        )
    assert result is True


def test_clone_repo_git_failure_mock(tmp_path):
    dest = tmp_path / "clone-dest"
    dest.mkdir()
    with patch.object(show_diff, "run_cmd", return_value=(1, "", "clone failed")):
        result = show_diff.clone_repo("https://github.com/owner/repo.git", dest)
    assert result is False


# --- main() ---

def test_main_source_id_not_found(tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill",
        "url": "https://github.com/owner/repo", "branch": "main",
        "vendored_path": ".devin/skills/test-skill/",
    })
    with patch("sys.argv", ["show_diff.py", "--source-id", "nonexistent", "--tracker", str(tracker)]):
        with patch.object(show_diff, "guard_main_branch", return_value=True):
            code = show_diff.main()
    assert code == 1


def test_main_no_vendored_path_lists_upstream(tmp_path):
    """Source không có vendored_path → liệt kê file upstream."""
    tracker = _write_tracker(tmp_path, {
        "id": "ahd-main-engine", "type": "repo",
        "url": "https://github.com/owner/repo", "branch": "main",
        "vendored_path": "",
    })
    upstream_tmp = tmp_path / "ahd-upstream"
    upstream_tmp.mkdir()
    (upstream_tmp / "README.md").write_text("# readme", encoding="utf-8")

    with patch("sys.argv", ["show_diff.py", "--source-id", "ahd-main-engine", "--tracker", str(tracker)]):
        with patch.object(show_diff, "guard_main_branch", return_value=True):
            with patch.object(show_diff, "clone_repo", return_value=True):
                with patch.object(show_diff, "REPO_ROOT", tmp_path):
                    code = show_diff.main()
    assert code == 0


def test_main_with_vendored_path_diff(tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill",
        "url": "https://github.com/owner/repo", "branch": "main",
        "vendored_path": "test-skill/",
    })
    target = tmp_path / "test-skill"
    target.mkdir()
    (target / "SKILL.md").write_text("# local version", encoding="utf-8")

    upstream_tmp = tmp_path / "test-skill-diff"
    upstream_tmp.mkdir()
    (upstream_tmp / "SKILL.md").write_text("# upstream version", encoding="utf-8")

    with patch("sys.argv", ["show_diff.py", "--source-id", "test-skill", "--tracker", str(tracker)]):
        with patch.object(show_diff, "guard_main_branch", return_value=True):
            with patch.object(show_diff, "clone_repo", return_value=True):
                with patch.object(show_diff, "REPO_ROOT", tmp_path):
                    code = show_diff.main()
    assert code == 0


def test_main_tracker_not_found(tmp_path):
    with patch("sys.argv", ["show_diff.py", "--source-id", "x", "--tracker", str(tmp_path / "missing.json")]):
        with patch.object(show_diff, "guard_main_branch", return_value=True):
            with pytest.raises(SystemExit):
                show_diff.load_tracker(tmp_path / "missing.json")


def test_main_clone_failure(tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill",
        "url": "https://github.com/owner/repo", "branch": "main",
        "vendored_path": "test-skill/",
    })
    target = tmp_path / "test-skill"
    target.mkdir()

    with patch("sys.argv", ["show_diff.py", "--source-id", "test-skill", "--tracker", str(tracker)]):
        with patch.object(show_diff, "guard_main_branch", return_value=True):
            with patch.object(show_diff, "clone_repo", return_value=False):
                code = show_diff.main()
    assert code == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
