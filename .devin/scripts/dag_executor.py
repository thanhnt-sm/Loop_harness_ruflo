#!/usr/bin/env python3
"""dag_executor.py — Phase D: Bộ thực thi song song dựa trên DAG (Entry Point).

Mô hình LLMCompiler: đọc một workflow đã biên dịch (DAG gồm các task có
tham chiếu phụ thuộc), xác định các task sẵn sàng (không còn phụ thuộc
chưa hoàn thành), lấy một lô (batch) kích thước giới hạn, đánh dấu
"running", và trả về cho hệ thống bên ngoài phân phối (dispatch) song
song. Khi task hoàn thành (callback bên ngoài), đánh dấu complete và
tìm các task mới sẵn sàng.

Lược đồ workflow đầu vào (từ dag_compile.py):
    {
      "workflow_id": str,
      "tasks": [
        {
          "id": str,
          "goal": str,
          "dependencies": [str],   # id các task phải hoàn thành trước
          "agent": str              # agent phụ trách (tuỳ chọn)
        }
      ]
    }

Trạng thái thực thi (lưu file):
    {
      "workflow_id": str,
      "tasks": {
        "<task_id>": {
          "status": "pending|ready|running|complete|failed",
          "result": dict | None,
          "completed_at": str | None
        }
      }
    }

CLI:
    python dag_executor.py <workflow.json> --execute [--batch-size N]
    python dag_executor.py <workflow.json> --status
    python dag_executor.py <workflow.json> --next [--batch-size N]
    python dag_executor.py <workflow.json> --complete <task_id> <result.json>
    python dag_executor.py <workflow.json> --fail <task_id> <reason>

Lưu trữ: .devin/plan_state/<workflow_id>_execution.json

Mã thoát:
    0 — mọi task đã hoàn thành
    1 — có task thất bại hoặc lỗi đầu vào
    2 — vẫn còn task đang chạy/chưa chạy
"""
from __future__ import annotations

# Import internal modules (not part of public API)
# Use absolute imports for compatibility with direct script execution
import os
import sys
from pathlib import Path

# Ensure the scripts directory is in path for absolute imports
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

# Đăng ký module này vào sys.modules["dag_executor"] để các sub-module
# (vd dag_state) import dag_executor tìm đúng module này, tránh circular
# import do double-import (hai instance module khác nhau khi chạy script).
# Chạy BẤT KỂ import hay chạy trực tiếp.
if "dag_executor" not in sys.modules:
    sys.modules["dag_executor"] = sys.modules[__name__]
# Reconfigure stdout/stderr sang UTF-8 để help text tiếng Việt không
# gây UnicodeEncodeError trên console Windows (cp1258/ cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, ValueError, OSError):
    pass

# Config functions (need to be here for test monkeypatching)
def _repo_root() -> Path:
    """Tìm thư mục gốc repo (chứa thư mục .devin)."""
    here = Path(__file__).resolve().parent  # .../.devin/scripts
    return here.parent.parent               # repo root


def _state_dir() -> Path:
    """Trả về thư mục .devin/plan_state, tự tạo nếu thiếu."""
    d = _repo_root() / ".devin" / "plan_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file(workflow_id: str) -> Path:
    """Trả về đường dẫn file trạng thái thực thi cho workflow."""
    safe_id = workflow_id.replace("/", "_").replace("\\", "_")
    # Task 3.9: namespace isolation — loop_id prefix nếu cấu hình AHD_LOOP_ID
    loop_id = os.environ.get("AHD_LOOP_ID", "")
    if loop_id:
        safe_id = f"{loop_id.replace('/', '_')}__{safe_id}"
    return _state_dir() / f"{safe_id}_execution.json"


# Task 3.9: hard max iterations (configurable, default 50)
def _max_loop_iterations() -> int:
    """Đọc giới hạn loop từ env mỗi lần gọi (cho phép đổi lúc runtime)."""
    try:
        return int(os.environ.get("AHD_MAX_LOOP_ITERATIONS", "50"))
    except (TypeError, ValueError):
        return 50


# Kích thước lô mặc định (số task tối đa trả về mỗi lần).
DEFAULT_BATCH_SIZE = 5

# T12 fix: State machine retry/branch cho execute phase
MAX_RETRIES = 2

import dag_state
import dag_analysis
import dag_operations
import dag_execution
import dag_failure
import dag_callbacks
import dag_types
import dag_cli

# Re-export public API for backward compatibility
from dag_types import ExecResult, IdempotencyBlockedError
from dag_operations import get_batch, get_next
from dag_callbacks import (
    on_node_complete,
    resume,
    get_status,
    complete_task,
    fail_task,
)
from dag_execution import execute
from dag_state import (
    _load_workflow,
    _load_state,
    _save_state,
    _init_state,
    _state_to_workflow,
)
from dag_analysis import (
    _detect_cycle,
    _is_ready,
    _mark_ready,
    _get_ready_tasks,
    _get_status_summary,
)
from dag_failure import (
    _handle_failure,
    _retry_task,
    _branch_task,
)
from dag_execution import _run_task, _transient_exception, _default_runner, _current_run_id
from dag_state import _save_checkpoint_for_state
from dag_cli import main

__all__ = [
    # Types
    "ExecResult",
    "IdempotencyBlockedError",
    # Core functions
    "execute",
    "resume",
    "get_batch",
    "get_next",
    "get_status",
    "complete_task",
    "fail_task",
    "on_node_complete",
    # Internal (used by tests)
    "_load_workflow",
    "_load_state",
    "_save_state",
    "_init_state",
    "_state_to_workflow",
    "_detect_cycle",
    "_is_ready",
    "_mark_ready",
    "_get_ready_tasks",
    "_get_status_summary",
    "_handle_failure",
    "_retry_task",
    "_branch_task",
    "_run_task",
    "_transient_exception",
    "_default_runner",
    "_current_run_id",
    "_save_checkpoint_for_state",
    "_repo_root",
    "_state_dir",
    "_state_file",
    "_max_loop_iterations",
    # Config
    "DEFAULT_BATCH_SIZE",
    "MAX_RETRIES",
    # CLI
    "main",
]


if __name__ == "__main__":
    import sys
    sys.exit(main())