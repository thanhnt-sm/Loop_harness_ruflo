#!/usr/bin/env python3
"""PlanStateAdapter — Dual-write adapter for plan state.

Migrates from .devin/plan_state/*.json to EventStore PlanView.
"""
from __future__ import annotations

import asyncio
import hashlib
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


class PlanState(BaseModel):
    """Plan state data model."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    plan_file: str
    artifact: str = ""
    status: str = "pending"
    reviewer: str = ""
    date: str = ""
    comments: str = ""
    plan_hash: str = ""
    signature: str = ""
    file_hashes: dict = field(default_factory=dict)
    artifact_path: str = ""
    artifact_type: str = "plan"  # "plan" or "sd"
    approval_round: int = 0
    rejection_reason: str = ""
    modifications: str = ""


class PlanStateAdapter(DualWriteAdapter):
    """Dual-write adapter for plan state.

    Migrates from .devin/plan_state/*.json to EventStore PlanView.
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
        self._legacy_dir = legacy_root / ".devin" / "plan_state"
        self._locks: dict[str, asyncio.Lock] = {}
        self._logger = logging.getLogger("plan_state_adapter")

    def _get_lock(self, plan_id: str) -> asyncio.Lock:
        """Get or create per-plan lock."""
        if plan_id not in self._locks:
            self._locks[plan_id] = asyncio.Lock()
        return self._locks[plan_id]

    def _legacy_path(self, plan_id: str) -> Path:
        """Get legacy plan state file path."""
        safe_id = plan_id.replace("/", "_").replace("\\", "_")
        return self._legacy_dir / f"{safe_id}.json"

    def _plan_id_from_path(self, plan_path: Path) -> str:
        """Extract plan ID from plan file path."""
        # plan_path is like: /repo/docs/plans/task_slug/SOLUTION_DESIGN.md
        # or /repo/docs/plans/task_slug/IMPLEMENTATION_PLAN.md
        parts = plan_path.parts
        try:
            idx = parts.index("plans")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        except ValueError:
            pass
        return plan_path.stem

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _compute_plan_hash(self, plan_path: Path) -> str:
        """Compute SHA-256 hash of plan file content."""
        content = plan_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    async def _read_legacy(self, plan_id: str) -> Optional[PlanState]:
        """Read plan state from legacy file."""
        path = self._legacy_path(plan_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PlanState.model_validate(data)
        except Exception as e:
            self._logger.warning(f"Failed to read legacy plan {plan_id}: {e}")
            return None

    async def _write_legacy(self, state: PlanState) -> None:
        """Write plan state to legacy file."""
        path = self._legacy_path(state.plan_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def _extract_plan_id(self, plan_file: str) -> str:
        """Extract plan_id from plan_file path."""
        path = Path(plan_file)
        return self._plan_id_from_path(path)

    async def get(self, plan_file: str) -> Optional[PlanState]:
        """Get plan state (reads from EventStore primary, legacy fallback)."""
        plan_id = self._extract_plan_id(plan_file)

        # Try EventStore first (primary)
        try:
            plan = await self._event_store.plans.get(plan_id)
            if plan:
                return PlanState.model_validate(plan)
        except Exception as e:
            self._logger.warning(f"EventStore read failed for {plan_id}: {e}")

        # Fallback to legacy
        return await self._read_legacy(plan_id)

    async def set(
        self,
        state: PlanState,
        saga_id: Optional[str] = None,
    ) -> None:
        """Set plan state (dual-write to EventStore + legacy)."""
        plan_id = self._extract_plan_id(state.plan_file)
        lock = self._get_lock(plan_id)
        async with lock:
            saga_id = saga_id or f"plan-{plan_id}-{uuid.uuid4().hex[:8]}"

            async def primary_write():
                if state.status == "approved":
                    # First upsert full state to preserve all fields including plan_file
                    await self._event_store.plans.upsert(
                        plan_id,
                        state.model_dump(mode="json"),
                    )
                    # Then mark as approved
                    await self._event_store.plans.approve(
                        plan_id,
                        state.reviewer,
                        state.signature,
                        state.plan_hash,
                    )
                elif state.status == "rejected":
                    # First upsert full state to preserve all fields including plan_file
                    await self._event_store.plans.upsert(
                        plan_id,
                        state.model_dump(mode="json"),
                    )
                    # Then mark as rejected
                    await self._event_store.plans.reject(
                        plan_id,
                        state.reviewer,
                        state.rejection_reason,
                    )
                else:
                    # For pending/changes_requested, just upsert
                    await self._event_store.plans.upsert(
                        plan_id,
                        state.model_dump(mode="json"),
                    )

            async def secondary_write():
                await self._write_legacy(state)

            async def primary_rollback():
                await self._event_store.plans.upsert(
                    plan_id,
                    {**state.model_dump(mode="json"), "status": "rolled_back"},
                )

            async def secondary_rollback():
                pass  # Could restore from backup

            await self.dual_write(
                saga_id,
                primary_write,
                secondary_write,
                primary_rollback,
                secondary_rollback,
            )

    async def approve(
        self,
        plan_file: str,
        reviewer: str,
        signature: str,
        plan_hash: str,
        saga_id: Optional[str] = None,
    ) -> None:
        """Approve plan (dual-write)."""
        plan_id = self._extract_plan_id(plan_file)
        lock = self._get_lock(plan_id)
        async with lock:
            state = await self.get(plan_file)
            if not state:
                state = PlanState(plan_file=plan_file)

            state.status = "approved"
            state.reviewer = reviewer
            state.signature = signature
            state.plan_hash = plan_hash
            state.date = datetime.now(timezone.utc).isoformat()

            await self.set(state, saga_id)

    async def reject(
        self,
        plan_file: str,
        reviewer: str,
        reason: str,
        saga_id: Optional[str] = None,
    ) -> None:
        """Reject plan (dual-write)."""
        plan_id = self._extract_plan_id(plan_file)
        lock = self._get_lock(plan_id)
        async with lock:
            state = await self.get(plan_file)
            if not state:
                state = PlanState(plan_file=plan_file)

            state.status = "rejected"
            state.reviewer = reviewer
            state.rejection_reason = reason
            state.date = datetime.now(timezone.utc).isoformat()

            await self.set(state, saga_id)

    async def request_changes(
        self,
        plan_file: str,
        reviewer: str,
        modifications: str,
        saga_id: Optional[str] = None,
    ) -> None:
        """Request changes to plan (dual-write)."""
        plan_id = self._extract_plan_id(plan_file)
        lock = self._get_lock(plan_id)
        async with lock:
            state = await self.get(plan_file)
            if not state:
                state = PlanState(plan_file=plan_file)

            state.status = "changes_requested"
            state.reviewer = reviewer
            state.modifications = modifications
            state.approval_round = state.approval_round + 1
            state.date = datetime.now(timezone.utc).isoformat()

            await self.set(state, saga_id)

    async def update_file_hashes(
        self,
        plan_file: str,
        saga_id: Optional[str] = None,
    ) -> None:
        """Update file hashes for plan (dual-write)."""
        plan_id = self._extract_plan_id(plan_file)
        lock = self._get_lock(plan_id)
        async with lock:
            state = await self.get(plan_file)
            if not state:
                state = PlanState(plan_file=plan_file)

            # Compute hashes for referenced files
            root = Path(self._legacy_root).parent.parent.parent  # repo root
            hashes = {}
            try:
                content = (root / plan_file).read_text()
                import re
                file_paths = re.findall(r"`([^`]*[/\\][^`]*)`", content)
                for fp in file_paths:
                    rel = fp.replace("\\", "/").lstrip("/")
                    candidate = root / rel
                    if candidate.exists():
                        hashes[rel] = self._compute_file_hash(candidate)
            except Exception:
                pass

            state.file_hashes = hashes
            state.plan_hash = self._compute_plan_hash(root / plan_file)

            await self.set(state, saga_id)


from dataclasses import field
from datetime import datetime, timezone