#!/usr/bin/env python3
"""SessionStateAdapter — Dual-write adapter for session state.

Migrates from .devin/session_state/*.json to EventStore SessionView.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.migration_coordinator import DualWriteCoordinator, DualWriteAdapter
from state_machine_v2.event_store import EventStore


class SessionState(BaseModel):
    """Session state data model."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    goal: str = ""
    tier: str = "M"
    complexity: str = "M"
    status: str = "in_progress"
    current_subtask: str = ""
    cumulative_cost: float = 0.0
    cost_cap: float = 5.0
    cost_tracked_calls: int = 0
    last_heartbeat: Optional[str] = None
    last_tool: str = ""
    last_file: str = ""
    last_error: bool = False
    boot_complete: bool = False
    context_oversized: bool = False
    oversized_tool_calls_since_flag: int = 0
    oversized_first_detected: Optional[str] = None
    file_shas: dict = field(default_factory=dict)
    verify_status: dict = field(default_factory=dict)
    quality_scores: dict = field(default_factory=dict)
    done_declared: bool = False
    fable_judge_required: bool = False
    skill_suggestions: list = field(default_factory=list)
    skill_suggested_at: Optional[str] = None
    candidate_memory: list = field(default_factory=list)
    iteration_count: int = 0
    last_state_write_iteration: int = 0
    budget_exceeded: bool = False
    total_cost: float = 0.0
    budget_cap: float = 0.0
    time_limit_seconds: int = 0
    started_at: Optional[str] = None
    state_write_failures: int = 0
    last_memory_confidence: int = 100
    last_memory_source: str = ""

    def model_post_init(self, __context):
        from dataclasses import field
        pass


class SessionStateAdapter(DualWriteAdapter):
    """Dual-write adapter for session state.

    Migrates from .devin/session_state/*.json to EventStore SessionView.
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
        self._legacy_dir = legacy_root / ".devin" / "session_state"
        self._locks: dict[str, asyncio.Lock] = {}
        self._logger = logging.getLogger("session_state_adapter")

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        """Get or create per-session lock."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def _legacy_path(self, session_id: str) -> Path:
        """Get legacy session state file path."""
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return self._legacy_dir / f"{safe_id}.json"

    async def _read_legacy(self, session_id: str) -> Optional[SessionState]:
        """Read session state from legacy file."""
        path = self._legacy_path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SessionState.model_validate(data)
        except Exception as e:
            self._logger.warning(f"Failed to read legacy session {session_id}: {e}")
            return None

    async def _write_legacy(self, state: SessionState) -> None:
        """Write session state to legacy file."""
        path = self._legacy_path(state.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    async def get(self, session_id: str) -> Optional[SessionState]:
        """Get session state (reads from EventStore primary, legacy fallback)."""
        # Try EventStore first (primary)
        try:
            session = await self._event_store.sessions.get(session_id)
            if session:
                return SessionState.model_validate(session)
        except Exception as e:
            self._logger.warning(f"EventStore read failed for {session_id}: {e}")

        # Fallback to legacy
        return await self._read_legacy(session_id)

    async def set(
        self,
        state: SessionState,
        saga_id: Optional[str] = None,
    ) -> None:
        """Set session state (dual-write to EventStore + legacy)."""
        lock = self._get_lock(state.session_id)
        async with lock:
            saga_id = saga_id or f"session-{state.session_id}-{uuid.uuid4().hex[:8]}"

            async def primary_write():
                await self._event_store.sessions.upsert(
                    state.session_id,
                    state.model_dump(mode="json"),
                )

            async def secondary_write():
                await self._write_legacy(state)

            async def primary_rollback():
                # EventStore doesn't support delete easily, mark as rolled back
                await self._event_store.sessions.upsert(
                    state.session_id,
                    {**state.model_dump(mode="json"), "status": "rolled_back"},
                )

            async def secondary_rollback():
                # Restore previous legacy state if possible
                pass  # Could restore from backup

            await self.dual_write(
                saga_id,
                primary_write,
                secondary_write,
                primary_rollback,
                secondary_rollback,
            )

    async def heartbeat(
        self,
        session_id: str,
        tool: str,
        cost: float = 0.0,
        saga_id: Optional[str] = None,
    ) -> None:
        """Update session heartbeat (dual-write)."""
        lock = self._get_lock(session_id)
        async with lock:
            state = await self.get(session_id)
            if not state:
                return

            state.last_heartbeat = datetime.now(timezone.utc).isoformat()
            state.last_tool = tool
            state.cumulative_cost = round(state.cumulative_cost + cost, 6)
            state.cost_tracked_calls += 1

            await self.set(state, saga_id)

    async def update_cost(self, session_id: str, cost: float, saga_id: Optional[str] = None) -> None:
        """Update cumulative cost (dual-write)."""
        lock = self._get_lock(session_id)
        async with lock:
            state = await self.get(session_id)
            if not state:
                return

            state.cumulative_cost = round(state.cumulative_cost + cost, 6)
            state.cost_tracked_calls += 1

            await self.set(state, saga_id)

    async def update_tool(self, session_id: str, tool: str, saga_id: Optional[str] = None) -> None:
        """Update last tool used (dual-write)."""
        lock = self._get_lock(session_id)
        async with lock:
            state = await self.get(session_id)
            if not state:
                return

            state.last_tool = tool

            await self.set(state, saga_id)

    async def update_file(self, session_id: str, file: str, saga_id: Optional[str] = None) -> None:
        """Update last file (dual-write)."""
        lock = self._get_lock(session_id)
        async with lock:
            state = await self.get(session_id)
            if not state:
                return

            state.last_file = file

            await self.set(state, saga_id)

    async def set_error(self, session_id: str, error: bool, saga_id: Optional[str] = None) -> None:
        """Set error flag (dual-write)."""
        lock = self._get_lock(session_id)
        async with lock:
            state = await self.get(session_id)
            if not state:
                return

            state.last_error = error

            await self.set(state, saga_id)

    async def update_context_flag(
        self,
        session_id: str,
        flag: str,
        value: Any,
        saga_id: Optional[str] = None,
    ) -> None:
        """Update context flag (dual-write)."""
        lock = self._get_lock(session_id)
        async with lock:
            state = await self.get(session_id)
            if not state:
                return

            setattr(state, flag, value)

            await self.set(state, saga_id)

    async def increment_iteration(self, session_id: str, saga_id: Optional[str] = None) -> None:
        """Increment iteration count (dual-write)."""
        lock = self._get_lock(session_id)
        async with lock:
            state = await self.get(session_id)
            if not state:
                return

            state.iteration_count += 1

            await self.set(state, saga_id)


from dataclasses import field