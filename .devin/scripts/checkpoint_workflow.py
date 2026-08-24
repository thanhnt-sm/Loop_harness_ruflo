#!/usr/bin/env python3
"""checkpoint_workflow.py — Workflow loading and dependency mapping.

Handles workflow JSON parsing, downstream map building, and dependency extraction.
"""
from __future__ import annotations

import json
from pathlib import Path


def _load_workflow(root: Path, workflow_path: Path) -> dict | None:
    """Tai workflow JSON. Tra ve None neu khong ton tai / hong."""
    if not workflow_path.exists():
        print(f"[ERROR] Khong tim thay workflow file: {workflow_path}")
        return None
    try:
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError) as e:
        print(f"[ERROR] Workflow file hong: {e}")
        return None
    return None


def _build_downstream_map(workflow: dict) -> dict:
    """Xay dung anh xa: step_id -> list downstream steps (transitive).

    Dua vao edges (from -> to): downstream cua X = tat ca node ma X co the den.
    """
    edges = workflow.get("edges", [])
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
    # Tinh transitive downstream bang BFS
    downstream = {}
    nodes = {n["task_id"] for n in workflow.get("nodes", [])}
    for start in nodes:
        visited = set()
        queue = list(adj.get(start, []))
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            queue.extend(adj.get(node, []))
        downstream[start] = sorted(visited)
    return downstream


def _dependencies_for(workflow: dict, step_id: str) -> list:
    """Lay danh sach phu thuoc cua 1 step tu workflow."""
    for n in workflow.get("nodes", []):
        if n["task_id"] == step_id:
            return n.get("deps", [])
    return []