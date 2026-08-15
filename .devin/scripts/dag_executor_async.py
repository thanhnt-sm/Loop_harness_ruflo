#!/usr/bin/env python3
"""dag_executor_async.py — Async DAG executor using AsyncTaskGraph.

Replaces ThreadPoolExecutor-based dag_executor with async-native execution.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime import (
    AsyncTaskGraph,
    Task,
    TaskStatus,
    ExecutionProgress,
    CancellationToken,
    StreamingExecutor,
    TokenBudget,
    CostOptimizer,
    StreamAdapter,
)
from runtime.cancellation import CancellationToken
from runtime.backpressure import BackpressureQueue
from runtime.token_budget import TokenBudget, CostOptimizer
from runtime.llm_stream import StreamAdapter, StreamChunk, LLMClient, LightningExecutorClient, GLMExecutorClient, KimiExecutorClient
from runtime.cache_layer import CacheLayer, CacheKeyBuilder

import checkpoint as checkpoint_module
import idempotency as idempotency_module
from data_models import CheckpointState, Turn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Find repo root (contains .devin directory)."""
    here = Path(__file__).resolve().parent  # .../.devin/scripts
    return here.parent.parent               # repo root


def _state_dir() -> Path:
    """Return .devin/plan_state directory, create if missing."""
    d = _repo_root() / ".devin" / "plan_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file(workflow_id: str) -> Path:
    """Return path to execution state file for workflow."""
    safe_id = workflow_id.replace("/", "_").replace("\\", "_")
    loop_id = os.environ.get("AHD_LOOP_ID", "")
    if loop_id:
        safe_id = f"{loop_id.replace('/', '_')}__{safe_id}"
    return _state_dir() / f"{safe_id}_execution.json"


# Task 3.9: hard max iterations (configurable, default 50)
def _max_loop_iterations() -> int:
    """Read loop limit from env each call (allows runtime change)."""
    try:
        return int(os.environ.get("AHD_MAX_LOOP_ITERATIONS", "50"))
    except (TypeError, ValueError):
        return 50


DEFAULT_BATCH_SIZE = 5


# ---------------------------------------------------------------------------
# Load/save state
# ---------------------------------------------------------------------------

def _load_workflow(path: str) -> dict | None:
    """Load compiled workflow file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor_async] Cannot read workflow {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict) or "workflow_id" not in data or "tasks" not in data:
        print(f"[dag_executor_async] Workflow invalid format: missing workflow_id or tasks", file=sys.stderr)
        return None
    return data


def _load_state(workflow_id: str) -> dict | None:
    """Load execution state from file."""
    f = _state_file(workflow_id)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor_async] Error reading state {workflow_id}: {exc}", file=sys.stderr)
        return None


def _save_state(state: dict) -> bool:
    """Save execution state to file."""
    wf_id = state.get("workflow_id", "unknown")
    f = _state_file(wf_id)
    try:
        f.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        # Task 3.9: immutable state log (append-only Merkle chain)
        try:
            from loop_memory_sync import append_state_log
            append_state_log(
                _repo_root(), str(state.get("workflow_id", "")), "dag_state_saved",
                {"step": state.get("last_executed_step", ""), "status": state.get("status", "")},
            )
        except (ImportError, ModuleNotFoundError):
            pass
        return True
    except OSError as exc:
        print(f"[dag_executor_async] Error saving state: {exc}", file=sys.stderr)
        return False


def _init_state(workflow: dict) -> dict:
    """Initialize execution state from workflow."""
    wf_id = workflow["workflow_id"]
    tasks_def = workflow.get("tasks", [])
    state = {
        "workflow_id": wf_id,
        "tasks": {},
    }
    for task in tasks_def:
        tid = task.get("id")
        if not tid:
            continue
        state["tasks"][tid] = {
            "status": "pending",
            "result": None,
            "completed_at": None,
            "dependencies": task.get("dependencies", []),
            "goal": task.get("goal", ""),
            "agent": task.get("agent", ""),
        }
    # Check for cycles.
    cycle = _detect_cycle(state["tasks"])
    if cycle:
        print(f"[dag_executor_async] Cycle detected: {' -> '.join(cycle)}", file=sys.stderr)
        return {}
    # Mark ready tasks.
    _mark_ready(state)
    return state


# ---------------------------------------------------------------------------
# DAG analysis
# ---------------------------------------------------------------------------

def _detect_cycle(tasks: dict) -> list[str]:
    """Detect cycle in DAG using DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in tasks}
    stack: list[str] = []

    def dfs(node: str) -> list[str]:
        color[node] = GRAY
        stack.append(node)
        for dep in tasks.get(node, {}).get("dependencies", []):
            if dep not in tasks:
                continue
            if color[dep] == GRAY:
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
    """Check if task is ready (all dependencies complete)."""
    deps = tasks.get(tid, {}).get("dependencies", [])
    for dep in deps:
        if dep not in tasks:
            return False
        if tasks[dep].get("status") != "complete":
            return False
    return True


def _mark_ready(state: dict) -> None:
    """Mark pending tasks with satisfied dependencies as ready."""
    tasks = state.get("tasks", {})
    for tid, info in tasks.items():
        if info.get("status") == "pending":
            if _is_ready(tid, tasks):
                info["status"] = "ready"


