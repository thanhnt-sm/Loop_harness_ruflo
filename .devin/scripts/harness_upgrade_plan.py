#!/usr/bin/env python3
"""harness_upgrade_plan.py — Planning functions cho harness upgrade loop.

Chứa _plan_target.
"""

from __future__ import annotations

import sys
import json
from typing import Optional
from pathlib import Path

# Thêm thư mục .devin/scripts để import khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_upgrade_utils import _python, _run


def _plan_target(target: str) -> dict:
    """Gọi plan_orchestrator để lập kế hoạch cho target."""
    task = f"fix {target}"
    print(f"[harness_upgrade_loop] Khởi tạo plan cho target: {target}")
    rc, out, err = _run([_python(), ".devin/scripts/plan_orchestrator.py", "--init", "--task", task], timeout=60)
    if rc != 0:
        print(f"[harness_upgrade_loop] plan_orchestrator lỗi: {err}", file=__import__("sys").stderr)
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"[harness_upgrade_loop] Không parse được output plan: {out[:200]}", file=__import__("sys").stderr)
        return {}