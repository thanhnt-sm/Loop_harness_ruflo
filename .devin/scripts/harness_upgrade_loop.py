#!/usr/bin/env python3
"""harness_upgrade_loop.py — Driver cho loop nâng cấp workspace.

Mỗi lần chạy = 1 iteration:
  1. Đọc/ghi loop state.
  2. Chạy pytest để lấy baseline (có thể skip nếu đã có).
  3. Phân tích failures, chọn target theo priority.
  4. Nếu không có failure target, chạy audit (qa_doc, hook, sbom) để chọn
     proactive improvement target.
  5. Gọi plan_orchestrator --init --task để lập kế hoạch cho target.
  6. Ghi state và in next_action; kiểm tra stop conditions.

Usage:
    .venv/bin/python .devin/scripts/harness_upgrade_loop.py [--max-iterations N] [--max-time-min M] [--skip-baseline]
"""
from __future__ import annotations

import sys
import argparse
import sys as sys_module
import time
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

# Thêm thư mục .devin/scripts để import khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_upgrade_constants import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_TIME_MIN,
    DEFAULT_CONVERGENCE,
)
from harness_upgrade_state import _load_state, _save_state, _find_log_iteration
from harness_upgrade_target import (
    _pick_target,
    _pick_audit_target,
    _pick_proactive_target,
    _run_pytest_baseline,
)
from harness_upgrade_execute import (
    _build_execute_task,
    _changed_files,
    _revert_unauthorized_changes,
    _auto_execute_target,
    _get_target_coverage,
)
from harness_upgrade_plan import _plan_target
from harness_upgrade_utils import _check_stop, _is_plan_done


