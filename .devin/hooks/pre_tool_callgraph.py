#!/usr/bin/env python3
"""pre_tool_callgraph.py — RC-3 Tool Registry Call-Graph Enforcement.

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API:
  - _load_tool_registry, _get_tool_tier, _get_tool_metadata, _get_call_graph_config
  - _get_session_call_stack, _update_session_call_stack, _get_current_call_depth
  - _enforce_call_depth, _enforce_allowed_chains, _log_call_violation
  - _check_call_graph_gate
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import ahd_session
from pre_tool_gates import _gate_error


# --- RC-3: Tool Registry Call-Graph Enforcement ---
# Load tool registry with call-graph metadata
def _load_tool_registry() -> dict:
    """Load tool_registry.json with call-graph metadata."""
    try:
        root = ahd_session.get_repo_root()
        registry_path = root / ".devin" / "tool_registry.json"
        if registry_path.exists():
            return json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {"tiers": {}, "call_graph": {"max_depth": 3, "allowed_chains": {}}}


def _get_tool_tier(tool_name: str) -> str:
    """Get the tier of a tool from the registry."""
    registry = _load_tool_registry()
    for tier, tier_data in registry.get("tiers", {}).items():
        if tool_name in tier_data.get("tools", []):
            return tier
    return "L0"  # default to L0 if not found


def _get_tool_metadata(tool_name: str) -> dict:
    """Get tool metadata including max_call_depth and allowed_children."""
    registry = _load_tool_registry()
    for tier, tier_data in registry.get("tiers", {}).items():
        if tool_name in tier_data.get("tools", []):
            return {
                "tier": tier,
                "max_call_depth": tier_data.get("max_call_depth", 1),
                "allowed_children": tier_data.get("allowed_children", []),
            }
    return {"tier": "L0", "max_call_depth": 1, "allowed_children": []}


def _get_call_graph_config() -> dict:
    """Get call-graph configuration from registry."""
    registry = _load_tool_registry()
    return registry.get("call_graph", {"max_depth": 3, "allowed_chains": {}})


def _get_session_call_stack(session_id: str, root: Path) -> list:
    """Get current call stack from session state."""
    state = ahd_session.read_session_state(session_id, root)
    return state.get("call_stack", [])


def _update_session_call_stack(session_id: str, root: Path, tool_name: str, action: str) -> None:
    """Update call stack in session state (push/pop)."""
    state = ahd_session.read_session_state(session_id, root)
    call_stack = state.get("call_stack", [])

    if action == "push":
        call_stack.append(tool_name)
        if len(call_stack) > 10:  # max history
            call_stack = call_stack[-10:]
    elif action == "pop" and call_stack:
        call_stack.pop()

    state["call_stack"] = call_stack
    ahd_session.update_session_state(session_id, {"call_stack": call_stack}, root)


def _get_current_call_depth(session_id: str, root: Path) -> int:
    """Get current call stack depth."""
    call_stack = _get_session_call_stack(session_id, root)
    return len(call_stack)


def _enforce_call_depth(session_id: str, root: Path, tool_name: str) -> None:
    """Enforce max call depth for the tool."""
    tool_meta = _get_tool_metadata(tool_name)
    max_depth = tool_meta.get("max_call_depth", 1)
    current_depth = _get_current_call_depth(session_id, root)

    if current_depth > max_depth:
        print(
            f"[RC-3 Call-Graph] BLOCKED: max_depth={max_depth} exceeded "
            f"(current depth={current_depth}). Tool: {tool_name}",
            file=sys.stderr,
        )
        sys.exit(2)


def _enforce_allowed_chains(session_id: str, root: Path, tool_name: str) -> None:
    """Enforce allowed call chains between tool tiers."""
    call_stack = _get_session_call_stack(session_id, root)
    # Stack vừa được push current tool → parent là phần tử kế cuối (nếu có).
    if len(call_stack) < 2:
        return  # first tool in chain

    parent_tool = call_stack[-2]
    parent_tier = _get_tool_tier(parent_tool)
    current_tier = _get_tool_tier(tool_name)

    call_graph = _get_call_graph_config()
    allowed_chains = call_graph.get("allowed_chains", {})

    allowed_parents = allowed_chains.get(current_tier, [])
    if parent_tier not in allowed_parents:
        print(
            f"[RC-3 Call-Graph] BLOCKED: {parent_tier} -> {current_tier} "
            f"not allowed. Parent: {parent_tool}, Current: {tool_name}",
            file=sys.stderr,
        )
        sys.exit(2)


def _log_call_violation(session_id: str, root: Path, violation: str, tool_name: str) -> None:
    """Log call-graph violation to session state."""
    state = ahd_session.read_session_state(session_id, root)
    violations = state.get("call_violations", [])
    violations.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "violation": violation,
    })
    if len(violations) > 50:  # keep last 50
        violations = violations[-50:]
    state["call_violations"] = violations
    ahd_session.update_session_state(session_id, {"call_violations": violations}, root)


def _check_call_graph_gate(data: dict) -> None:
    """RC-3: Enforce call-graph constraints on tool calls."""
    try:
        session_id = ahd_session.get_session_id(data)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        if not session_id or not tool_name:
            return

        root = ahd_session.get_repo_root()
        session_id = ahd_session.get_session_id(data)

        # Push current tool onto call stack
        _update_session_call_stack(session_id, root, tool_name, "push")

        try:
            # Enforce max depth
            _enforce_call_depth(session_id, root, tool_name)

            # Enforce allowed chains
            _enforce_allowed_chains(session_id, root, tool_name)

            # Update call stack on success
            _update_session_call_stack(session_id, root, tool_name, "pop")
        except SystemExit:
            # Pop on failure too
            _update_session_call_stack(session_id, root, tool_name, "pop")
            raise
    except SystemExit:
        raise
    except FileExistsError:
        # session_state dir đã tồn tại — không phải lỗi security, skip gate
        return
    except Exception as e:  # noqa: BLE001
        _gate_error("call_graph", e)
