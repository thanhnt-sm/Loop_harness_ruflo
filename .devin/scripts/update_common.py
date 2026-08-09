#!/usr/bin/env python3
"""
update_common.py — shared utilities for update-merge scripts.

Cung cấp các hàm dùng chung cho `apply_ahd_patch.py`, `merge_updates.py`,
`check_updates.py`, `show_diff.py`, `qa_doc_audit.py`:
- REPO_ROOT resolution with marker validation
- subprocess helper
- glob / protected pattern matching
- tracker load/save with error handling
- git URL validation
- chunked file hash
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# REPO_ROOT: từ `.devin/scripts/update_common.py` -> repo root là parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]

# Validate repo root bằng marker files
_MARKER_FILES = [".devin/AGENTS.md", "REPOS.md", ".git"]
if not any((REPO_ROOT / m).exists() for m in _MARKER_FILES):
    raise RuntimeError(
        f"[CRITICAL] Cannot resolve REPO_ROOT: none of {_MARKER_FILES} found at {REPO_ROOT}"
    )

# Constants
REPOS_TRACKER = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"

# Patterns bảo vệ mặc định — đảm bảo không đụng các file/thư mục nhạy cảm
DEFAULT_PROTECTED_PATTERNS = [
    ".env",
    "*.pem",
    "*.key",
    "secrets/**",
    "credentials/**",
    "HLK/**",
    ".devin/hooks/**",
    ".devin/config.json",
    ".devin/mcp_config.json",
    ".devin/canon/BOOT_PROTOCOL.md",
    ".devin/canon/CORE_CANON.md",
    ".devin/canon/REDLINES.md",
    ".devin/AGENTS.md",
    ".devin/AGENTS_full.md",
    ".claude/settings.json",
    ".gitignore",
    ".gitattributes",
]

# Allowed git URL schemes; block file://, git://, http://, etc.
ALLOWED_GIT_SCHEMES = ("https://",)
TRUSTED_GIT_HOSTS = ("github.com", "gitlab.com", "bitbucket.org")


def _normalize_pattern(pat: str) -> str:
    """Chuẩn hóa pattern: dấu `/` cuối thành `/**`, backslash thành slash."""
    pat = pat.replace("\\", "/")
    if pat.endswith("/"):
        pat = pat[:-1] + "/**"
    return pat


def glob_match(name: str, pattern: str) -> bool:
    """Kiểm tra `name` khớp `pattern` dùng fnmatch (hỗ trợ *, ?, [seq])."""
    return fnmatch.fnmatch(name, pattern)


def is_protected(path: str, protected: list[str]) -> bool:
    """Kiểm tra path có khớp bất kỳ pattern nào trong danh sách protected không.

    Hỗ trợ:
    - exact match
    - prefix match với `/**` hoặc `/` cuối
    - glob patterns (`*.pem`, `secrets/**`, ...)
    """
    norm = Path(path).as_posix().replace("\\", "/").lstrip("./")
    for p in protected:
        pat = _normalize_pattern(p)
        if pat.endswith("/**"):
            prefix = pat[:-3]
            if norm == prefix or norm.startswith(prefix + "/"):
                return True
            continue
        if any(c in pat for c in "*?["):
            if glob_match(norm, pat):
                return True
            continue
        if norm == pat or norm.startswith(pat + "/"):
            return True
    return False


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 120,
    input_text: str = "",
) -> tuple[int, str, str]:
    """Chạy lệnh subprocess shell=False, trả (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return 1, "", f"Timeout after {timeout}s: {e}"
    except FileNotFoundError as e:
        return 127, "", f"Command not found: {e}"
    except Exception as e:
        return 1, "", f"Unexpected error: {e}"


def load_tracker(path: Path) -> dict[str, Any]:
    """Đọc tracker JSON với error handling rõ ràng."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Tracker not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Cannot read tracker {path}: {e}", file=sys.stderr)
        sys.exit(1)


def save_tracker(path: Path, data: dict[str, Any]) -> None:
    """Ghi tracker JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def file_hash(path: Path) -> str:
    """Tính SHA-256 theo chunk để tránh MemoryError với file lớn."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_git_url(url: str) -> tuple[bool, str]:
    """Validate URL git clone: chỉ cho https, chặn local/file protocols."""
    url = url.strip()
    if not any(url.startswith(s) for s in ALLOWED_GIT_SCHEMES):
        return False, f"Invalid URL scheme (only HTTPS allowed): {url}"
    # Block URLs with embedded credentials, fragments or query strings
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if "@" in parsed.netloc:
        return False, f"URL must not contain credentials: {url}"
    if parsed.hostname and parsed.hostname not in TRUSTED_GIT_HOSTS:
        return False, (
            f"Untrusted git host '{parsed.hostname}'. Allowed: "
            + ", ".join(TRUSTED_GIT_HOSTS)
        )
    return True, ""


def get_current_branch() -> str:
    """Trả về tên branch hiện tại."""
    code, out, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
    return out.strip() if code == 0 else "unknown"


def is_dirty_workspace() -> bool:
    """Trả về True nếu working tree có uncommitted changes."""
    code, out, _ = run_cmd(["git", "status", "--short"], cwd=REPO_ROOT)
    return bool(out.strip())


def guard_main_branch(force: bool) -> bool:
    """Chặn chạy trên main/master nếu force=False."""
    branch = get_current_branch()
    if branch in ("main", "master") and not force:
        print(
            f"[ERROR] This script must not run on '{branch}'. "
            "Use a feature branch or pass --force.",
            file=sys.stderr,
        )
        return False
    return True


def guard_clean_workspace(force: bool) -> bool:
    """Chặn chạy nếu workspace dirty, trừ khi --allow-dirty/--force."""
    if is_dirty_workspace() and not force:
        print(
            "[ERROR] Workspace has uncommitted changes. "
            "Commit/stash them or pass --force/--allow-dirty.",
            file=sys.stderr,
        )
        return False
    return True
