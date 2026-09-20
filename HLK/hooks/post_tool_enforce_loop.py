"""Enforcement hooks U60-U62: loop enforcement, state-write verify, memory confidence.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import ahd_session

from post_tool_config import (HOOK_TIMEOUT_SECONDS, MAX_ITERATIONS_WITHOUT_STATE_WRITE, MIN_COMPRESSION_THRESHOLD, MAX_OUTPUT_SIZE_COMPRESSION, DEFAULT_COMPRESSION_THRESHOLD, MAX_FAILURE_THRESHOLD, _CONTEXT_FLAGS_CACHE, _CONTEXT_FLAGS_LOADED, _STATE_WRITE_COUNTER, _STATE_WRITE_BATCH, CONTEXT_OVERSIZE_THRESHOLD, CANDIDATE_MEMORY_MAX, VALID_CORRECT_ACTIONS, CANDIDATE_MEMORY_PER_HOUR, CANDIDATE_MEMORY_WINDOW_SECONDS, _SECRET_PATTERNS)

def _u60_loop_enforcement(data: dict, session_id: str, root: Path) -> None:
    """Enforce loop stop conditions: budget cap, time limit, state write."""
    state = ahd_session.read_session_state(session_id, root)

    # Check budget cap (token cost)
    total_cost = state.get("total_cost", 0)
    budget_cap = state.get("budget_cap", 0)
    if budget_cap > 0 and total_cost > budget_cap:
        ahd_session._locked_json_update(
            ahd_session.get_session_state_path(session_id, root),
            lambda existing: {**(existing or {}), "budget_exceeded": True},
            default={},
            session_id=session_id,
        )

    # Check time limit
    started_at = state.get("started_at")
    time_limit = state.get("time_limit_seconds", 0)
    if started_at and time_limit > 0:
        try:
            start = datetime.fromisoformat(started_at)
            elapsed = (datetime.now(start.tzinfo) - start).total_seconds()
            if elapsed > time_limit:
                print(
                    f"[U60] TIME LIMIT EXCEEDED: {elapsed:.0f}s > {time_limit}s. "
                    f"Loop should stop.",
                    file=sys.stderr,
                )
        except (ValueError, TypeError, KeyError, AttributeError):
            pass

    # Check iteration count vs state writes
        except Exception as e:
            print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
            pass

    # Check iteration count vs state writes
    iteration_count = state.get("iteration_count", 0)
    last_state_write = state.get("last_state_write_iteration", 0)
    if iteration_count - last_state_write > MAX_ITERATIONS_WITHOUT_STATE_WRITE:
        print(
            f"[U60] WARNING: {iteration_count - last_state_write} iterations "
            f"without state write. Loop state may be stale.",
            file=sys.stderr,
        )

def _u61_state_write_verification(data: dict, session_id: str, root: Path) -> None:
    """Verify session state write succeeded by reading back."""
    state_path = ahd_session.get_session_state_path(session_id, root)
    if not state_path.exists():
        return

    try:
        content = state_path.read_text(encoding="utf-8")
        if not content.strip():
            # Empty file — write failure
            state = ahd_session.read_session_state(session_id, root)
            fail_count = state.get("state_write_failures", 0) + 1
            ahd_session._locked_json_update(
                state_path,
                lambda existing: {
                    **(existing or {}),
                    "state_write_failures": fail_count,
                },
                default={},
                session_id=session_id,
            )
            if fail_count > MAX_FAILURE_THRESHOLD:
                print(
                    f"[U61] CRITICAL: {fail_count} state write failures. "
                    f"Escalate to human.",
                    file=sys.stderr,
                )
    except (OSError, UnicodeDecodeError):
        pass


# U62: Memory confidence + honest limit
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

def _u62_memory_confidence(data: dict, session_id: str, root: Path) -> None:
    """Track memory confidence and enforce honest limit thresholds."""
    tool_name = data.get("tool_name", "").lower()

    # Only check on memory-related tools
    if "memory" not in tool_name and "recall" not in tool_name:
        return

    tool_response = data.get("tool_response", {})
    output = str(tool_response.get("output", "")) if isinstance(tool_response, dict) else str(tool_response)

    # Estimate confidence: if output is empty or very short, low confidence
    confidence = 100
    if not output.strip():
        confidence = 0
    elif len(output.strip()) < 50:
        confidence = 30

    # Check for uncertainty markers
    uncertainty_markers = [
        r"\b(might be|possibly|perhaps|maybe|uncertain|not sure|unclear)\b",
        r"\b(approximately|roughly|around)\b",
    ]
    uncertainty_count = 0
    for pattern in uncertainty_markers:
        uncertainty_count += len(re.findall(pattern, output, re.IGNORECASE))

    if uncertainty_count > MIN_COMPRESSION_THRESHOLD:
        confidence = min(confidence, 50)

    state_path = ahd_session.get_session_state_path(session_id, root)
    ahd_session._locked_json_update(
        state_path,
        lambda existing: {
            **(existing or {}),
            "last_memory_confidence": confidence,
            "last_memory_source": tool_name,
        },
        default={},
        session_id=session_id,
    )

    # U62: Honest limit — auto-escalate if uncertainty > 30%
    if confidence < MAX_OUTPUT_SIZE_COMPRESSION:
        print(
            f"[U62] Memory confidence low ({confidence}%). "
            f"Consider escalating to human. Honest limit threshold: 70%.",
            file=sys.stderr,
        )
