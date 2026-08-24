#!/usr/bin/env python3
"""harness_upgrade_state.py — State management cho harness upgrade loop.

Chứa _load_state, _save_state, _find_log_iteration.
"""

from __future__ import annotations

import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Thêm thư mục .devin/scripts để import khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_upgrade_constants import REPO_ROOT, LOOP_STATE_DIR, LOOP_STATE_FILE, LOOP_LOG_FILE, LOG_FILE


def _find_log_iteration() -> int:
    """Tìm iteration lớn nhất trong harness-upgrade-log.md, dùng để đặt tên upgrade."""
    if not LOG_FILE.exists():
        return 1
    text = LOG_FILE.read_text(encoding="utf-8")
    nums = [int(m) for m in re.findall(r"^# ITERATION (\d+)", text, re.MULTILINE)]
    return max(nums, default=0) + 1


def _load_state() -> dict:
    """Đọc loop state."""
    if LOOP_STATE_FILE.exists():
        try:
            return json.loads(LOOP_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "iteration": 0,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "cumulative_cost_usd": 0.0,
        "last_improvement_iteration": 0,
        "failures_history": [],
        "status": "in_progress",
        "phase": "normal",
    }


def _save_state(state: dict) -> None:
    """Ghi loop state JSON và markdown tóm tắt."""
    LOOP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOOP_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    md = f"""# Harness Upgrade Loop State

- loop_iteration: {state.get('loop_iteration', 0)}
- log_iteration: {state.get('log_iteration', 0)}
- phase: {state.get('phase', 'normal')}
- status: {state.get('status', 'in_progress')}
- start_time: {state.get('start_time', '')}
- baseline: {state.get('passed', 0)} passed / {state.get('failed', 0)} failed / {state.get('skipped', 0)} skipped
- target: `{state.get('target', 'N/A')}`
- state_file: `{state.get('plan_state_file', 'N/A')}`
- stop_reason: {state.get('stop_reason', 'None')}
- next_action: `{state.get('next_action', 'N/A')}`
"""
    LOOP_LOG_FILE.write_text(md, encoding="utf-8")