def _run_one_iteration(state: dict, args) -> bool:
    """Chạy một iteration của loop. Trả True nếu nên tiếp tục, False nếu dừng."""
    loop_iteration = state.get("loop_iteration", 0) + 1
    state["loop_iteration"] = loop_iteration
    state.setdefault("log_iteration", _find_log_iteration())
    if loop_iteration == 1:
        state["start_time"] = datetime.now(timezone.utc).isoformat()

    if not args.skip_baseline:
        passed, failed, skipped, failures = _run_pytest_baseline()
    else:
        passed = state.get("passed", 0)
        failed = state.get("failed", 0)
        skipped = state.get("skipped", 0)
        failures = state.get("failures", [])

    state.update({
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    })

    history = state.get("failures_history", [])
    history.append(failed)
    limit = args.convergence if args.convergence else 1000
    state["failures_history"] = history[-limit:]

    # Nếu đang có plan chưa DONE thì chờ (cho executor bên ngoài thực hiện)
    if not args.infinite and state.get("plan_state_file") and not _is_plan_done(state):
        print(f"[harness_upgrade_loop] Iteration {loop_iteration}: đang chờ plan hoàn thành -> {state['plan_state_file']}")
        _save_state(state)
        return True

    failed_targets = set(state.get("failed_targets", []))
    target = _pick_target(failures)
    if target and target in failed_targets:
        target = None
    if not target:
        state["phase"] = "audit"
        audit_target = _pick_audit_target()
        if audit_target and audit_target not in failed_targets:
            target = audit_target

    if not target:
        state["phase"] = "proactive"
        proactive_target = _pick_proactive_target(state, failed_targets)
        if proactive_target and proactive_target not in failed_targets:
            target = proactive_target

    if not target:
        if audit_target:
            state["phase"] = "audit"
        else:
            state["phase"] = "proactive"
        stop_reason = _check_stop(state, args)
        if stop_reason:
            state["status"] = "stopped"
            state["stop_reason"] = stop_reason
            _save_state(state)
            print(f"[harness_upgrade_loop] STOP: {stop_reason}")
            print(f"[harness_upgrade_loop] Baseline: {passed} passed / {failed} failed / {skipped} skipped")
            return False

    state["target"] = target or "wait"
    state["phase"] = state.get("phase", "normal")

    if args.infinite and target:
        # Trong --infinite, tự động thực thi target qua devin -p
        # Ghi coverage trước để so sánh sau
        before_cov: Optional[float] = None
        if target.startswith("proactive:"):
            before_cov = _get_target_coverage(target)
            attempts = state.setdefault("proactive_attempts", {})
            if before_cov is not None:
                attempts[target] = before_cov

        rc, out, err = _auto_execute_target(target, timeout=1800)
        if rc == 0:
            print("[harness_upgrade_loop] Auto-execute thành công.")
            # Với proactive target, kiểm tra coverage đã tăng chưa
            if target.startswith("proactive:"):
                after_cov = _get_target_coverage(target)
                if after_cov is None or (before_cov is not None and after_cov <= before_cov):
                    print(f"[harness_upgrade_loop] Coverage không cải thiện ({before_cov}% -> {after_cov}%), đánh dấu failed target.", file=sys.stderr)
                    state["failed_targets"] = state.get("failed_targets", []) + [target]
                else:
                    print(f"[harness_upgrade_loop] Coverage cải thiện từ {before_cov}% lên {after_cov}%")
                    state["last_improvement_iteration"] = loop_iteration
            else:
                state["last_improvement_iteration"] = loop_iteration
            # Xóa target cũ để iteration sau tìm target mới
            state.pop("target", None)
            state.pop("plan_state_file", None)
            state.pop("next_action", None)
            state.pop("plan_output", None)
        else:
            print(f"[harness_upgrade_loop] Auto-execute thất bại (rc={rc}).", file=sys.stderr)
            # Đánh dấu target này để không chọn lại trong iteration tới
            state["failed_targets"] = state.get("failed_targets", []) + [target]
    else:
        # Chế độ plan-only (hoặc non-infinite)
        plan = _plan_target(target) if target else {}
        state["plan_state_file"] = plan.get("state_file", "")
        state["next_action"] = plan.get("next_action", {}).get("action", "")
        state["plan_output"] = plan

    _save_state(state)

    print(f"\n[harness_upgrade_loop] === LOOP ITERATION {loop_iteration} (log iter {state.get('log_iteration', 0)}) ===")
    print(f"Phase: {state['phase']}")
    print(f"Baseline: {passed} passed / {failed} failed / {skipped} skipped")
    print(f"Target: {target or 'wait'}")
    if args.infinite and target:
        print("Auto-execute đã chạy; iteration kế tiếp sẽ lấy baseline mới.")
    else:
        plan = state.get("plan_output", {})
        print(f"Plan state file: {plan.get('state_file', 'N/A')}")
        print(f"Next action: {plan.get('next_action', {}).get('action', 'N/A')}")
        print("\nTiếp tục bằng cách thực hiện next_action và gọi --step với kết quả.")
        print("Sau khi xong, chạy lại script này để lấy baseline mới.")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harness upgrade loop driver")
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--max-time-min", type=int, default=DEFAULT_MAX_TIME_MIN)
    parser.add_argument("--convergence", type=int, default=DEFAULT_CONVERGENCE)
    parser.add_argument("--skip-baseline", action="store_true", help="Không chạy pytest, dùng state cũ")
    parser.add_argument("--infinite", action="store_true", help="Chạy vòng lặp vô tận")
    parser.add_argument("--sleep", type=int, default=10, help="Giây chờ giữa các iteration trong --infinite")
    args = parser.parse_args(argv)

    if args.infinite:
        args.max_iterations = 0
        args.convergence = 0
        if args.max_time_min == DEFAULT_MAX_TIME_MIN:
            args.max_time_min = 0

    while True:
        state = _load_state()
        if args.infinite and state.get("status") == "stopped":
            state["status"] = "in_progress"
            state["stop_reason"] = None
            state["start_time"] = datetime.now(timezone.utc).isoformat()
            state["failures_history"] = []
        should_continue = _run_one_iteration(state, args)
        if not should_continue:
            return 0
        if not args.infinite:
            return 0
        print(f"[harness_upgrade_loop] Ngủ {args.sleep}s trước iteration tiếp theo...")
        time.sleep(args.sleep)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())