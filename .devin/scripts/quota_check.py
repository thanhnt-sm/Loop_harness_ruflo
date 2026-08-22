#!/usr/bin/env python3
"""quota_check.py — Kiểm tra subagent quota trước khi dispatch.

V2 fix: khi subagent quota hết, harness phải có degraded mode
(main agent tự làm thay subagent) thay vì collapse hoàn toàn.

Check mechanism: thử dispatch 1 test subagent nhỏ. Nếu fail → quota exhausted.
FSM sẽ check trước mỗi dispatch_* action và switch sang degraded mode.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def check_quota() -> dict:
    """Kiểm tra subagent quota availability.

    Returns:
        {"available": bool, "reason": str}

    Strategy:
      1. Nếu AHD_QUOTA_FORCE=exhausted env → trả exhausted (test mode)
      2. Nếu AHD_QUOTA_FORCE=available env → trả available (test mode)
      3. Default: trả available (không thể check thật mà không dispatch)
         — FSM sẽ phát hiện quota hết khi dispatch fail và switch sang degraded
    """
    # Test mode: force exhausted
    force = os.environ.get("AHD_QUOTA_FORCE", "").lower()
    if force == "exhausted":
        return {"available": False, "reason": "quota_exhausted (forced)"}
    if force == "available":
        return {"available": True, "reason": "available (forced)"}

    # Default: available — FSM sẽ catch dispatch failure và switch sang degraded
    return {"available": True, "reason": "assumed_available"}


def is_degraded_mode(state: dict) -> bool:
    """Kiểm tra state có đang ở degraded mode không."""
    return bool(state.get("degraded_mode", False))


def should_switch_to_degraded(quota_result: dict) -> bool:
    """Quyết định có nên switch sang degraded mode không."""
    return not quota_result.get("available", True)


def degraded_mode_requirements() -> list[str]:
    """Trả về danh sách requirements cho degraded mode.

    Degraded mode KHÔNG skip adversarial review — main agent phải tự play
    các personas (Saboteur, Security Auditor, Architect) thay vì dispatch.
    """
    return [
        "adversarial_self_review: main agent phải tự review với 3+ perspectives",
        "Saboteur: 'How do I break this?'",
        "Security Auditor: 'Can an attacker exploit this?'",
        "Architect: 'Is this scalable and maintainable?'",
        "Flag degraded_mode=true trong state",
        "Report phải ghi rõ degraded mode được sử dụng",
    ]


if __name__ == "__main__":
    result = check_quota()
    print(f"Quota check: {result}")
