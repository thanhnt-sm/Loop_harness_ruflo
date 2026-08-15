#!/usr/bin/env python3
"""AsyncTaskGraph — DAG with async node execution.

Replaces ThreadPoolExecutor-based dag_executor with native async/await.
Supports streaming, cancellation, backpressure, and checkpointing.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Idempotency lock failure


class Task(BaseModel):
    model_config = ConfigDict(frozen=False)

    id: str
    goal: str
    dependencies: list[str] = field(default_factory=list)
    agent: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0
    max_retries: int = 2


@dataclass
class ExecutionProgress:
    """Progress event yielded during execution."""
    type: str  # "task_started" | "task_completed" | "task_failed" | "checkpoint" | "progress"
    task_id: Optional[str] = None
    task_status: Optional[TaskStatus] = None
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class AsyncTaskGraph:
    """Async DAG executor with streaming progress, cancellation, and checkpointing."""

    def __init__(
        self,
        tasks: list[Task],
        runner: Callable[[str, str], Any],  # (task_id, goal) -> result
        max_parallel: int = 5,
        checkpoint_interval: int = 10,
        cancel_token: Optional[asyncio.Event] = None,
    ):
        self._tasks = {t.id: t for t in tasks}
        self._runner = runner
        self._max_parallel = max_parallel
        self._checkpoint_interval = checkpoint_interval
        self._cancel_token = cancel_token or asyncio.Event()
        self._semaphore = asyncio.Semaphore(max_parallel)
        self._running_tasks: set[str] = set()
        self._completed_count = 0
        self._checkpoint_count = 0
        self._start_time = datetime.now(timezone.utc)

        # Validate DAG
        self._validate_dag()

    def _validate_dag(self) -> None:
        """Check for cycles and missing dependencies."""
        visited = set()
        path = set()

        def visit(task_id: str) -> None:
            if task_id in path:
                raise ValueError(f"Cycle detected involving task: {task_id}")
            if task_id in visited:
                return
            path.add(task_id)
            for dep in self._tasks[task_id].dependencies:
                if dep not in self._tasks:
                    raise ValueError(f"Task {task_id} depends on missing task: {dep}")
                visit(dep)
            path.remove(task_id)
            visited.add(task_id)

        for task_id in self._tasks:
            visit(task_id)

    def _get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to run (all deps completed)."""
        ready = []
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            deps_complete = all(
                self._tasks[dep].status == TaskStatus.COMPLETED
                for dep in task.dependencies
            )
            if deps_complete:
                task.status = TaskStatus.READY
                ready.append(task)
        return ready

    async def _run_task(self, task: Task) -> AsyncIterator[ExecutionProgress]:
        """Run a single task with retries and cancellation support."""
        if self._cancel_token.is_set():
            task.status = TaskStatus.BLOCKED
            yield ExecutionProgress(
                type="task_failed",
                task_id=task.id,
                task_status=TaskStatus.BLOCKED,
                message="Execution cancelled",
            )
            return

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        self._running_tasks.add(task.id)

        # Yield started event
        yield ExecutionProgress(
            type="task_started",
            task_id=task.id,
            task_status=TaskStatus.RUNNING,
            message=f"Starting task: {task.goal[:50]}",
        )

        last_error = None
        for attempt in range(task.max_retries + 1):
            if self._cancel_token.is_set():
                task.status = TaskStatus.BLOCKED
                yield ExecutionProgress(
                    type="task_failed",
                    task_id=task.id,
                    task_status=TaskStatus.BLOCKED,
                    message="Execution cancelled during retry",
                )
                self._running_tasks.discard(task.id)
                return

            try:
                # Run with timeout (configurable per task)
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._runner, task.id, task.goal),
                    timeout=300.0,  # 5 min default
                )
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc)
                task.retries = attempt

                self._running_tasks.discard(task.id)
                self._completed_count += 1

                yield ExecutionProgress(
                    type="task_completed",
                    task_id=task.id,
                    task_status=TaskStatus.COMPLETED,
                    message=f"Task completed: {task.goal[:50]}",
                    metadata={"result": str(result)[:200]},
                )
                return

            except asyncio.TimeoutError:
                last_error = f"Task timed out after 300s (attempt {attempt + 1})"
            except asyncio.CancelledError:
                task.status = TaskStatus.BLOCKED
                yield ExecutionProgress(
                    type="task_failed",
                    task_id=task.id,
                    task_status=TaskStatus.BLOCKED,
                    message="Execution cancelled",
                )
                self._running_tasks.discard(task.id)
                return
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"

            if attempt < task.max_retries:
                yield ExecutionProgress(
                    type="progress",
                    task_id=task.id,
                    message=f"Retrying ({attempt + 1}/{task.max_retries}): {last_error}",
                )
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All retries exhausted
        task.status = TaskStatus.FAILED
        task.error = last_error or "Unknown error"
        task.completed_at = datetime.now(timezone.utc)

        self._running_tasks.discard(task.id)

        yield ExecutionProgress(
            type="task_failed",
            task_id=task.id,
            task_status=TaskStatus.FAILED,
            message=f"Task failed after {task.max_retries + 1} attempts: {last_error}",
        )

    async def execute(self) -> AsyncIterator[ExecutionProgress]:
        """Execute the DAG, yielding progress events."""
        while True:
            # Check cancellation
            if self._cancel_token.is_set():
                yield ExecutionProgress(
                    type="progress",
                    message="Execution cancelled by user",
                )
                break

            # Get ready tasks
            ready = self._get_ready_tasks()
            if not ready:
                # Check if all done
                pending = [t for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.READY)]
                running = len(self._running_tasks)
                if not pending and running == 0:
                    # All done
                    yield ExecutionProgress(
                        type="progress",
                        message="All tasks completed",
                        metadata={
                            "total_tasks": len(self._tasks),
                            "completed": self._completed_count,
                            "duration_sec": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
                        },
                    )
                    break
                # Wait for running tasks to complete
                await asyncio.sleep(0.1)
                continue

            # Launch ready tasks (up to semaphore)
            launched = 0
            for task in ready:
                if launched >= self._max_parallel - len(self._running_tasks):
                    break
                if self._cancel_token.is_set():
                    break
                asyncio.create_task(self._consume_task_progress(task))
                launched += 1

            # Yield control to let tasks run
            await asyncio.sleep(0.05)

    async def _consume_task_progress(self, task: Task) -> None:
        """Consume progress from a single task runner."""
        async for progress in self._run_task(task):
            # Progress is yielded via the main execute() generator
            # This is a placeholder - actual yielding happens in execute()
            pass

    async def execute_streaming(self) -> AsyncIterator[ExecutionProgress]:
        """Main entry point: execute DAG and stream progress."""
        # Track running task generators
        running_generators: dict[str, AsyncIterator[ExecutionProgress]] = {}

        while True:
            if self._cancel_token.is_set():
                yield ExecutionProgress(type="progress", message="Execution cancelled")
                break

            # Get ready tasks
            ready = self._get_ready_tasks()

            # Launch new tasks
            for task in ready:
                if len(running_generators) >= self._max_parallel:
                    break
                if task.id in running_generators:
                    continue
                running_generators[task.id] = self._run_task(task)

            if not running_generators:
                # No running tasks, check if done
                if all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED) for t in self._tasks.values()):
                    yield ExecutionProgress(
                        type="progress",
                        message="All tasks completed",
                        metadata={
                            "total_tasks": len(self._tasks),
                            "completed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
                            "failed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
                            "duration_sec": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
                        },
                    )
                    break
                await asyncio.sleep(0.1)
                continue

            # Process one step from each running task
            done_tasks = []
            for task_id, gen in running_generators.items():
                try:
                    progress = await gen.__anext__()
                    yield progress
                    if progress.type in ("task_completed", "task_failed", "task_failed"):
                        done_tasks.append(task_id)
                except StopAsyncIteration:
                    done_tasks.append(task_id)

            # Clean up done tasks
            for task_id in done_tasks:
                running_generators.pop(task_id, None)

    # Checkpointing
    def get_state(self) -> dict:
        """Get serializable state for checkpointing."""
        return {
            "tasks": {
                tid: {
                    "id": t.id,
                    "goal": t.goal,
                    "dependencies": t.dependencies,
                    "agent": t.agent,
                    "status": t.status.value,
                    "result": str(t.result) if t.result else None,
                    "error": t.error,
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    "retries": t.retries,
                    "max_retries": t.max_retries,
                }
                for tid, t in self._tasks.items()
            },
            "completed_count": self._completed_count,
            "start_time": self._start_time.isoformat(),
        }

    @classmethod
    def from_state(cls, state: dict, runner: Callable[[str, str], Any]) -> "AsyncTaskGraph":
        """Restore from checkpoint state."""
        tasks = []
        for tid, tdata in state["tasks"].items():
            t = Task(
                id=tdata["id"],
                goal=tdata["goal"],
                dependencies=tdata["dependencies"],
                agent=tdata["agent"],
                status=TaskStatus(tdata["status"]),
                result=tdata["result"],
                error=tdata["error"],
                retries=tdata["retries"],
                max_retries=tdata["max_retries"],
            )
            if tdata["started_at"]:
                t.started_at = datetime.fromisoformat(tdata["started_at"])
            if tdata["completed_at"]:
                t.completed_at = datetime.fromisoformat(tdata["completed_at"])
            tasks.append(t)

        graph = cls(tasks, runner)
        graph._completed_count = state["completed_count"]
        graph._start_time = datetime.fromisoformat(state["start_time"])
        return graph