def _get_ready_tasks(state: dict, batch_size: int) -> list[str]:
    """Get list of ready tasks, up to batch_size."""
    tasks = state.get("tasks", {})
    ready = [tid for tid, info in tasks.items() if info.get("status") == "ready"]
    return ready[:batch_size]


def _get_status_summary(state: dict) -> dict:
    """Summarize workflow status."""
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


# ---------------------------------------------------------------------------
# Async execution
# ---------------------------------------------------------------------------

@dataclass
class ExecResult:
    """Result of full DAG execution."""
    success: bool
    status: dict
    results: dict[str, Any]
    error: str | None = None


async def _run_task_async(
    task_id: str,
    task_info: dict,
    runner: Callable[[str, str], Any],
    max_retries: int,
    run_id: str,
    cancel_token,
) -> Any:
    """Run a single task with idempotency + retry + cancellation support."""
    goal = task_info.get("goal", "")
    attempts = 0
    last_exc: Exception | None = None

    async def _op():
        return await runner(task_id, goal)

    while attempts <= max_retries:
        if cancel_token.cancelled:
            raise asyncio.CancelledError("Execution cancelled")

        try:
            return await idempotency_module.register_async(
                f"{run_id}:{task_id}",
                _op,
                run_id=run_id,
            )
        except idempotency_module.IdempotencyLockError as exc:
            raise IdempotencyBlockedError(task_id, str(exc)) from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            # Check if transient (simplified - in practice, use more sophisticated detection)
            if not isinstance(exc, (asyncio.TimeoutError, ConnectionError, TimeoutError)):
                break
            attempts += 1
            await asyncio.sleep(2 ** attempts)  # Exponential backoff

    raise last_exc or RuntimeError(f"task {task_id} failed after {max_retries} retries")


class IdempotencyBlockedError(RuntimeError):
    """Execution blocked due to idempotency lock failure (fail-closed)."""

    def __init__(self, task_id: str, detail: str):
        super().__init__(f"idempotency lock failure blocked task '{task_id}': {detail}")
        self.task_id = task_id


async def execute_async(
    workflow: dict,
    checkpoint: dict | None = None,
    batch_size: int = 5,
    runner: Callable[[str, str], Any] | None = None,
    max_retries: int = 2,
    cancel_token: CancellationToken | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
) -> dict:
    """Async execution of DAG using AsyncTaskGraph."""
    from runtime import AsyncTaskGraph, Task, TaskStatus, CancellationToken

    if cancel_token is None:
        cancel_token = CancellationToken()

    if runner is None:
        async def default_runner(task_id: str, goal: str) -> dict:
            return {"ok": True, "task_id": task_id, "goal": goal}

    # Initialize or resume state
    if checkpoint is not None:
        state = checkpoint
    else:
        state = _load_state(os.environ.get("AHD_RUN_ID", ""))

    if not state:
        workflow_data = _load_workflow("")  # This would need the workflow path
        # For now, require explicit state
        raise ValueError("Checkpoint or run_id required for async execution")

    wf_id = state.get("workflow_id", "")
    os.environ["AHD_RUN_ID"] = wf_id

    # T2.7/T3.5: reset running tasks to pending on resume
    for tid, info in state.get("tasks", {}).items():
        if info.get("status") == "running":
            info["status"] = "pending"

    cancel_token = CancellationToken()
    token_budget = TokenBudget(budget_usd=10.0)  # Default budget
    cost_optimizer = CostOptimizer()
    stream_adapter = StreamAdapter()

    iteration = 0
    while True:
        if cancel_token.cancelled:
            return {"success": False, "error": "Cancelled"}

        # Mark ready tasks
        _mark_ready(state)

        # Get ready tasks
        batch = _get_ready_tasks(state, 5)  # batch_size

        if not batch:
            summary = _get_status_summary(state)
            if summary.get("all_complete"):
                return {"success": True, "status": summary, "results": {}}
            if summary.get("any_failed"):
                return {"success": False, "error": "Tasks failed"}
            # Deadlock
            return {"success": False, "error": "deadlock"}

        # Check max iterations
        if iteration > 50:
            return {"success": False, "error": "max iterations exceeded"}

        # Run batch
        for task_id in batch:
            state["tasks"][task_id]["status"] = "running"

        # Execute batch tasks concurrently
        async def run_task(tid):
            task_info = state["tasks"][tid]
            try:
                result = await _run_task_async(tid, state["tasks"][tid], _default_runner, 2, "")
                state["tasks"][tid]["status"] = "complete"
                state["tasks"][tid]["result"] = result
                state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()
                return tid, result
            except Exception as exc:
                state["tasks"][tid]["status"] = "failed"
                state["tasks"][tid]["result"] = {"error": str(exc)}
                state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()
                return tid, exc

        tasks = [run_task(tid) for tid in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for tid, result in zip(batch, results):
            if isinstance(result, Exception):
                state["tasks"][tid]["status"] = "failed"
                state["tasks"][tid]["result"] = {"error": str(result)}
            else:
                state["tasks"][tid]["status"] = "complete"
                state["tasks"][tid]["result"] = result
                state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()

        _save_state(state)

    return {"success": True, "status": _get_status_summary({}), "results": {}}


# Placeholder for CLI compatibility
def main(argv: list[str] | None = None) -> int:
    print("[dag_executor_async] Not yet fully implemented - use dag_executor.py for now")
    return 1


if __name__ == "__main__":
    sys.exit(main())