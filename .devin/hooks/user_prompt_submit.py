#!/usr/bin/env python3
"""U70: UserPromptSubmit hook — inject context on user prompt.

Called by Devin CLI UserPromptSubmit hook event. Injects harness context reminders.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ahd_session import get_session_state_path, get_repo_root, _locked_json_update, now_utc, read_session_state


def main() -> None:
    """U70: On user prompt, inject context about harness state."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    session_id = data.get("session_id", "unknown")
    prompt = data.get("prompt", "")
    root = get_repo_root()

    # Read session state for context
    state = read_session_state(session_id, root)

    # Build context injection
    context_parts = []

    # Check if BOOT is complete
    if not state.get("boot_complete", True):
        context_parts.append(
            "[U70] BOOT protocol not yet complete. "
            "Complete BOOT steps before working on tasks."
        )

    # Check if done was declared but not verified
    if state.get("fable_judge_required"):
        context_parts.append(
            "[U70] Previous task declared done but fable-judge verification pending. "
            "Verify before starting new work."
        )

    # Check circuit breakers
    tripped = state.get("circuit_breakers_tripped", [])
    if tripped:
        context_parts.append(
            f"[U70] Circuit breakers tripped: {tripped}. "
            f"Minimal mode may be active."
        )

    # Check memory confidence
    confidence = state.get("last_memory_confidence", 100)
    if confidence < 70:
        context_parts.append(
            f"[U70] Last memory confidence low ({confidence}%). "
            f"Verify recalled information before acting."
        )

    # Update prompt count
    state_path = get_session_state_path(session_id, root)
    _locked_json_update(
        state_path,
        lambda existing: {
            **(existing or {}),
            "prompt_count": ((existing or {}).get("prompt_count", 0)) + 1,
            "last_prompt_at": now_utc(),
        },
        default={},
        session_id=session_id,
    )

    if context_parts:
        output = {
            "hookSpecificOutput": {
                "UserPromptSubmit": {
                    "additionalContext": "\n".join(context_parts)
                }
            }
        }
        print(json.dumps(output))


if __name__ == "__main__":
    main()
