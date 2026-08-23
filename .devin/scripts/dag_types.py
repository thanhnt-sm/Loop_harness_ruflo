#!/usr/bin/env python3
"""dag_types.py — Kiểu dữ liệu và exception cho DAG executor.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExecResult:
    """Kết quả thực thi DAG hoàn chỉnh."""

    success: bool
    status: dict
    results: dict[str, Any]
    error: str | None = None


class IdempotencyBlockedError(RuntimeError):
    """Execution bị BLOCK vì không giữ được idempotency lock (fail-closed).

    Khác task failed: đây là lỗi hạ tầng an toàn — DAG phải dừng, không tiếp tục.
    """

    def __init__(self, task_id: str, detail: str):
        super().__init__(f"idempotency lock failure blocked task '{task_id}': {detail}")
        self.task_id = task_id