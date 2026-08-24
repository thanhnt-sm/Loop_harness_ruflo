#!/usr/bin/env python3
"""plan_dispatch_parse.py — Plan parsing utilities.

Module for parsing IMPLEMENTATION_PLAN.md into subtasks and extracting
task tables and Mermaid edges.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

try:
    import plan_quality_check as _pqc
except ImportError:  # pragma: no cover
    _pqc = None


def _parse_mermaid_edges(text: str) -> list[tuple[str, str]]:
    """Parse Mermaid graph edges from plan text.

    Returns list of (source, destination) tuples where source --> destination.
    """
    edges = []
    in_mermaid = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```mermaid"):
            in_mermaid = True
            continue
        if in_mermaid and stripped.startswith("```"):
            in_mermaid = False
            continue
        if in_mermaid and "-->" in stripped:
            parts = stripped.split("-->")
            if len(parts) == 2:
                src = parts[0].strip()
                dst = parts[1].strip()
                if src and dst:
                    edges.append((src, dst))
    return edges


def _parse_task_tables(text: str) -> list[dict]:
    """Parse task tables from plan markdown.

    Returns list of task dicts with id, file_path, raw goal text.
    """
    tasks = []
    in_table = False
    headers = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "---" in stripped:
            # Table separator - mark table start
            in_table = True
            continue
        if in_table and stripped.startswith("|"):
            parts = [p.strip() for p in stripped.split("|")]
            parts = [p for p in parts if p]
            if not headers and parts and parts[0].lower() in ("id", "task id", "task_id"):
                headers = parts
                continue
            if headers and len(parts) >= len(headers):
                task = dict(zip(headers, parts))
                if task.get("id") or task.get("task id") or task.get("task_id"):
                    tid = task.get("id") or task.get("task id") or task.get("task_id", "")
                    tasks.append({
                        "id": tid,
                        "file_path": task.get("file path", task.get("file_path", task.get("file", ""))),
                        "raw": task.get("goal", task.get("description", task.get("raw", ""))),
                    })
            continue
        if in_table and not stripped.startswith("|"):
            in_table = False
            headers = []

    return tasks


def _parse_tasks(text: str) -> list[dict]:
    """Parse tasks from plan text using plan_quality_check parser if available."""
    if _pqc is not None:
        return _pqc._parse_tasks(text)

    # Fallback: use simple table parser
    return _parse_task_tables(text)


def _plan_to_subtasks(plan_path: Path) -> list[dict]:
    """Chuyển IMPLEMENTATION_PLAN.md thành danh sách subtasks để dispatch.

    Dùng parser từ `plan_quality_check.py` để trích task, file path,
    Mermaid DAG. Mỗi subtask có id, goal, files_hint, deps.
    """
    if _pqc is None:
        raise RuntimeError("plan_quality_check.py not available; cannot parse plan file")

    text = plan_path.read_text(encoding="utf-8-sig")
    tasks = _parse_tasks(text)
    edges = _parse_mermaid_edges(text)

    # Xây adjacency list: task_id -> [deps] (A --> B nghĩa là B phụ thuộc A)
    deps_map: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        if src and dst:
            deps_map[dst].append(src)

    subtasks = []
    for t in tasks:
        tid = t.get("id", "")
        if not tid:
            continue
        files_hint = []
        fp = t.get("file_path", "")
        if fp:
            files_hint.append(fp)
        subtasks.append({
            "id": tid,
            "goal": t.get("raw", ""),
            "files_hint": files_hint,
            "deps": list(dict.fromkeys(deps_map.get(tid, []))),
        })
    return subtasks