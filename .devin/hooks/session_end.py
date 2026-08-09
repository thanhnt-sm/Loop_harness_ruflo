#!/usr/bin/env python3
"""U70: SessionEnd hook — cleanup + memory save on session end.

Called by Devin CLI SessionEnd hook event. Saves session state + triggers memory sync.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ahd_session import get_session_state_path, get_repo_root, _locked_json_update, now_utc


def main() -> None:
    """U70: On session end, mark session as ended + trigger memory save."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        return

    except Exception:
        return

    session_id = data.get("session_id", "unknown")
    root = get_repo_root()

    state_path = get_session_state_path(session_id, root)
    _locked_json_update(
        state_path,
        lambda existing: {
            **(existing or {}),
            "session_ended": True,
            "session_ended_at": now_utc(),
        },
        default={},
        session_id=session_id,
    )

    # Output: inject context to remind agent to save memory
    output = {
        "hookSpecificOutput": {
            "SessionEnd": {
                "additionalContext": (
                    "[U70 SessionEnd] Session ending. "
                    "Save important context to aide-memory via aide_remember. "
                    "Run loop_memory_sync if needed."
                )
            }
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
