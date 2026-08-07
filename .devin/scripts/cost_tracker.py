#!/usr/bin/env python3
"""cost_tracker.py — U17: Track cumulative cost per session + enforce cost cap.

Called by post_tool_use.py after each tool call to estimate cost and
check against the session's cost_cap. If cost exceeds cap, flag for
human notification.

Cost estimation is rough (based on token counts in tool response) —
not a billing system, just a guardrail against budget overrun.

Usage (inline):
    from cost_tracker import track_tool_cost, check_cost_cap_session
    track_tool_cost(root, session_id, tool_name, response_size)
    exceeded, msg = check_cost_cap_session(root, session_id)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

try:
    import ahd_session
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session

# Rough cost estimates per 1K tokens (USD) — conservative averages
# Source: public pricing pages, 2026-07
COST_PER_1K_TOKENS = {
    "input": 0.003,   # ~$3/MTok average input
    "output": 0.015,  # ~$15/MTok average output
}

# Default cost cap per task (USD) — can be overridden in session_state
DEFAULT_COST_CAP = 5.0

# Rough estimate: 1 char ≈ 0.25 tokens (4 chars per token average)
CHARS_PER_TOKEN = 4


def _estimate_cost(tool_name: str, response_size: int) -> float:
    """Rough cost estimate for a single tool call.

    Assumes response_size chars ≈ response_size/4 tokens of output.
    Adds a small fixed overhead per call for input tokens.
    """
    output_tokens = response_size / CHARS_PER_TOKEN
    output_cost = (output_tokens / 1000) * COST_PER_1K_TOKENS["output"]
    # Input overhead: ~500 tokens per tool call (prompt + context)
    input_cost = (500 / 1000) * COST_PER_1K_TOKENS["input"]
    return round(output_cost + input_cost, 6)


def track_tool_cost(root: Path, session_id: str, tool_name: str, response_size: int) -> dict:
    """U17: Track cost of a tool call in session_state.

    Updates cumulative_cost in session_state. Returns the updated cost info.
    """
    if not session_id:
        return {"tracked": False, "reason": "no session_id"}

    # Pentest fix: response_size âm không hợp lệ — không cho giảm cumulative cost.
    if response_size < 0:
        response_size = 0

    cost = _estimate_cost(tool_name, response_size)

    # Read current state
    state = ahd_session.read_session_state(session_id, root)
    cumulative = state.get("cumulative_cost", 0.0)
    cost_cap = state.get("cost_cap", DEFAULT_COST_CAP)
    call_count = state.get("cost_tracked_calls", 0)

    cumulative = round(cumulative + cost, 6)
    call_count += 1

    # Update session_state
    ahd_session.update_session_state(session_id, {
        "cumulative_cost": cumulative,
        "cost_cap": cost_cap,
        "cost_tracked_calls": call_count,
        "last_tool_cost": cost,
    }, root)

    return {
        "tracked": True,
        "tool": tool_name,
        "estimated_cost": cost,
        "cumulative_cost": cumulative,
        "cost_cap": cost_cap,
        "calls_tracked": call_count,
    }


def check_cost_cap(state: dict) -> int:
    """U17/T2.4: Kiểm tra cost cap từ state.

    Trả về mã:
      0 — OK (dưới 80%)
      1 — WARN (từ 80% đến dưới 100%)
      2 — BLOCK (đã đạt hoặc vượt cost_cap)
    """
    cumulative = float(state.get("cumulative_cost", 0.0))
    cost_cap = float(state.get("cost_cap", DEFAULT_COST_CAP))
    # Pentest fix: cap âm hoặc NaN là giá trị không hợp lệ — không được bypass.
    # Cap <= 0 với cumulative > 0 nghĩa là đã vượt cap -> block.
    # Cap NaN: mọi so sánh đều False -> phải block để tránh bypass.
    if math.isnan(cost_cap) or math.isinf(cost_cap) and cost_cap < 0:
        return 2
    if cost_cap < 0:
        # Cap âm không hợp lệ; nếu đã tiêu cost thì block.
        return 2 if cumulative > 0 else 2
    if cost_cap == 0:
        # Cap 0: nếu đã tiêu bất kỳ cost nào -> đã vượt cap -> block.
        return 2 if cumulative > 0 else 0
    ratio = cumulative / cost_cap
    if cumulative >= cost_cap or ratio >= 1.0:
        return 2
    if ratio >= 0.8:
        return 1
    return 0


def check_cost_cap_session(root: Path, session_id: str) -> tuple[bool, str]:
    """U17: Kiểm tra cumulative cost theo root + session_id.

    Giữ lại để tương thích với post_tool_use.py. Trả (exceeded, message).
    """
    if not session_id:
        return False, ""

    state = ahd_session.read_session_state(session_id, root)
    status = check_cost_cap(state)
    cumulative = float(state.get("cumulative_cost", 0.0))
    cost_cap = float(state.get("cost_cap", DEFAULT_COST_CAP))

    if status == 2:
        msg = (
            f"COST CAP EXCEEDED: ${cumulative:.4f} >= ${cost_cap:.4f} cap. "
            f"Stop escalation. Ask human whether to continue or stop. "
            f"Session: {session_id}, calls tracked: {state.get('cost_tracked_calls', 0)}"
        )
        ahd_session.update_session_state(session_id, {
            "cost_cap_exceeded": True,
        }, root)
        return True, msg

    if status == 1:
        msg = (
            f"COST CAP WARNING: ${cumulative:.4f} approaching ${cost_cap:.4f} cap (80%). "
            f"Consider wrapping up or asking human for budget increase."
        )
        return False, msg

    return False, ""


def set_cost_cap(root: Path, session_id: str, cap: float) -> None:
    """U17: Set cost cap for a session (called at BOOT or by user)."""
    if not session_id:
        return
    ahd_session.update_session_state(session_id, {
        "cost_cap": cap,
    }, root)


if __name__ == "__main__":
    # CLI: check cost for a session
    import argparse
    ap = argparse.ArgumentParser(description="U17: Cost cap tracker")
    ap.add_argument("--session", required=True, help="Session ID")
    ap.add_argument("--check", action="store_true", help="Check if cost cap exceeded")
    ap.add_argument("--set-cap", type=float, help="Set cost cap (USD)")
    args = ap.parse_args()

    root = ahd_session.get_repo_root()
    if args.set_cap is not None:
        set_cost_cap(root, args.session, args.set_cap)
        print(f"Cost cap set to ${args.set_cap:.2f} for session {args.session}")
    if args.check:
        exceeded, msg = check_cost_cap_session(root, args.session)
        if exceeded:
            print(f"[!] {msg}")
            sys.exit(1)
        elif msg:
            print(f"[WARN] {msg}")
        else:
            state = ahd_session.read_session_state(args.session, root)
            print(f"OK: ${state.get('cumulative_cost', 0):.4f} / ${state.get('cost_cap', DEFAULT_COST_CAP):.4f}")
