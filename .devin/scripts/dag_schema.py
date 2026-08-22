#!/usr/bin/env python3
"""dag_schema.py — Shared schema contract cho DAG compile + execute.

V1 fix: dag_compile.py output và dag_executor.py input dùng cùng schema.
Schema version 1: tasks + edges + schema_version.

Validation strict: nếu có cả tasks và nodes → reject (chống schema confusion).
Migration: old schema (nodes/edges) → new schema (tasks/edges).
"""
from __future__ import annotations

import json
from typing import Any

# Schema version hiện tại
SCHEMA_VERSION = 1

# Fields bắt buộc trong mỗi task
TASK_REQUIRED_FIELDS = {"id", "goal", "dependencies"}
TASK_OPTIONAL_FIELDS = {"agent", "file", "function", "acceptance_criteria"}


def validate_workflow(data: dict) -> tuple[bool, str]:
    """Validate workflow JSON theo schema v1.

    Returns (valid, reason):
      - (True, "") nếu hợp lệ
      - (False, reason) nếu không hợp lệ

    Rules:
      1. Phải có workflow_id (str)
      2. Phải có tasks (list) HOẶC nodes (list) — không được có cả hai
      3. Nếu có cả tasks và nodes → reject (schema confusion)
      4. Mỗi task phải có id, goal, dependencies
      5. edges (nếu có) phải là list dict {from, to}
    """
    if not isinstance(data, dict):
        return False, "workflow phải là dict"

    # Rule 1: workflow_id
    wf_id = data.get("workflow_id")
    if not isinstance(wf_id, str) or not wf_id:
        return False, "thiếu workflow_id hoặc không phải str"

    has_tasks = "tasks" in data and data["tasks"] is not None
    has_nodes = "nodes" in data and data["nodes"] is not None

    # Rule 3: không được có cả tasks và nodes (strict)
    if has_tasks and has_nodes:
        return False, "cannot have both tasks and nodes — schema confusion detected"

    # Rule 2: phải có ít nhất một
    if not has_tasks and not has_nodes:
        return False, "thiếu tasks hoặc nodes — workflow rỗng"

    # Validate tasks (new schema)
    if has_tasks:
        tasks = data["tasks"]
        if not isinstance(tasks, list):
            return False, "tasks phải là list"
        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                return False, f"task[{i}] phải là dict"
            tid = t.get("id")
            if not isinstance(tid, str) or not tid:
                return False, f"task[{i}] thiếu id hoặc không phải str"
            if "goal" not in t:
                return False, f"task '{tid}' thiếu goal"
            deps = t.get("dependencies", [])
            if not isinstance(deps, list):
                return False, f"task '{tid}' dependencies phải là list"

    # Validate nodes (old schema — sẽ migrate)
    if has_nodes:
        nodes = data["nodes"]
        if not isinstance(nodes, list):
            return False, "nodes phải là list"
        for i, n in enumerate(nodes):
            if not isinstance(n, dict):
                return False, f"node[{i}] phải là dict"
            if "task_id" not in n:
                return False, f"node[{i}] thiếu task_id"

    # Validate edges (optional)
    edges = data.get("edges", [])
    if edges is not None:
        if not isinstance(edges, list):
            return False, "edges phải là list"
        for i, e in enumerate(edges):
            if not isinstance(e, dict):
                return False, f"edge[{i}] phải là dict"
            if "from" not in e or "to" not in e:
                return False, f"edge[{i}] thiếu from hoặc to"

    return True, ""


def migrate_old_schema(data: dict) -> dict:
    """Chuyển old schema (nodes/edges) sang new schema (tasks/edges).

    Old: {"nodes": [{"task_id", "description", "deps", ...}], "edges": [...]}
    New: {"tasks": [{"id", "goal", "dependencies", ...}], "edges": [...], "schema_version": 1}

    Nếu data đã là new schema → trả về nguyên (thêm schema_version nếu thiếu).
    """
    has_tasks = "tasks" in data and data["tasks"] is not None
    has_nodes = "nodes" in data and data["nodes"] is not None

    # Đã là new schema → chỉ thêm schema_version
    if has_tasks and not has_nodes:
        result = dict(data)
        result["schema_version"] = SCHEMA_VERSION
        return result

    # Old schema → migrate
    if has_nodes:
        tasks = []
        for node in data["nodes"]:
            task = {
                "id": node.get("task_id", ""),
                "goal": node.get("description", ""),
                "dependencies": node.get("deps", []),
                "agent": node.get("agent", ""),
                "file": node.get("file", ""),
                "function": node.get("function", ""),
                "acceptance_criteria": node.get("acceptance_criteria", ""),
            }
            tasks.append(task)
        result = {
            "workflow_id": data.get("workflow_id", ""),
            "schema_version": SCHEMA_VERSION,
            "tasks": tasks,
            "edges": data.get("edges", []),
        }
        # Giữ source + compiled_at nếu có
        if "source" in data:
            result["source"] = data["source"]
        if "compiled_at" in data:
            result["compiled_at"] = data["compiled_at"]
        return result

    # Không có gì → trả nguyên
    return data


def normalize_workflow(data: dict) -> tuple[dict | None, str]:
    """Validate + migrate workflow. Trả (workflow_normalized, error).

    Pipeline: validate → migrate → validate lại.
    """
    valid, reason = validate_workflow(data)
    if not valid:
        return None, reason

    migrated = migrate_old_schema(data)

    # Validate lại sau migrate
    valid, reason = validate_workflow(migrated)
    if not valid:
        return None, f"post-migration validation failed: {reason}"

    return migrated, ""
