#!/usr/bin/env python3
"""harness_upgrade_utils.py — Utility functions cho harness upgrade loop.

Chứa _python, _run, _check_stop, _is_plan_done.
"""

from __future__ import annotations

import sys
import json
import subprocess
import sys as sys_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Thêm thư mục .devin/scripts để import khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_upgrade_constants import REPO_ROOT, DEFAULT_CONVERGENCE


def _python() -> Path:
    """Tìm python executable ưu tiên .venv/bin/python rồi system python."""
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def _run(cmd: list[str | Path], timeout: int = 600) -> tuple[int, str, str]:
    """Chạy shell command, trả (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [str(c) for c in cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _check_stop(state: dict, args) -> Optional[str]:
    """Kiểm tra stop conditions. Không dừng khi all_tests_pass để cho phép audit.

    Giá trị 0 = vô hạn (bỏ qua condition đó).
    """
    if args.max_iterations and state["loop_iteration"] >= args.max_iterations:
        return f"max_iterations ({args.max_iterations})"

    start = datetime.fromisoformat(state["start_time"])
    elapsed_min = (datetime.now(timezone.utc) - start).total_seconds() / 60
    if args.max_time_min and elapsed_min >= args.max_time_min:
        return f"max_time ({args.max_time_min} min)"

    history = state.get("failures_history", [])
    if args.convergence and len(history) >= args.convergence:
        recent = history[-args.convergence:]
        if all(h == state["failed"] for h in recent):
            return f"convergence ({args.convergence} iterations no improvement)"
    return None


def _is_plan_done(state: dict) -> bool:
    """Kiểm tra plan state file đã DONE hay chưa."""
    plan_file = state.get("plan_state_file", "")
    if not plan_file:
        return True
    try:
        data = json.loads(Path(plan_file).read_text(encoding="utf-8"))
        return data.get("current_state") == "DONE" or data.get("state") == "DONE"
    except (OSError, json.JSONDecodeError):
        return True