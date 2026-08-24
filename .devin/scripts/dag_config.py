#!/usr/bin/env python3
"""dag_config.py — Cấu hình và hằng số cho DAG executor.

Tách từ dag_executor.py để giảm kích thước file chính.

Lưu ý: module này ĐỊNH NGHĨA TRỰC TIẾP các hàm path helper (không import
dag_executor) để tránh circular import khi chạy `python dag_executor.py`
trực tiếp. Các sub-module khác import hằng số/helper từ đây; riêng logic
cần monkeypatch trong test (vd _repo_root) được truy cập qua module
dag_executor ở runtime.
"""
from __future__ import annotations

import os
from pathlib import Path

# Các hàm path helper — định nghĩa trực tiếp, self-contained.
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

# Make available for import
__all__ = [
    "_repo_root",
    "_state_dir",
    "_state_file",
    "_max_loop_iterations",
    "DEFAULT_BATCH_SIZE",
    "MAX_RETRIES",
]
