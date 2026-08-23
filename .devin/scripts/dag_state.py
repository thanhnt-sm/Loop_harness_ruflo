#!/usr/bin/env python3
"""dag_state.py — Đọc/ghi trạng thái thực thi DAG.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import checkpoint as checkpoint_module
from data_models import CheckpointState

from dag_types import ExecResult
from dag_analysis import _detect_cycle, _mark_ready


def _executor():
    """Lazy access to dag_executor module (tránh circular import)."""
    import dag_executor
    return dag_executor


# ---------------------------------------------------------------------------
# Đọc/ghi trạng thái
# ---------------------------------------------------------------------------

def _load_workflow(path: str) -> dict | None:
    """Đọc file workflow đã biên dịch — hỗ trợ schema mới (tasks) và cũ (nodes).

    Bước 1: Đọc file JSON.
    Bước 2: Validate + migrate schema (dag_schema.normalize_workflow).
    Bước 3: Strict validation — reject nếu có cả tasks và nodes.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor] Không đọc được workflow {path}: {exc}",
              file=sys.stderr)
        return None
    if not isinstance(data, dict) or "workflow_id" not in data:
        print(f"[dag_executor] Workflow sai định dạng: thiếu workflow_id",
              file=sys.stderr)
        return None
    # T1 fix: dùng dag_schema để validate + migrate
    try:
        from dag_schema import normalize_workflow
        normalized, error = normalize_workflow(data)
        if normalized is None:
            print(f"[dag_executor] Workflow không hợp lệ: {error}",
                  file=sys.stderr)
            return None
        return normalized
    except (ImportError, ModuleNotFoundError):
        # Fallback: chấp nhận schema cũ (tasks hoặc nodes)
        has_tasks = "tasks" in data and data["tasks"] is not None
        has_nodes = "nodes" in data and data["nodes"] is not None
        if has_tasks and has_nodes:
            print(f"[dag_executor] Schema confusion: có cả tasks và nodes",
                  file=sys.stderr)
            return None
        if not has_tasks and not has_nodes:
            print(f"[dag_executor] Workflow sai định dạng: thiếu tasks hoặc nodes",
                  file=sys.stderr)
            return None
        # Migrate old schema (nodes → tasks) inline
        if has_nodes:
            tasks = []
            for node in data["nodes"]:
                tasks.append({
                    "id": node.get("task_id", ""),
                    "goal": node.get("description", ""),
                    "dependencies": node.get("deps", []),
                    "agent": node.get("agent", ""),
                })
            data = {
                "workflow_id": data.get("workflow_id", ""),
                "schema_version": 1,
                "tasks": tasks,
                "edges": data.get("edges", []),
            }
        return data


def _load_state(workflow_id: str) -> dict | None:
    """Tải trạng thái thực thi từ file. Nếu lỗi → trả None."""
    f = _executor()._state_file(workflow_id)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor] Lỗi đọc trạng thái {workflow_id}: {exc}",
              file=sys.stderr)
        return None


def _save_state(state: dict) -> bool:
    """Lưu trạng thái thực thi vào file."""
    wf_id = state.get("workflow_id", "unknown")
    f = _executor()._state_file(wf_id)
    try:
        f.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        # Task 3.9: immutable state log (append-only Merkle chain) —
        # best-effort, không chặn execution khi telemetry lỗi.
        try:
            from loop_memory_sync import append_state_log
            append_state_log(
                _executor()._repo_root(), str(wf_id), "dag_state_saved",
                {"step": state.get("last_executed_step", ""),
                 "status": state.get("status", "")},
            )
        except (ImportError, ModuleNotFoundError):
            pass
        return True
    except OSError as exc:
        print(f"[dag_executor] Lỗi lưu trạng thái: {exc}", file=sys.stderr)
        return False


def _init_state(workflow: dict) -> dict:
    """Khởi tạo trạng thái thực thi từ workflow.

    Bước 1: Tạo dict tasks với mọi task ở trạng thái "pending".
    Bước 2: Kiểm tra chu trình (cyclic dependency).
    Bước 3: Đánh dấu các task sẵn sàng (không có phụ thuộc) là "ready".
    """
    wf_id = workflow["workflow_id"]
    tasks_def = workflow.get("tasks", [])
    state = {
        "workflow_id": wf_id,
        "tasks": {},
    }
    for task in tasks_def:
        tid = task.get("id")
        if not tid:
            continue
        state["tasks"][tid] = {
            "status": "pending",
            "result": None,
            "completed_at": None,
            "dependencies": task.get("dependencies", []),
            "goal": task.get("goal", ""),
            "agent": task.get("agent", ""),
        }
    # Kiểm tra chu trình.
    cycle = _detect_cycle(state["tasks"])
    if cycle:
        print(f"[dag_executor] Phát hiện chu trình: {' -> '.join(cycle)}",
              file=sys.stderr)
        return {}
    # Đánh dấu task sẵn sàng.
    _mark_ready(state)
    return state


def _state_to_workflow(state: dict) -> dict:
    """Tái tạo workflow dict từ trạng thái đã lưu để resume."""
    tasks = []
    for tid, info in state.get("tasks", {}).items():
        tasks.append({
            "id": tid,
            "dependencies": info.get("dependencies", []),
            "goal": info.get("goal", ""),
            "agent": info.get("agent", ""),
        })
    return {"workflow_id": state.get("workflow_id", "default"), "tasks": tasks}


def _save_checkpoint_for_state(state: dict) -> None:
    """T2.7: Lưu checkpoint sau mỗi batch bằng checkpoint.save."""
    try:
        wf_id = state.get("workflow_id", "default")
        step_id = state.get("last_executed_step", "batch") or "batch"
        ts = datetime.now(timezone.utc)
        ckpt = CheckpointState(
            version=2,
            run_id=wf_id,
            conversation=[],
            side_effects_ledger=[],
            run_metadata={"dag_state": copy.deepcopy(state)},
            external_handles=[],
            timestamp=ts,
            step_id=step_id,
        )
        checkpoint_module.save(ckpt, workflow_id=wf_id, root=_executor()._repo_root())
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    except Exception as e:
        print(f"[dag_executor] unexpected exception: {e}", file=sys.stderr)
        pass