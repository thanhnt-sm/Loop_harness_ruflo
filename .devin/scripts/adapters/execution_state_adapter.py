#!/usr/bin/env python3
"""ExecutionStateAdapter — Dual-write adapter for execution state.

Migrates from .devin/checkpoints/ and .devin/plan_state/*_execution.json
to EventStore ExecutionView.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.migration_coordinator import DualWriteCoordinator, DualWriteAdapter
from state_machine_v2.event_store import EventStore


class ExecutionState(BaseModel):
    """Execution state data model."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    task_id: str = ""
    status: str = "pending"  # pending, ready, running, completed, failed, blocked
    goal: str = ""
    agent: str = ""
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retries: int = 0
    max_retries: int = 2


class ExecutionStateAdapter(DualWriteAdapter):
    """Dual-write adapter for execution state.

    Migrates from .devin/checkpoints/ and .devin/plan_state/*_execution.json
    to EventStore ExecutionView.
    """

    def __init__(
        self,
        dual_write_coordinator: DualWriteCoordinator,
        event_store: EventStore,
        legacy_root: Path,
    ):
        super().__init__(dual_write_coordinator)
        self._event_store = event_store
        self._legacy_root = legacy_root
        self._checkpoints_dir = legacy_root / ".devin" / "checkpoints"
        self._plan_state_dir = legacy_root / ".devin" / "plan_state"
        self._locks: dict[str, asyncio.Lock] = {}
        self._logger = logging.getLogger("execution_state_adapter")

    def _get_lock(self, run_id: str) -> asyncio.Lock:
        """Get or create per-run lock."""
        if run_id not in self._locks:
            self._locks[run_id] = asyncio.Lock()
        return self._locks[run_id]

    def _legacy_execution_path(self, run_id: str) -> Path:
        """Get legacy execution state file path."""
        safe_id = run_id.replace("/", "_").replace("\\", "_")
        return self._plan_state_dir / f"{safe_id}_execution.json"

    def _legacy_checkpoint_path(self, run_id: str, step_id: str = "checkpoint") -> Path:
        """Get legacy checkpoint file path."""
        safe_id = run_id.replace("/", "_").replace("\\", "_")
        safe_step = step_id.replace("/", "_").replace("\\", "_")
        return self._checkpoints_dir / f"{safe_id}_{safe_step}.json"

    async def _read_legacy_execution(self, run_id: str) -> Optional[dict]:
        """Read execution state from legacy file."""
        path = self._legacy_execution_path(run_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            self._logger.warning(f"Failed to read legacy execution {run_id}: {e}")
            return None

    async def _write_legacy_execution(self, run_id: str, state: dict) -> None:
        """Write execution state to legacy file."""
        path = self._legacy_execution_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _read_legacy_checkpoint(self, run_id: str, step_id: str = "checkpoint") -> Optional[dict]:
        """Read checkpoint from legacy file."""
        path = self._legacy_checkpoint_path(run_id, step_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            self._logger.warning(f"Failed to read legacy checkpoint {run_id}: {e}")
            return None

    async def _write_legacy_checkpoint(self, run_id: str, step_id: str, state: dict) -> None:
        """Write checkpoint to legacy file."""
        path = self._legacy_checkpoint_path(run_id, step_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    async def get_task(self, run_id: str, task_id: str) -> Optional[ExecutionState]:
        """Get task execution state."""
        # Try EventStore first
        try:
            task = await self._event_store.executions.get_task(run_id, task_id)
            if task:
                return ExecutionState.model_validate(task)
        except Exception as e:
            self._logger.warning(f"EventStore read failed for {run_id}:{task_id}: {e}")

        # Fallback to legacy execution state
        legacy = await self._read_legacy_execution(run_id)
        if legacy and "tasks" in legacy and task_id in legacy["tasks"]:
            task_data = legacy["tasks"][task_id]
            return ExecutionState(
                run_id=run_id,
                task_id=task_id,
                **task_data,
            )
        return None

    async def set_task(
        self,
        run_id: str,
        task_id: str,
        state: ExecutionState,
        saga_id: Optional[str] = None,
    ) -> None:
        """Set task execution state (dual-write)."""
        lock = self._get_lock(run_id)
        async with lock:
            saga_id = saga_id or f"task-{run_id}-{task_id}-{uuid.uuid4().hex[:8]}"

            async def primary_write():
                await self._event_store.executions.upsert_task(
                    run_id, task_id, state.model_dump(mode="json")
                )

            async def secondary_write():
                legacy = await self._read_legacy_execution(run_id) or {"tasks": {}}
                legacy["tasks"][task_id] = state.model_dump(mode="json")
                await self._write_legacy_execution(run_id, legacy)

            async def primary_rollback():
                await self._event_store.executions.upsert_task(
                    run_id, task_id, {"status": "rolled_back"}
                )

            async def secondary_rollback():
                pass

            await self.dual_write(
                saga_id,
                primary_write,
                secondary_write,
                primary_rollback,
                secondary_rollback,
            )

    async def get_task_status(self, run_id: str, task_id: str) -> Optional[str]:
        """Get task status."""
        task = await self.get_task(run_id, task_id)
        return task.status if task else None

    async def checkpoint(
        self,
        run_id: str,
        state: dict,
        step_id: str = "checkpoint",
        saga_id: Optional[str] = None,
    ) -> None:
        """Save checkpoint (dual-write)."""
        lock = self._get_lock(run_id)
        async with lock:
            saga_id = saga_id or f"checkpoint-{run_id}-{step_id}-{uuid.uuid4().hex[:8]}"

            async def primary_write():
                await self._event_store.executions.checkpoint(run_id, state)

            async def secondary_write():
                await self._write_legacy_checkpoint(run_id, step_id, state)

            async def primary_rollback():
                # Checkpoints are immutable, no rollback
                pass

            async def secondary_rollback():
                pass

            await self.dual_write(
                saga_id,
                primary_write,
                secondary_write,
                primary_rollback,
                secondary_rollback,
            )

    async def get_checkpoint(self, run_id: str, step_id: str = "checkpoint") -> Optional[dict]:
        """Get checkpoint."""
        try:
            return await self._event_store.executions.get_checkpoint(run_id)
        except Exception:
            pass
        return await self._read_legacy_checkpoint(run_id, step_id)

    async def list_tasks(self, run_id: str) -> list[ExecutionState]:
        """List all tasks for a run."""
        try:
            return await self._event_store.executions.list_tasks(run_id)
        except Exception:
            pass
        legacy = await self._read_legacy_execution(run_id)
        if legacy and "tasks" in legacy:
            tasks = []
            for task_id, task_data in legacy["tasks"].items():
                tasks.append(ExecutionState(run_id=run_id, task_id=task_id, **task_data))
            return tasks
        return []

    async def _read_legacy_execution(self, run_id: str) -> Optional[dict]:
        path = self._legacy_execution_path(run_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            self._logger.warning(f"Failed to read legacy execution {run_id}: {e}")
            return None

    async def _write_legacy_execution(self, run_id: str, state: dict) -> None:
        path = self._legacy_execution_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _read_legacy_checkpoint(self, run_id: str, step_id: str) -> Optional[dict]:
        path = self._legacy_checkpoint_path(run_id, step_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def _write_legacy_checkpoint(self, run_id: str, step_id: str, state: dict) -> None:
        path = self._legacy_checkpoint_path(run_id, step_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


from dataclasses import field