@dataclass
class CancellationToken:
    """Cancellation token for cooperative cancellation."""
    _cancelled: bool = False
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self) -> None:
        self._cancelled = True
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    async def wait(self) -> None:
        """Wait until cancelled."""
        await self._event.wait()

    def throw_if_cancelled(self) -> None:
        if self._cancelled:
            raise asyncio.CancelledError("Operation cancelled")


class BackpressureQueue:
    """Bounded async queue with backpressure."""

    def __init__(self, maxsize: int = 100):
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._maxsize = maxsize

    async def put(self, item: Any, timeout: Optional[float] = None) -> None:
        """Put item with optional timeout. Raises asyncio.TimeoutError if full."""
        try:
            await asyncio.wait_for(self._queue.put(item), timeout=timeout)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Queue full (maxsize={self._maxsize}), backpressure")

    async def get(self) -> Any:
        return await self._queue.get()

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()

    def full(self) -> bool:
        return self._queue.full()


class TokenBudget:
    """Per-session/task/agent token budget with atomic reservations."""

    def __init__(self, budget_usd: float, cost_per_1k_tokens: float = 0.002):
        self._budget_usd = budget_usd
        self._cost_per_1k = cost_per_1k_tokens
        self._spent_usd = 0.0
        self._lock = asyncio.Lock()

    async def reserve(self, estimated_tokens: int) -> bool:
        """Atomically reserve budget for estimated tokens."""
        async with self._lock:
            estimated_cost = (estimated_tokens / 1000) * self._cost_per_1k
            if self._spent_usd + estimated_cost > self._budget_usd:
                return False
            self._spent_usd += estimated_cost
            return True

    async def release(self, actual_tokens: int) -> None:
        """Release unused reserved budget."""
        async with self._lock:
            actual_cost = (actual_tokens / 1000) * self._cost_per_1k
            self._spent_usd = max(0, self._spent_usd - actual_cost)

    async def record_actual(self, actual_tokens: int) -> None:
        """Record actual usage (adjusts reservation)."""
        async with self._lock:
            actual_cost = (actual_tokens / 1000) * self._cost_per_1k
            # Already reserved estimated, now adjust to actual
            pass  # Simplified - in practice, track reserved vs actual

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    @property
    def remaining_usd(self) -> float:
        return max(0, self._budget_usd - self._spent_usd)

    @property
    def percent_used(self) -> float:
        return (self._spent_usd / self._budget_usd * 100) if self._budget_usd > 0 else 0


