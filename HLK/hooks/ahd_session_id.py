#!/usr/bin/env python3
"""Session ID utilities for ahd_session.

Provides:
- get_repo_root: Find the main repo root with caching
- slugify_session_id: Make filesystem-safe session id slug
- get_session_id: Resolve session_id with fallback chain
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


# Cache for git rev-parse result (avoid repeated subprocess calls)
_REPO_ROOT_CACHE: Optional[Path] = None
_REPO_ROOT_CACHE_LOCK = threading.RLock()


def get_repo_root(start_from: Optional[Path] = None) -> Path:
    """Find the main repo root.

    1. Try git rev-parse --show-toplevel.
    2. Walk up from start_from (default cwd) for .git, .agents, AGENTS.md, pyproject.toml, README.md.
    3. Fallback to cwd.

    Caches result to avoid repeated git rev-parse subprocess calls.
    """
    global _REPO_ROOT_CACHE
    with _REPO_ROOT_CACHE_LOCK:
        if _REPO_ROOT_CACHE is not None and start_from is None:
            return _REPO_ROOT_CACHE

    cwd = Path(start_from) if start_from else Path.cwd()
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=str(cwd)
        )
        if r.returncode == 0 and r.stdout.strip():
            result = Path(r.stdout.strip())
            if start_from is None:
                with _REPO_ROOT_CACHE_LOCK:
                    _REPO_ROOT_CACHE = result
            return result
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    # Không dùng .agents làm marker vì thư mục home của user cũng có thể có .agents,
    # gây nhầm repo root khi chạy test trong tmp_path không phải git repo.
    for parent in [cwd, *cwd.parents]:
        for marker in (".git", "AGENTS.md", "pyproject.toml", "README.md"):
            if (parent / marker).exists():
                if start_from is None:
                    with _REPO_ROOT_CACHE_LOCK:
                        _REPO_ROOT_CACHE = parent
                return parent
    if start_from is None:
        with _REPO_ROOT_CACHE_LOCK:
            _REPO_ROOT_CACHE = cwd
    return cwd


def slugify_session_id(sid: str, max_len: int = 64) -> str:
    """Make a filesystem-safe session id slug.

    Empty session_id gets random UUID suffix to avoid
    collision on per-session lock files.
    """
    if not sid:
        sid = f"unknown-{uuid.uuid4().hex[:8]}"
    # Replace separators and illegal chars
    sid = re.sub(r"[:/\\\s|<>\"'?*\"]+", "-", sid)
    sid = re.sub(r"-+", "-", sid)
    sid = sid.strip("-.")
    if not sid:
        sid = f"unknown-{uuid.uuid4().hex[:8]}"
    sid = sid[:max_len]
    return sid


def get_session_id(data: Optional[Dict[str, Any]] = None, env_prefix: str = "AHD") -> str:
    """Resolve session_id with fallback chain.

    1. tool input `data["session_id"]`
    2. env var `{env_prefix}_SESSION_ID`
    3. file `.devin/session_state/current_session`
    4. UUID
    """
    data = data or {}
    sid = data.get("session_id", "")
    if sid:
        return slugify_session_id(sid)

    sid = os.environ.get(f"{env_prefix}_SESSION_ID", "")
    if sid:
        return slugify_session_id(sid)

    # Racy fallback: read current_session file
    try:
        root = get_repo_root()
        from ahd_session_paths import get_config_root

        current_file = get_config_root(root) / "session_state" / "current_session"
        if current_file.exists():
            sid = current_file.read_text(encoding="utf-8").strip()
            if sid:
                return slugify_session_id(sid)
    except (OSError, ValueError):
        pass

    return slugify_session_id(str(uuid.uuid4()))