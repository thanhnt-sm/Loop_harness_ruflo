#!/usr/bin/env python3
"""dag_failure.py — Xử lý failure: retry, branch.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

from typing import Any

from dag_config import MAX_RETRIES
from dag_state import _save_state


# ---------------------------------------------------------------------------
# T12 fix: State machine retry/branch cho execute phase
# ---------------------------------------------------------------------------

def _handle_failure(state: dict, task_id: str, error: str) -> str:
    """T12 fix: Xử lý task failure — chuyển sang retry_pending hoặc human_review.

    State transitions:
      failed → retry_pending (nếu retry_count < MAX_RETRIES)
      failed → human_review (nếu retry_count >= MAX_RETRIES)

    Returns next state name.
    """
    task = state.get("tasks", {}).get(task_id, {})
    retry_count = task.get("retry_count", 0)

    if retry_count < MAX_RETRIES:
        task["status"] = "retry_pending"
        task["retry_count"] = retry_count + 1
        task["last_error"] = error
        state["tasks"][task_id] = task
        _save_state(state)
        return "retry_pending"
    else:
        task["status"] = "human_review"
        task["last_error"] = error
        task["retry_count"] = retry_count
        state["tasks"][task_id] = task
        _save_state(state)
        return "human_review"


def _retry_task(state: dict, task_id: str) -> dict:
    """T12 fix: Retry task — chuyển từ retry_pending sang retrying.

    Returns {"retried": bool, "next_status": str}
    """
    task = state.get("tasks", {}).get(task_id, {})
    if task.get("status") != "retry_pending":
        return {"retried": False, "next_status": task.get("status", "unknown")}

    task["status"] = "retrying"
    state["tasks"][task_id] = task
    _save_state(state)
    return {"retried": True, "next_status": "retrying"}


def _branch_task(state: dict, task_id: str, branch_condition: str) -> dict:
    """T12 fix: Branch task — tạo branch task dựa trên condition.

    Pentest V12 fix: thêm counter suffix để đảm bảo branch_id unique
    ngay cả khi cùng condition (tránh collision).

    Returns {"branched": bool, "branch_task_id": str}
    """
    task = state.get("tasks", {}).get(task_id, {})
    # Pentest V12 fix: base branch_id + counter để đảm bảo unique
    base_id = f"{task_id}_branch_{branch_condition[:8]}"
    branch_id = base_id
    counter = 1
    while branch_id in state.get("tasks", {}):
        branch_id = f"{base_id}_{counter}"
        counter += 1

    state["tasks"][branch_id] = {
        "status": "pending",
        "result": None,
        "completed_at": None,
        "branch_of": task_id,
        "branch_condition": branch_condition,
    }
    _save_state(state)
    return {"branched": True, "branch_task_id": branch_id}