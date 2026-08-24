#!/usr/bin/env python3
"""dag_analysis.py — Phân tích DAG: cycle detection, ready checking, status summary.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Phân tích DAG
# ---------------------------------------------------------------------------

def _detect_cycle(tasks: dict) -> list[str]:
    """Phát hiện chu trình trong DAG bằng DFS.

    Trả về danh sách task_id tạo thành chu trình, hoặc [] nếu không có.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in tasks}
    stack: list[str] = []

    def dfs(node: str) -> list[str]:
        """DFS từ node, trả về chu trình nếu tìm thấy."""
        color[node] = GRAY
        stack.append(node)
        for dep in tasks.get(node, {}).get("dependencies", []):
            if dep not in tasks:
                continue  # phụ thuộc không tồn tại → bỏ qua
            if color[dep] == GRAY:
                # Tìm thấy chu trình.
                idx = stack.index(dep)
                return stack[idx:] + [dep]
            if color[dep] == WHITE:
                result = dfs(dep)
                if result:
                    return result
        stack.pop()
        color[node] = BLACK
        return []

    for tid in tasks:
        if color[tid] == WHITE:
            cycle = dfs(tid)
            if cycle:
                return cycle
    return []


def _is_ready(tid: str, tasks: dict) -> bool:
    """Kiểm tra task có sẵn sàng (mọi phụ thuộc đã complete)."""
    deps = tasks.get(tid, {}).get("dependencies", [])
    for dep in deps:
        if dep not in tasks:
            return False  # phụ thuộc không tồn tại → không sẵn sàng
        if tasks[dep].get("status") != "complete":
            return False
    return True


def _mark_ready(state: dict) -> None:
    """Đánh dấu các task pending thỏa điều kiện là "ready"."""
    tasks = state.get("tasks", {})
    for tid, info in tasks.items():
        if info.get("status") == "pending":
            if _is_ready(tid, tasks):
                info["status"] = "ready"


def _get_ready_tasks(state: dict, batch_size: int) -> list[str]:
    """Lấy danh sách task sẵn sàng, tối đa batch_size.

    Bước 1: Thu thập tất cả task ở trạng thái "ready".
    Bước 2: Cắt theo batch_size.
    Bước 3: Trả về danh sách task_id.
    """
    tasks = state.get("tasks", {})
    ready = [tid for tid, info in tasks.items() if info.get("status") == "ready"]
    return ready[:batch_size]


def _get_status_summary(state: dict) -> dict:
    """Tóm tắt trạng thái workflow: completed, ready, running, pending, failed, blocked."""
    tasks = state.get("tasks", {})
    counts = {"complete": 0, "ready": 0, "running": 0, "pending": 0, "failed": 0, "blocked": 0}
    by_status: dict[str, list[str]] = {k: [] for k in counts}
    for tid, info in tasks.items():
        st = info.get("status", "pending")
        counts[st] = counts.get(st, 0) + 1
        by_status.setdefault(st, []).append(tid)
    total = len(tasks)
    all_complete = total > 0 and counts["complete"] == total
    any_failed = counts.get("failed", 0) > 0
    any_blocked = counts.get("blocked", 0) > 0
    return {
        "workflow_id": state.get("workflow_id"),
        "total_tasks": total,
        "counts": counts,
        "by_status": by_status,
        "all_complete": all_complete,
        "any_failed": any_failed,
        "any_blocked": any_blocked,
    }