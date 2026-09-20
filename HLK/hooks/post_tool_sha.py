"""Theo doi SHA-256 cua file sau moi luot write/edit (U20).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import ahd_session

from post_tool_config import (HOOK_TIMEOUT_SECONDS, MAX_ITERATIONS_WITHOUT_STATE_WRITE, MIN_COMPRESSION_THRESHOLD, MAX_OUTPUT_SIZE_COMPRESSION, DEFAULT_COMPRESSION_THRESHOLD, MAX_FAILURE_THRESHOLD, _CONTEXT_FLAGS_CACHE, _CONTEXT_FLAGS_LOADED, _STATE_WRITE_COUNTER, _STATE_WRITE_BATCH, CONTEXT_OVERSIZE_THRESHOLD, CANDIDATE_MEMORY_MAX, VALID_CORRECT_ACTIONS, CANDIDATE_MEMORY_PER_HOUR, CANDIDATE_MEMORY_WINDOW_SECONDS, _SECRET_PATTERNS)

def _compute_sha256(file_path: str, root: Path) -> str:
    """U20: Compute SHA-256 of a file. Returns empty string if file doesn't exist."""
    import hashlib
    try:
        full_path = (root / file_path) if not Path(file_path).is_absolute() else Path(file_path)
        if full_path.exists() and full_path.is_file():
            # U20 redteam: chunked reading for large files (64KB chunks)
            sha256 = hashlib.sha256()
            with open(full_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
    except (OSError, UnicodeDecodeError):
        pass
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
    return ""

def _track_file_sha(session_id: str, file_path: str, tool_name: str, root: Path) -> None:
    """U20: Track file SHA + invalidate verification status on write.

    For write/edit tools: compute SHA after write, store in session_state,
    and invalidate previous verify_status for that file.
    """
    if not file_path or not session_id:
        return

    write_tools = {"Write", "Edit", "write", "edit", "notebook_edit", "NotebookEdit"}
    if tool_name not in write_tools:
        return

    sha = _compute_sha256(file_path, root)
    if not sha:
        return

    try:
        state = ahd_session.read_session_state(session_id, root)
        file_shas = state.get("file_shas", {})
        verify_status = state.get("verify_status", {})

        # Update SHA
        file_shas[file_path] = {
            "sha": sha,
            "updated_at": ahd_session.now_utc(),
        }

        # Invalidate verification status for this file (always set on write)
        verify_status[file_path] = {
            "verified": False,
            "invalidated_at": ahd_session.now_utc(),
            "reason": "file modified after verification",
        }

        ahd_session.update_session_state(session_id, {
            "file_shas": file_shas,
            "verify_status": verify_status,
        }, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