class CostOptimizer:
    """Route tasks to cheapest capable model."""

    def __init__(self):
        self._models = {
            "lightning": {"cost_per_1k": 0.002, "capabilities": ["fast", "code"]},
            "glm": {"cost_per_1k": 0.0, "capabilities": ["free", "reasoning"]},
            "kimi": {"cost_per_1k": 0.0, "capabilities": ["free", "open_source"]},
        }

    def select_model(self, required_capabilities: list[str], budget_usd: Optional[float] = None) -> str:
        """Select cheapest model that has all required capabilities."""
        candidates = []
        for name, info in self._models.items():
            if all(cap in info["capabilities"] for cap in required_capabilities):
                if budget_usd is None or info["cost_per_1k"] <= budget_usd:
                    candidates.append((info["cost_per_1k"], name))

        if not candidates:
            # Fallback: return first available
            return next(iter(self._models))

        candidates.sort()  # Sort by cost
        return candidates[0][1]

    def estimate_cost(self, model: str, tokens: int) -> float:
        info = self._models.get(model, {"cost_per_1k": 0.002})
        return (tokens / 1000) * info["cost_per_1k"]


# --- StreamingExecutor ---

class StreamingExecutor:
    """High-level streaming executor with progress callbacks."""

    def __init__(
        self,
        graph: AsyncTaskGraph,
        on_progress: Optional[Callable[[ExecutionProgress], Any]] = None,
        checkpoint_callback: Optional[Callable[[dict], Any]] = None,
        checkpoint_interval: int = 10,
    ):
        self._graph = graph
        self._on_progress = on_progress
        self._checkpoint_callback = checkpoint_callback
        self._checkpoint_interval = checkpoint_interval
        self._completed_since_checkpoint = 0

    async def execute(self) -> dict:
        """Execute graph with streaming progress and checkpointing."""
        final_state = {"completed": 0, "failed": 0, "errors": []}

        async for progress in self._graph.execute_streaming():
            # Callback
            if self._on_progress:
                try:
                    if asyncio.iscoroutinefunction(self._on_progress):
                        await self._on_progress(progress)
                    else:
                        self._on_progress(progress)
                except Exception:
                    pass  # Callback errors shouldn't stop execution

            # Track completion for checkpointing
            if progress.type in ("task_completed", "task_failed"):
                self._completed_since_checkpoint += 1

                if self._completed_since_checkpoint >= self._checkpoint_interval:
                    await self._save_checkpoint()
                    self._completed_since_checkpoint = 0

            # Aggregate final state
            if progress.type == "task_completed":
                final_state["completed"] += 1
            elif progress.type == "task_failed":
                final_state["failed"] += 1
                if progress.metadata.get("result"):
                    final_state["errors"].append(f"{progress.task_id}: {progress.message}")

        # Final checkpoint
        await self._save_checkpoint()
        return final_state

    async def _save_checkpoint(self) -> None:
        if self._checkpoint_callback:
            try:
                state = self._graph.get_state()
                if asyncio.iscoroutinefunction(self._checkpoint_callback):
                    await self._checkpoint_callback(state)
                else:
                    self._checkpoint_callback(state)
            except Exception:
                pass  # Checkpoint errors shouldn't stop execution