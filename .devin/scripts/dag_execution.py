#!/usr/bin/env python3
"""dag_execution.py — Logic thực thi DAG chính: execute, _run_task.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

import idempotency as idempotency_module

from dag_config import _repo_root, DEFAULT_BATCH_SIZE, _max_loop_iterations
from dag_state import _load_state, _init_state, _save_state, _save_checkpoint_for_state
from dag_analysis import _mark_ready, _get_ready_tasks, _get_status_summary
from dag_types import ExecResult, IdempotencyBlockedError


# ---------------------------------------------------------------------------
# T2.7: Durable execution API
# ---------------------------------------------------------------------------

def _transient_exception(exc: Exception) -> bool:
    """Coi hầu hết exception trong runner là transient (có thể retry).

    Có thể mở rộng sau này để phân biệt fatal vs transient.
    """
    return True


def _default_runner(task_id: str, goal: str) -> Any:
    """Runner mặc định — trả về ok nếu không có runner tùy chỉnh."""
    return {"ok": True, "task_id": task_id, "goal": goal}


def _current_run_id() -> str:
    """Lấy run_id từ env hoặc module."""
    return os.environ.get("AHD_RUN_ID", "")


def _run_task(task_id: str, task_info: dict, runner: Callable[[str, str], Any], max_retries: int, run_id: str) -> Any:
    """T2.7: Chạy một task với idempotency + retry."""
    goal = task_info.get("goal", "")
    attempts = 0
    last_exc: Exception | None = None

    # Idempotency: cùng (run_id, task_id) chỉ thực sự chạy một lần
    def _op():
        return runner(task_id, goal)

    while attempts <= max_retries:
        try:
            return idempotency_module.register(
                f"{run_id}:{task_id}",
                _op,
                run_id=run_id,
            )
        except idempotency_module.IdempotencyLockError as exc:
            # CVE-2026-AHD-003: lock failure = fail CLOSED.
            # KHÔNG retry, KHÔNG đánh dấu task "failed" rồi tiếp tục —
            # phải block toàn bộ execution (caller dừng DAG ngay).
            raise IdempotencyBlockedError(task_id, str(exc)) from exc
        except Exception as exc:
            last_exc = exc
            if not _transient_exception(exc):
                break
            attempts += 1

    raise last_exc or RuntimeError(f"task {task_id} failed after {max_retries} retries")


def execute(
    workflow: dict,
    checkpoint: dict | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    runner: Callable[[str, str], Any] | None = None,
    max_retries: int = 2,
) -> ExecResult:
    """T2.7: Thực thi DAG hoàn chỉnh, checkpoint mỗi batch, retry transient.

    - Nếu checkpoint là dict: resume từ đó.
    - Chạy từng batch song song (trong batch) theo dependency.
    - Gọi runner(task_id, goal) cho mỗi task; retry nếu exception transient.
    - Gọi on_node_complete sau mỗi task.
    - Trả về ExecResult khi hoàn thành hoặc thất bại.
    """
    if runner is None:
        runner = _default_runner

    # Khởi tạo hoặc resume state
    if checkpoint is not None:
        if "dag_state" in checkpoint:
            state = checkpoint["dag_state"]
        else:
            state = checkpoint
    else:
        state = _load_state(workflow["workflow_id"])

    if state is None or not state:
        state = _init_state(workflow)
        if not state:
            return ExecResult(success=False, status={}, results={}, error="cannot init state (cycle?)")

    wf_id = state.get("workflow_id", workflow["workflow_id"])
    os.environ["AHD_RUN_ID"] = wf_id

    # T2.7/T3.5: khi resume (có checkpoint/state đã lưu), reset các task đang
    # "running" về "pending" — giả định process bị kill giữa chừng. Idempotency
    # ledger sẽ đảm bảo task đã thực sự hoàn thành không bị re-run (cache hit).
    if checkpoint is not None:
        for tid, info in state.get("tasks", {}).items():
            if info.get("status") == "running":
                info["status"] = "pending"

    iteration = 0
    while True:
        _mark_ready(state)
        batch = _get_ready_tasks(state, batch_size)
        if not batch:
            summary = _get_status_summary(state)
            if summary.get("all_complete"):
                _save_state(state)
                _save_checkpoint_for_state(state)
                return ExecResult(success=True, status=summary, results={tid: state["tasks"][tid].get("result") for tid in state["tasks"]})
            if summary.get("any_failed"):
                _save_state(state)
                _save_checkpoint_for_state(state)
                failed = [tid for tid, info in state["tasks"].items() if info.get("status") == "failed"]
                return ExecResult(success=False, status=summary, results={}, error=f"failed tasks: {failed}")
            # Deadlock: có task đang running hoặc pending nhưng không ready
            _save_state(state)
            return ExecResult(success=False, status=summary, results={}, error="deadlock or waiting for running tasks")

        iteration += 1
        # Task 3.9: hard max iterations — còn batch nhưng đã vượt ngưỡng ->
        # dừng (không loop vô hạn). Chỉ áp dụng khi vẫn còn việc phải chạy.
        if iteration > _max_loop_iterations():
            _save_state(state)
            summary = _get_status_summary(state)
            return ExecResult(
                success=False, status=summary, results={},
                error=f"max loop iterations exceeded ({_max_loop_iterations()})",
            )
        # Đánh dấu running
        for tid in batch:
            state["tasks"][tid]["status"] = "running"
        _save_state(state)

        # Chạy batch song song
        results: dict[str, Any] = {}
        blocked: str | None = None
        with ThreadPoolExecutor(max_workers=min(len(batch), 8)) as pool:
            futures = {pool.submit(_run_task, tid, state["tasks"][tid], runner, max_retries, wf_id): tid for tid in batch}
            for future in as_completed(futures):
                tid = futures[future]
                try:
                    result = future.result()
                    results[tid] = result
                    state["tasks"][tid]["status"] = "complete"
                    state["tasks"][tid]["result"] = result
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()
                except IdempotencyBlockedError as exc:
                    # CVE-2026-AHD-003: lock failure -> BLOCK toàn bộ execution.
                    # Không đánh dấu "failed" (failed = có thể retry/continue),
                    # mà đánh dấu "blocked" và dừng DAG ngay.
                    blocked = str(exc)
                    state["tasks"][tid]["status"] = "blocked"
                    state["tasks"][tid]["result"] = {"error": str(exc)}
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    state["tasks"][tid]["status"] = "failed"
                    state["tasks"][tid]["result"] = {"error": str(exc)}
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()

                except Exception as exc:
                    state["tasks"][tid]["status"] = "failed"
                    state["tasks"][tid]["result"] = {"error": str(exc)}
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()

        if blocked is not None:
            # Fail-closed: dừng DAG, không chạy batch kế tiếp.
            _save_state(state)
            summary = _get_status_summary(state)
            return ExecResult(success=False, status=summary, results={}, error=blocked)

        state["last_executed_step"] = f"batch_{iteration}"
        _save_state(state)
        _save_checkpoint_for_state(state)