#!/usr/bin/env python3
"""cross_family_verify.py — Hook PostToolUse: enforce cross-family verification.

V9 fix: VERIFICATION_PROTOCOL U10 yêu cầu cross-family verifier cho L/XL.
Hook này check producer_model khi agent mark task "complete".
Nếu verifier cùng family → warning (advisory). Cho L/XL → block.

Input (stdin JSON):
  {"tool_name": "Write", "tool_input": {...}, "tool_output": {...},
   "session_id": "...", "session_state": {"tier": "XL", "producer_model": "glm-5.2"}}

Exit codes: 0=allow, 2=block
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Model families
MODEL_FAMILIES = {
    "glm": {"glm-5.2", "glm-5.2-high", "glm-4.6", "glm-4", "chatglm"},
    "claude": {"claude-3.5", "claude-3.7", "claude-4", "claude-opus", "claude-sonnet"},
    "gpt": {"gpt-4", "gpt-4o", "gpt-5", "o1", "o3"},
    "kimi": {"kimi-k2", "kimi-k2.7"},
    "gemini": {"gemini-1.5", "gemini-2", "gemini-2.5"},
    "llama": {"llama-3", "llama-4", "llama-405b"},
    "qwen": {"qwen-2.5", "qwen-3"},
    "deepseek": {"deepseek-v3", "deepseek-r1"},
}


def _get_family(model: str) -> str:
    """Trả về family của model (lowercase match)."""
    model_lower = model.lower().strip()
    for family, models in MODEL_FAMILIES.items():
        if model_lower in models:
            return family
        # Partial match
        if family in model_lower:
            return family
    return "unknown"


def _is_cross_family(producer: str, verifier: str) -> bool:
    """Kiểm tra producer và verifier có khác family không."""
    return _get_family(producer) != _get_family(verifier)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        print(json.dumps({"allow": True, "reason": "parse error, allow"}))
        sys.exit(0)

    session_state = data.get("session_state", {})
    tier = session_state.get("tier", "M")
    producer_model = session_state.get("producer_model", "")
    verifier_model = session_state.get("verifier_model", os.environ.get("AHD_MODEL", ""))

    # Nếu không có producer/verifier → skip
    if not producer_model or not verifier_model:
        print(json.dumps({"allow": True, "reason": "no model info to verify"}))
        sys.exit(0)

    same_family = not _is_cross_family(producer_model, verifier_model)

    if same_family:
        family = _get_family(producer_model)
        if tier in ("L", "XL"):
            # L/XL + same family → BLOCK (require cross-family hoặc strong anchor)
            print(json.dumps({
                "allow": False,
                "reason": f"CROSS-FAMILY VERIFY: L/XL task verified by same family ({family}). "
                          f"Producer={producer_model}, Verifier={verifier_model}. "
                          f"Require cross-family verifier hoặc strong anchor.",
                "enforcement": "cross_family_required",
            }))
            sys.exit(2)
        else:
            # M-tier + same family → advisory warning
            print(json.dumps({
                "allow": True,
                "reason": f"CROSS-FAMILY VERIFY: advisory — same family ({family}) for M-tier",
                "enforcement": "cross_family_advisory",
            }))
            sys.exit(0)

    # Cross-family → OK
    print(json.dumps({
        "allow": True,
        "reason": f"cross-family verify OK: {_get_family(producer_model)} → {_get_family(verifier_model)}",
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
