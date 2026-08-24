#!/usr/bin/env python3
"""dag_operations.py — Các thao tác chính: get_batch, get_next.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

from typing import Any

from dag_config import DEFAULT_BATCH_SIZE
from dag_state import _load_state, _init_state, _save_state
from dag_analysis import _mark_ready, _get_ready_tasks, _get_status_summary


# ---------------------------------------------------------------------------
# Các thao tác chính
# ---------------------------------------------------------------------------

def get_batch(workflow: dict, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """Lấy lô task sẵn sàng, đánh dấu "running", trả về lô.

    Bước 1: Tải hoặc khởi tạo trạng thái.
    Bước 2: Đánh dấu task sẵn sàng.
    Bước 3: Lấy lô batch_size task.
    Bước 4: Đánh dấu lô là "running".
    Bước 5: Lưu trạng thái.
    Bước 6: Trả về lô + tóm tắt.
    """
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        state = _init_state(workflow)
        if not state or not state.get("tasks"):
            return {"executed": False, "reason": "Không thể khởi tạo trạng thái (có thể do chu trình)"}
    # Đánh dấu ready + lấy lô.
    _mark_ready(state)
    batch = _get_ready_tasks(state, batch_size)
    for tid in batch:
        state["tasks"][tid]["status"] = "running"
    _save_state(state)
    summary = _get_status_summary(state)
    batch_details = [
        {
            "id": tid,
            "goal": state["tasks"][tid].get("goal", ""),
            "agent": state["tasks"][tid].get("agent", ""),
            "dependencies": state["tasks"][tid].get("dependencies", []),
        }
        for tid in batch
    ]
    return {
        "executed": True,
        "workflow_id": wf_id,
        "batch": batch_details,
        "batch_size": len(batch),
        "status": summary,
    }


def get_next(workflow: dict, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """Lấy lô task sẵn sàng tiếp theo (không đánh dấu running)."""
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        state = _init_state(workflow)
        if not state:
            return {"next": [], "reason": "Không thể khởi tạo trạng thái"}
    _mark_ready(state)
    batch = _get_ready_tasks(state, batch_size)
    batch_details = [
        {
            "id": tid,
            "goal": state["tasks"][tid].get("goal", ""),
            "agent": state["tasks"][tid].get("agent", ""),
            "dependencies": state["tasks"][tid].get("dependencies", []),
        }
        for tid in batch
    ]
    return {
        "workflow_id": wf_id,
        "next": batch_details,
        "batch_size": len(batch),
        "status": _get_status_summary(state),
    }