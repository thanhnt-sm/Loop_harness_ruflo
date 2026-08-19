#!/usr/bin/env python3
"""Kiểm thử an ninh cho check_updates.py — B310 URL guard."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _import():
    import check_updates
    return check_updates


def test_github_api_get_blocks_non_github_urls():
    mod = _import()
    res = mod.github_api_get("file:///etc/passwd")
    assert "error" in res
    assert "Blocked" in res["error"]

    res = mod.github_api_get("http://api.github.com/repos/x/y")
    assert "error" in res
    assert "Blocked" in res["error"]

    res = mod.github_api_get("https://evil.example.com/repos/x/y")
    assert "error" in res
    assert "Blocked" in res["error"]


def test_github_api_get_allows_github_urls():
    mod = _import()
    # Không gọi network thật — chỉ đảm bảo URL hợp lệ lọt qua guard.
    # (API sẽ trả HTTPError 404/403 với token rỗng, không phải "Blocked".)
    res = mod.github_api_get("https://api.github.com/repos/octocat/Hello-World/commits/main")
    assert "Blocked" not in res.get("error", "")


def test_parse_repo_url_variants():
    mod = _import()
    assert mod.parse_repo_url("https://github.com/owner/repo.git") == ("owner", "repo")
    assert mod.parse_repo_url("https://github.com/owner/repo") == ("owner", "repo")


def test_check_repo_invalid_url_marks_invalid():
    mod = _import()
    res = mod.check_repo({"url": "not-a-url"}, token="")
    assert res["status"] == "invalid-url"


# --- check_repo ---

def test_check_repo_up_to_date():
    mod = _import()
    source = {
        "id": "test", "type": "repo", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "abc1234", "current_commit_full": "abc1234def",
    }
    with patch.object(mod, "github_api_get", return_value={"sha": "abc1234def"}):
        res = mod.check_repo(source, token="")
    assert res["status"] == "up-to-date"
    assert res["upstream_commit"] == "abc1234"


def test_check_repo_behind():
    mod = _import()
    source = {
        "id": "test", "type": "repo", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "abc1234", "current_commit_full": "abc1234def",
    }
    with patch.object(mod, "github_api_get", return_value={"sha": "def5678ghijklm"}):
        res = mod.check_repo(source, token="")
    assert res["status"] == "behind"
    assert res["upstream_commit"] == "def5678"


def test_check_repo_canon_source_manual_review():
    mod = _import()
    source = {
        "id": "caveman", "type": "canon-source", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "unknown", "current_commit_full": "",
    }
    with patch.object(mod, "github_api_get", return_value={"sha": "abc1234def"}):
        res = mod.check_repo(source, token="")
    assert res["status"] == "manual-review"


def test_check_repo_api_error():
    mod = _import()
    source = {
        "id": "test", "type": "repo", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "abc1234", "current_commit_full": "abc1234def",
    }
    with patch.object(mod, "github_api_get", return_value={"error": "HTTP 403"}):
        res = mod.check_repo(source, token="")
    assert res["status"] == "api-error"


def test_check_repo_empty_current_commit():
    mod = _import()
    source = {
        "id": "test", "type": "repo", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "", "current_commit_full": "",
    }
    with patch.object(mod, "github_api_get", return_value={"sha": "abcdefg1234567"}):
        res = mod.check_repo(source, token="")
    assert res["status"] == "behind"


def test_check_repo_vendored_skill_up_to_date():
    mod = _import()
    source = {
        "id": "nuwa-skill", "type": "vendored-skill", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "27642f5", "current_commit_full": "27642f5abcdef",
    }
    with patch.object(mod, "github_api_get", return_value={"sha": "27642f5abcdef"}):
        res = mod.check_repo(source, token="")
    assert res["status"] == "up-to-date"
