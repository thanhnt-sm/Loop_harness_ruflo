#!/usr/bin/env python3
"""U56: SessionStart hook — BOOT enforcement.

Verifies that BOOT protocol steps are completed before allowing work tools.
Sets boot_complete in session_state. Blocks work tools until BOOT complete.

Usage: Called by Devin CLI SessionStart hook event.
Stdin: {"session_id": "...", "prompt_id": "..."}
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add hooks dir to path for ahd_session
sys.path.insert(0, str(Path(__file__).parent))
from ahd_session import get_session_state_path, get_repo_root, _locked_json_update


def main() -> None:
    """U56: On session start, initialize boot_complete=false in session_state."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # can't parse, don't block

    session_id = data.get("session_id", "unknown")
    root = get_repo_root()

    # Initialize boot_complete=false — must be set true by BOOT protocol
    state_path = get_session_state_path(session_id, root)
    _locked_json_update(
        state_path,
        lambda existing: {
            **(existing or {}),
            "boot_complete": False,
            "boot_started_at": data.get("prompt_id", ""),
            "boot_steps_verified": [],
        },
        default={},
        session_id=session_id,
    )

    # Output: inject context to remind agent of BOOT protocol
    output = {
        "hookSpecificOutput": {
            "SessionStart": {
                "additionalContext": (
                    "[U56 BOOT Enforcement] Session started. "
                    "BOOT protocol MUST be completed before work tools. "
                    "Set boot_complete=true in session_state after BOOT steps verified. "
                    "Work tools (exec, write, edit) will be blocked until boot_complete=true."
                )
            }
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
