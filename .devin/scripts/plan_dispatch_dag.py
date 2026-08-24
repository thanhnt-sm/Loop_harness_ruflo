#!/usr/bin/env python3
"""plan_dispatch_dag.py — Dependency graph and topological sorting.

Module for building dependency graphs from explicit deps + file conflicts,
topological sorting with cycle detection, and grouping into parallel levels.
"""

from __future__ import annotations

from collections import deque


def _build_dependency_graph(subtasks: list[dict], conflicts: list[dict]) -> dict[str, list[str]]:
    """Build a dependency graph from explicit deps + file conflicts.

    Nếu subtask A và B share file, và A được suggest đi trước,
    thì B phụ thuộc A. Ngoài ra, plan Mermaid DAG cũng được tôn trọng
    qua trường `deps` trong mỗi subtask.

    Active session conflicts có session_id trong suggested_order,
    không phải subtask. Bỏ qua — active session conflicts xử lý qua parallel_safe.

    Returns adjacency list: {subtask_id: [depends_on_ids]}.
    """
    graph: dict[str, list[str]] = {st["id"]: list(st.get("deps", [])) for st in subtasks}
    for c in conflicts:
        # Skip active session conflicts (session_id not a subtask)
        if c.get("resolution") == "wait_for_session":
            continue
        order = c.get("suggested_order", [])
        if len(order) >= 2:
            # order[0] goes first, order[1+] depend on order[0]
            for dependent in order[1:]:
                # Skip self-dependency
                if dependent == order[0]:
                    continue
                if dependent in graph and order[0] in graph and order[0] not in graph[dependent]:
                    graph[dependent].append(order[0])
    return graph


def _topological_sort(graph: dict[str, list[str]]) -> tuple[list[str] | None, list[str] | None]:
    """Topological sort with cycle detection (Kahn's algorithm).

    Returns (dispatch_order, cycle_nodes):
    - dispatch_order: list of subtask IDs in dependency order (None if cycle)
    - cycle_nodes: list of subtask IDs with unresolved dependencies
      (includes nodes in cycles AND nodes depending on cycles)
    """
    # in_degree = count of dependencies that exist in graph
    in_degree: dict[str, int] = {}
    for node in graph:
        in_degree[node] = sum(1 for dep in graph[node] if dep in in_degree or dep in graph)

    # Queue of nodes with no dependencies
    queue = deque([n for n in graph if in_degree[n] == 0])
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        # Find nodes that depend on this node (reverse edges)
        for other in graph:
            if node in graph[other]:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)

    if len(order) < len(graph):
        # Cycle detected — find nodes with remaining dependencies
        # Note: includes nodes in cycles AND nodes that depend on cycles
        cycle_nodes = [n for n in graph if in_degree[n] > 0]
        return None, cycle_nodes

    return order, []


def _parallel_groups(graph: dict[str, list[str]], dispatch_order: list[str]) -> list[list[str]]:
    """Group subtasks into parallel execution levels.

    Subtasks at the same level have all dependencies satisfied by previous levels.
    Level 0 = no dependencies. Level N = depends on something in level N-1 or earlier.
    """
    if not dispatch_order:
        return []

    levels: dict[str, int] = {}
    for node in dispatch_order:
        if not graph[node]:
            levels[node] = 0
        else:
            levels[node] = max(levels.get(dep, 0) for dep in graph[node]) + 1

    max_level = max(levels.values()) if levels else 0
    groups: list[list[str]] = [[] for _ in range(max_level + 1)]
    for node, level in levels.items():
        groups[level].append(node)

    return groups