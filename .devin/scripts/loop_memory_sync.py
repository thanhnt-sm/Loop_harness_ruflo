#!/usr/bin/env python3
"""loop_memory_sync.py — Entry point for loop memory synchronization.

This is the single machine writer of `.devin/loop_state.md`. It reads:
- `.devin/session_state/*.json` for active session metadata
- `.devin/loop_state/<session_id>.md` for human-readable GoalSpec and subtasks

It writes:
- `.devin/loop_state.md` registry (active + recent 3 completed)
- `.devin/loop_state_archive.md` event summaries for archived sessions
- moves completed session files to `.devin/loop_state_archive/<session_id>.md`

Public API (unchanged):
- append_state_log
- verify_state_log
- watchdog_status
- regenerate
- run_inline
- main
"""

# Re-export all public APIs from submodules
from loop_memory_state_log import (  # type: ignore[import-not-found]
    _state_log_path,
    _telemetry_signing_key,
    _sign_entry,
    _verify_entry_sig,
    _chain_hash,
    append_state_log,
    verify_state_log,
)

from loop_memory_watchdog import watchdog_status  # type: ignore[import-not-found]

from loop_memory_fallback import (  # type: ignore[import-not-found]
    _write_fallback,
    _safe_regenerate,
)

from loop_memory_registry import (  # type: ignore[import-not-found]
    _parse_front_matter,
    _read_loop_state_md,
    _build_registry,
    _enforce_active_session_limit,
    _archive_session,
    _cleanup_loop_state_dir,
    _is_stale,
    regenerate,
)

from loop_memory_inline import (  # type: ignore[import-not-found]
    _inline_lock,
    run_inline,
)

from loop_memory_cli import main  # type: ignore[import-not-found]

# Constants (kept for backward compatibility)
MAX_REGISTRY_COMPLETED = 3
MAX_ACTIVE_SESSIONS = 3
MAX_LOOP_STATE_FILES = 10
STALE_THRESHOLD_SECONDS = 1800  # 30 minutes
ACTIVE_STATUSES = ("in_progress", "crashed", "suspected_crashed")

# U06: Fallback paths for Memory Keeper single-point-of-failure
FALLBACK_DIR_NAME = "loop_state_fallback"
FALLBACK_REGISTRY_NAME = "loop_state_fallback.md"

# Task 3.9: Immutable state log (append-only Merkle chain) + Ed25519 signing
STATE_LOG_NAME = "state_log.jsonl"


if __name__ == "__main__":
    import sys
    sys.exit(main())