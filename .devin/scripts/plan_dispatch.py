#!/usr/bin/env python3
"""plan_dispatch.py — Dependency graph analysis + file ownership allocation + conflict detection.

The Commander calls this BEFORE dispatching parallel Workers. It:

  1. Analyzes which files each subtask touches (from grep/AST scan)
  2. Detects file ownership conflicts (two subtasks touching the same file)
  3. Allocates files to workers (disjoint sets — no overlap)
  4. Suggests Nuwa cognitive angles for each subtask (from the deployer's
     Nuwa 3-tree system + any user-distilled perspective skills)
  5. Outputs a JSON dispatch plan the Commander can paste into Worker prompts

Usage:
  python .devin/scripts/plan_dispatch.py --analyze --subtasks subtasks.json
  python .devin/scripts/plan_dispatch.py --analyze --subtasks subtasks.json --json

subtasks.json format:
  [
    {
      "id": "st-1",
      "goal": "Fix backup logic in plan_dispatch.py",
      "files_hint": [".devin/scripts/plan_dispatch.py", ".devin/scripts/pre_task_audit.py"]
    },
    {
      "id": "st-2",
      "goal": "Add new adapter for tool X",
      "files_hint": [".devin/tool_registry.json", ".devin/scripts/hook_integrity.py"]
    }
  ]

Output (JSON):
  {
    "subtasks": [
      {
        "id": "st-1",
        "owned_files": [".devin/scripts/plan_dispatch.py"],
        "shared_files": [".devin/scripts/pre_task_audit.py"],
        "conflicts": [],
        "nuwa_angles": ["edge-case", "dependency"],
        "parallel_safe": true,
        "worktree": "builder-a"
      },
      ...
    ],
    "conflicts": [
      {
        "file": ".devin/scripts/pre_task_audit.py",
        "subtasks": ["st-1", "st-2"],
        "resolution": "serialize",
        "suggested_order": ["st-1", "st-2"]
      }
    ],
    "worktrees": ["builder-a", "builder-b"],
    "summary": "2 subtasks, 1 conflict (.devin/scripts/pre_task_audit.py), 2 worktrees needed"
  }
"""
from __future__ import annotations

import sys
from pathlib import Path

# Re-export all public APIs from submodules
try:
    from .plan_dispatch_grep import _grep_files, _expand_file_hints
    from .plan_dispatch_parse import _plan_to_subtasks, _parse_tasks, _parse_task_tables, _parse_mermaid_edges
    from .plan_dispatch_conflict import _detect_conflicts, _allocate_ownership, _active_session_conflicts
    from .plan_dispatch_nuwa import _suggest_nuwa_angles, NUWA_ANGLES
    from .plan_dispatch_dag import _build_dependency_graph, _topological_sort, _parallel_groups
    from .plan_dispatch_worktree import _get_active_sessions, _assign_worktrees
except ImportError:  # pragma: no cover - fallback for direct script execution
    from plan_dispatch_grep import _grep_files, _expand_file_hints
    from plan_dispatch_parse import _plan_to_subtasks, _parse_tasks, _parse_task_tables, _parse_mermaid_edges
    from plan_dispatch_conflict import _detect_conflicts, _allocate_ownership, _active_session_conflicts
    from plan_dispatch_nuwa import _suggest_nuwa_angles, NUWA_ANGLES
    from plan_dispatch_dag import _build_dependency_graph, _topological_sort, _parallel_groups
    from plan_dispatch_worktree import _get_active_sessions, _assign_worktrees

# Import ahd_session for the analyze function
try:
    import ahd_session
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session


def analyze(subtasks: list[dict], session_id: str = "") -> dict:
    """Full analysis: expand files, detect conflicts, allocate, suggest angles."""
    root = ahd_session.get_repo_root()

    # Step 1: Expand file hints (find dependents via grep)
    for st in subtasks:
        st["_expanded_files"] = sorted(_expand_file_hints(st.get("files_hint", [])))

    # Step 2: Detect internal conflicts
    conflicts = _detect_conflicts(subtasks)

    # Step 3: Detect conflicts with active sessions
    active_sessions = _get_active_sessions(root)
    active_conflicts = _active_session_conflicts(subtasks, active_sessions)
    conflicts.extend(active_conflicts)

    # Step 4: Allocate ownership
    allocation = _allocate_ownership(subtasks, conflicts)

    # Step 5: Suggest Nuwa angles
    for st in subtasks:
        st["_nuwa_angles"] = _suggest_nuwa_angles(st)

    # Step 6: Assign worktrees
    worktree_map = _assign_worktrees(subtasks, allocation, session_id)

    # Step 7: Build dependency graph + topological sort + deadlock detection
    dep_graph = _build_dependency_graph(subtasks, conflicts)
    dispatch_order, cycle_nodes = _topological_sort(dep_graph)
    parallel_groups = _parallel_groups(dep_graph, dispatch_order) if dispatch_order else []

    # Build output
    result_subtasks = []
    for st in subtasks:
        alloc = allocation[st["id"]]
        result_subtasks.append({
            "id": st["id"],
            "goal": st["goal"],
            "owned_files": alloc["owned_files"],
            "shared_files": alloc["shared_files"],
            "conflicts": [c for c in conflicts if st["id"] in c["subtasks"]],
            "active_session_conflicts": [
                c for c in active_conflicts if st["id"] in c["subtasks"]
            ],
            "nuwa_angles": st["_nuwa_angles"],
            "parallel_safe": len(alloc["shared_files"]) == 0 and not any(
                st["id"] in c["subtasks"] for c in active_conflicts
            ),
            "worktree": worktree_map[st["id"]],
        })

    summary = (
        f"{len(subtasks)} subtasks, "
        f"{len(conflicts)} conflict(s)"
        f"{', ' + str(len(set(w for w in worktree_map.values()))) + ' worktrees needed' if subtasks else ''}"
    )

    return {
        "subtasks": result_subtasks,
        "conflicts": conflicts,
        "worktrees": sorted(set(worktree_map.values())),
        "dispatch_order": dispatch_order or [],
        "parallel_groups": parallel_groups,
        "deadlock_detected": cycle_nodes is not None and len(cycle_nodes) > 0,
        "cycle_nodes": cycle_nodes or [],
        "dependency_graph": dep_graph,
        "summary": summary,
    }


if __name__ == "__main__":
    try:
        from .plan_dispatch_cli import main
    except ImportError:
        from plan_dispatch_cli import main
    sys.exit(main())