#!/usr/bin/env python3
"""Path resolution utilities for ahd_session.

Provides:
- get_config_root: Determine config root directory for runtime state files
- get_shared_state_root: Return canonical shared-state root (.agents/)
- resolve_shared_state_file: Resolve shared state file with backward-compat fallback
- get_session_state_path: Return path to session_state JSON
- get_context_flags_path: Return per-session context_flags path
- get_loop_state_path: Return per-session loop_state markdown path
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ahd_session_id import get_repo_root


def get_config_root(root: Path) -> Path:
    """Determine the config root directory for runtime state files.

    When deployed, this file lives at ``<config_root>/scripts/ahd_session.py`` or
    ``<config_root>/hooks/ahd_session.py``. The config root is ``parent.parent``.
    In the source repo (``.devin/scripts/ahd_session.py``) the parent.parent
    is ``core/assets/runtime/`` which is NOT a config root, so we fall back to
    ``root / ".agents"``.

    This is what makes the harness work across tools with different config roots:
    Antigravity uses ``.devin/``, Claude Code uses ``.claude/``, Codex uses
    ``.codex/``, etc. The canonical text references ``.devin/`` as a placeholder;
    at runtime this function resolves it to the actual deployed config root.

    Logic:
    - If passed `root` is the real repo root (from get_repo_root()), do deployed config root detection
    - Otherwise, use the passed `root` directly (test isolation)
    - Priority for test roots: .devin > .agents > session_state/loop_state > fallback to .agents
    """
    # Get the real repo root for comparison
    try:
        real_repo_root = get_repo_root()
    except Exception:
        real_repo_root = None

    # Xác định config root dựa trên marker thư mục trong `root`,
    # không dùng Path(__file__) để tránh lỗi khi get_repo_root bị monkeypatch trong test.
    # Ưu tiên: root/.devin > root/.agents > root/session_state > fallback root/.agents.
    if (root / ".devin" / "session_state").is_dir() or (root / ".devin" / "loop_state").is_dir():
        return root / ".devin"
    if (root / ".agents" / "session_state").is_dir() or (root / ".agents" / "loop_state").is_dir():
        return root / ".agents"
    if (root / "session_state").is_dir() or (root / "loop_state").is_dir():
        return root
    # Nếu thư mục .devin/.agents tồn tại nhưng chưa có session_state/loop_state
    # (bootstrap) thì vẫn ưu tiên theo thứ tự trên.
    if (root / ".devin").is_dir():
        return root / ".devin"
    if (root / ".agents").is_dir():
        return root / ".agents"

    # Fallback
    return root / ".agents"


def get_shared_state_root(root: Path) -> Path:
    """Return the canonical shared-state root (``<root>/.agents``).

    Shared state files (user_profile.md, knowledge_distill.md,
    handoff_letter.md, context_quick_lookup.md) live at ``.agents/`` and are
    shared across all tools. Per-tool session state (loop_state.md,
    session_state/, context_flags/) lives at the tool's config root.

    Backward compatibility: if a shared state file exists in the tool's config
    root but not in ``.agents/``, this function still returns ``.agents/``.
    The caller should use ``resolve_shared_state_file()`` for automatic
    migration fallback.
    """
    return root / ".agents"


def resolve_shared_state_file(filename: str, root: Path) -> Path:
    """Resolve a shared state file path with backward-compat fallback.

    Checks ``.devin/<filename>`` first (canonical location).
    Falls back to ``<config_root>/<filename>`` (old AHD location) if the
    canonical path doesn't exist but the old one does.

    Does NOT copy — callers that need to persist should write to
    ``get_shared_state_root(root) / filename``.
    """
    canonical = get_shared_state_root(root) / filename
    if canonical.exists():
        return canonical
    old = get_config_root(root) / filename
    if old.exists():
        return old
    return canonical  # default to canonical for new file creation


def _lock_relpath(root: Path) -> Path:
    """Return the repo-level lock file path (for registry writes)."""
    return get_config_root(root) / "tmp" / "ahd_session.lock"


def _session_lock_relpath(root: Path, session_id: str) -> Path:
    """Return a per-session lock file path.

    Per-session locks eliminate contention when multiple sessions
    write to different session_state files concurrently.
    """
    from ahd_session_id import slugify_session_id

    slug = slugify_session_id(session_id)
    return get_config_root(root) / "tmp" / f"ahd_session.{slug}.lock"


def get_session_state_path(session_id: str, root: Optional[Path] = None) -> Path:
    """Return path to session_state JSON."""
    root = root or get_repo_root()
    from ahd_session_id import slugify_session_id

    return get_config_root(root) / "session_state" / f"{slugify_session_id(session_id)}.json"


def get_context_flags_path(session_id: str, root: Optional[Path] = None) -> Path:
    """Return per-session context_flags path."""
    root = root or get_repo_root()
    from ahd_session_id import slugify_session_id

    return get_config_root(root) / "context_flags" / f"{slugify_session_id(session_id)}.json"


def get_loop_state_path(session_id: str, root: Optional[Path] = None) -> Path:
    """Return per-session loop_state markdown path."""
    root = root or get_repo_root()
    from ahd_session_id import slugify_session_id

    return get_config_root(root) / "loop_state" / f"{slugify_session_id(session_id)}.md"


def _get_lock_path(root: Path) -> Path:
    """Return a repo-level lock file path (for registry writes)."""
    return _lock_relpath(root)


def _get_session_lock_path(root: Path, session_id: str) -> Path:
    """Return a per-session lock file path (for session_state writes)."""
    return _session_lock_relpath(root, session_id)