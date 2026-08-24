#!/usr/bin/env python3
"""dag_callbacks.py — Callbacks: on_node_complete, resume, get_status, complete_task, fail_task.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from dag_config import DEFAULT_BATCH_SIZE
from dag_state import _load_state, _init_state, _save_state, _state_to_workflow, _save_checkpoint_for_state
from dag_analysis import _mark_ready, _get_status_summary
from dag_execution import execute
from dag_types import ExecResult


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def on_node_complete(node_id: str, result: Any, run_id: str | None = None) -> None:
    """T2.7: Callback đánh dấu node hoàn thành và cập nhật DAG."""
    if run_id is None:
        run_id = _current_run_id()
    if not run_id:
        return
    state = _load_state(run_id)
    if state is None:
        return
    if node_id not in state.get("tasks", {}):
        return
    state["tasks"][node_id]["status"] = "complete"
    state["tasks"][node_id]["result"] = result
    state["tasks"][node_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    _mark_ready(state)
    _save_state(state)
    _save_checkpoint_for_state(state)


def _current_run_id() -> str:
    """Lấy run_id từ env."""
    import os
    return os.environ.get("AHD_RUN_ID", "")


def resume(run_id: str, runner: Callable[[str, str], Any] | None = None, max_retries: int = 2) -> ExecResult:
    """T2.7: Resume DAG từ run_id."""
    state = _load_state(run_id)
    if state is None:
        return ExecResult(success=False, status={}, results={}, error=f"no state for run_id {run_id}")
    workflow = _state_to_workflow(state)
    return execute(workflow, checkpoint=state, runner=runner, max_retries=max_retries)


def get_status(workflow: dict) -> dict:
    """Lấy trạng thái hiện tại của workflow."""
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        state = _init_state(workflow)
        if not state:
            return {"status": {"error": "Không thể khởi tạo trạng thái"}}
        _save_state(state)
    _mark_ready(state)
    _save_state(state)
    return _get_status_summary(state)


def complete_task(workflow: dict, task_id: str, result: Any) -> dict:
    """Đánh dấu một task hoàn thành + tìm task mới sẵn sàng.

    Bước 1: Tải trạng thái. Bước 2: Đánh dấu task complete + lưu result.
    Bước 3: Đánh dấu task mới ready. Bước 4: Lưu + trả về.
    """
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        return {"completed": False, "reason": "Chưa có trạng thái thực thi"}
    if task_id not in state.get("tasks", {}):
        return {"completed": False, "reason": f"Task '{task_id}' không tồn tại"}
    state["tasks"][task_id]["status"] = "complete"
    state["tasks"][task_id]["result"] = result
    state["tasks"][task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    _mark_ready(state)
    _save_state(state)
    summary = _get_status_summary(state)
    newly_ready = [
        tid for tid, info in state["tasks"].items()
        if info.get("status") == "ready" and tid != task_id
    ]
    return {
        "completed": True,
        "task_id": task_id,
        "newly_ready": newly_ready,
        "status": summary,
    }


def fail_task(workflow: dict, task_id: str, reason: str) -> dict:
    """Đánh dấu một task thất bại."""
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        return {"failed": False, "reason": "Chưa có trạng thái thực thi"}
    if task_id not in state.get("tasks", {}):
        return {"failed": False, "reason": f"Task '{task_id}' không tồn tại"}
    state["tasks"][task_id]["status"] = "failed"
    state["tasks"][task_id]["result"] = {"error": reason}
    state["tasks"][task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)
    return {
        "failed": True,
        "task_id": task_id,
        "reason": reason,
        "status": _get_status_summary(state),
    }