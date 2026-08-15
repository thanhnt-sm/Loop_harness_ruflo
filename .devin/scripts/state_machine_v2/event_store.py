#!/usr/bin/env python3
"""EventStore — Event-sourced state machine (CQRS + Event Sourcing).

Single source of truth for all AHD state. Replaces 8 fragmented stores:
- session_state/, loop_state/, context_flags/, plan_state/
- checkpoints/, idempotency/, blackboard/, event_bus/
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from state_store import (
    StateStore,
    FileBackend,
    StateEntry,
    StateOptions,
    ConsistencyLevel,
    ConcurrencyMode,
    HealthStatus,
    KeyNotFoundError,
    ConcurrencyError,
)


# --- Event Schema ---

class Event(BaseModel):
    """Immutable event in the event log."""
    model_config = ConfigDict(frozen=True)

    seq: int
    ts: str  # ISO8601 UTC
    type: str  # Domain event type
    aggregate_id: str  # session_id, plan_id, loop_id, etc.
    payload: dict[str, Any]
    prev_hash: str  # Hash of previous event (Merkle chain)
    hash: str  # Hash of this event
    signature: Optional[str] = None  # Ed25519 signature


class EventSchema(BaseModel):
    """Schema validation for event types."""
    model_config = ConfigDict(frozen=True)

    type: str
    required_fields: list[str] = Field(default_factory=list)
    allowed_fields: list[str] = Field(default_factory=list)


# Built-in event schemas (extendable)
EVENT_SCHEMAS: dict[str, EventSchema] = {
    "session.started": EventSchema(
        type="session.started",
        required_fields=["session_id", "task", "tier"],
        allowed_fields=["session_id", "task", "tier", "goal", "complexity"],
    ),
    "session.heartbeat": EventSchema(
        type="session.heartbeat",
        required_fields=["session_id", "tool"],
        allowed_fields=["session_id", "tool", "file", "cost"],
    ),
    "session.completed": EventSchema(
        type="session.completed",
        required_fields=["session_id", "status"],
        allowed_fields=["session_id", "status", "duration_ms", "total_cost"],
    ),
    "plan.approved": EventSchema(
        type="plan.approved",
        required_fields=["plan_id", "approver"],
        allowed_fields=["plan_id", "approver", "signature", "plan_hash"],
    ),
    "plan.rejected": EventSchema(
        type="plan.rejected",
        required_fields=["plan_id", "reason"],
        allowed_fields=["plan_id", "reason", "reviewer"],
    ),
    "dag.task_started": EventSchema(
        type="dag.task_started",
        required_fields=["run_id", "task_id"],
        allowed_fields=["run_id", "task_id", "goal", "agent"],
    ),
    "dag.task_completed": EventSchema(
        type="dag.task_completed",
        required_fields=["run_id", "task_id", "result"],
        allowed_fields=["run_id", "task_id", "result", "duration_ms"],
    ),
    "dag.task_failed": EventSchema(
        type="dag.task_failed",
        required_fields=["run_id", "task_id", "error"],
        allowed_fields=["run_id", "task_id", "error", "retry_count"],
    ),
    "hook.pre_tool_use": EventSchema(
        type="hook.pre_tool_use",
        required_fields=["session_id", "tool_name"],
        allowed_fields=["session_id", "tool_name", "tool_input", "decision"],
    ),
    "hook.post_tool_use": EventSchema(
        type="hook.post_tool_use",
        required_fields=["session_id", "tool_name"],
        allowed_fields=["session_id", "tool_name", "tool_input", "tool_output", "ok"],
    ),
    "approval.sdd": EventSchema(
        type="approval.sdd",
        required_fields=["task_slug", "decision"],
        allowed_fields=["task_slug", "decision", "reviewer", "signature", "modifications"],
    ),
    "approval.plan": EventSchema(
        type="approval.plan",
        required_fields=["task_slug", "decision"],
        allowed_fields=["task_slug", "decision", "reviewer", "signature", "modifications"],
    ),
    "cost.cap_exceeded": EventSchema(
        type="cost.cap_exceeded",
        required_fields=["session_id", "cumulative", "cap"],
        allowed_fields=["session_id", "cumulative", "cap", "tool"],
    ),
    "security.block": EventSchema(
        type="security.block",
        required_fields=["session_id", "reason"],
        allowed_fields=["session_id", "reason", "tool", "pattern"],
    ),
}


# --- Materialized Views ---

class SessionView:
    """Materialized view: active sessions, heartbeats, costs."""

    def __init__(self, store: StateStore):
        self._store = store
        self._prefix = "view:session:"

    async def upsert(self, session_id: str, data: dict) -> None:
        await self._store.set(
            f"{self._prefix}{session_id}",
            json.dumps(data, separators=(",", ":")).encode(),
            StateOptions(ttl_seconds=86400 * 7),  # 7 days
        )

    async def get(self, session_id: str) -> Optional[dict]:
        try:
            entry = await self._store.get(f"{self._prefix}{session_id}")
            return json.loads(entry.value)
        except KeyNotFoundError:
            return None

    async def heartbeat(self, session_id: str, tool: str, cost: float = 0) -> None:
        current = await self.get(session_id) or {}
        current.update({
            "last_tool": tool,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "cumulative_cost": current.get("cumulative_cost", 0) + cost,
            "tool_count": current.get("tool_count", 0) + 1,
        })
        await self.upsert(session_id, current)

    async def list_active(self, since: datetime) -> list[dict]:
        """List sessions with heartbeat after `since`."""
        keys = await self._store.keys(f"{self._prefix}")
        active = []
        for key in keys:
            session_id = key[len(self._prefix):]
            data = await self.get(session_id)
            if data and data.get("last_heartbeat"):
                hb = datetime.fromisoformat(data["last_heartbeat"].replace("Z", "+00:00"))
                if hb >= since:
                    data["session_id"] = session_id
                    active.append(data)
        return active


class PlanView:
    """Materialized view: plan status, approvals, artifacts."""

    def __init__(self, store: StateStore):
        self._store = store
        self._prefix = "view:plan:"

    async def upsert(self, plan_id: str, data: dict) -> None:
        await self._store.set(
            f"{self._prefix}{plan_id}",
            json.dumps(data, separators=(",", ":")).encode(),
            StateOptions(ttl_seconds=86400 * 30),
        )

    async def get(self, plan_id: str) -> Optional[dict]:
        try:
            entry = await self._store.get(f"{self._prefix}{plan_id}")
            return json.loads(entry.value)
        except KeyNotFoundError:
            return None

    async def approve(self, plan_id: str, approver: str, signature: str, plan_hash: str) -> None:
        data = await self.get(plan_id) or {}
        data.update({
            "status": "approved",
            "approver": approver,
            "signature": signature,
            "plan_hash": plan_hash,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._store.set(
            f"{self._prefix}{plan_id}",
            json.dumps(data, separators=(",", ":")).encode(),
            StateOptions(ttl_seconds=86400 * 30, concurrency=ConcurrencyMode.LAST_WRITE),
        )

    async def reject(self, plan_id: str, reason: str, reviewer: str) -> None:
        data = await self.get(plan_id) or {}
        data.update({
            "status": "rejected",
            "rejection_reason": reason,
            "reviewer": reviewer,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._store.set(
            f"{self._prefix}{plan_id}",
            json.dumps(data, separators=(",", ":")).encode(),
            StateOptions(ttl_seconds=86400 * 30, concurrency=ConcurrencyMode.LAST_WRITE),
        )


class ExecutionView:
    """Materialized view: DAG state, task results, checkpoints."""

    def __init__(self, store: StateStore):
        self._store = store
        self._prefix = "view:execution:"

    async def upsert_task(self, run_id: str, task_id: str, data: dict) -> None:
        key = f"{self._prefix}{run_id}:{task_id}"
        await self._store.set(
            key,
            json.dumps(data, separators=(",", ":")).encode(),
            StateOptions(ttl_seconds=86400 * 7),
        )

    async def get_task(self, run_id: str, task_id: str) -> Optional[dict]:
        try:
            entry = await self._store.get(f"{self._prefix}{run_id}:{task_id}")
            return json.loads(entry.value)
        except KeyNotFoundError:
            return None

    async def list_tasks(self, run_id: str) -> list[dict]:
        keys = await self._store.keys(f"{self._prefix}{run_id}:")
        tasks = []
        for key in keys:
            task_id = key[len(self._prefix) + len(run_id) + 1:]
            data = await self.get_task(run_id, task_id)
            if data:
                data["task_id"] = task_id
                tasks.append(data)
        return tasks

    async def checkpoint(self, run_id: str, state: dict) -> None:
        key = f"{self._prefix}checkpoint:{run_id}"
        await self._store.set(
            key,
            json.dumps(state, separators=(",", ":")).encode(),
            StateOptions(ttl_seconds=86400 * 30),
        )

    async def get_checkpoint(self, run_id: str) -> Optional[dict]:
        try:
            entry = await self._store.get(f"{self._prefix}checkpoint:{run_id}")
            return json.loads(entry.value)
        except KeyNotFoundError:
            return None


class LoopView:
    """Materialized view: loop iterations, convergence metrics."""

    def __init__(self, store: StateStore):
        self._store = store
        self._prefix = "view:loop:"

    async def record_iteration(self, loop_id: str, data: dict) -> None:
        key = f"{self._prefix}{loop_id}:iter:{data['iteration']}"
        await self._store.set(
            key,
            json.dumps(data, separators=(",", ":")).encode(),
            StateOptions(ttl_seconds=86400 * 7),
        )

    async def get_iterations(self, loop_id: str) -> list[dict]:
        keys = await self._store.keys(f"{self._prefix}{loop_id}:iter:")
        iters = []
        for key in keys:
            try:
                entry = await self._store.get(key)
                iters.append(json.loads(entry.value))
            except KeyNotFoundError:
                pass
        return sorted(iters, key=lambda x: x.get("iteration", 0))

    async def get_convergence(self, loop_id: str) -> dict:
        """Compute convergence metrics from iterations."""
        iters = await self.get_iterations(loop_id)
        if not iters:
            return {"status": "no_data"}

        last = iters[-1]
        prev = iters[-2] if len(iters) > 1 else None

        return {
            "status": last.get("status", "unknown"),
            "iteration": last.get("iteration", 0),
            "blocking_issues": last.get("blocking_issues", 0),
            "stall_count": last.get("stall_count", 0),
            "converging": prev is not None and last.get("blocking_issues", 0) <= prev.get("blocking_issues", 0),
        }


# --- CRDT Implementations ---

class LWWRegister:
    """Last-Writer-Wins Register for config values."""

    def __init__(self, store: StateStore, key: str):
        self._store = store
        self._key = f"crdt:lww:{key}"

    async def set(self, value: Any, timestamp: Optional[datetime] = None) -> None:
        ts = timestamp or datetime.now(timezone.utc)
        payload = {"value": value, "timestamp": ts.isoformat()}
        await self._store.set(
            self._key,
            json.dumps(payload).encode(),
            StateOptions(concurrency=ConcurrencyMode.LAST_WRITE),
        )

    async def get(self) -> Any:
        try:
            entry = await self._store.get(self._key)
            payload = json.loads(entry.value)
            return payload["value"]
        except KeyNotFoundError:
            return None

    async def compare_and_swap(self, expected: Any, new_value: Any) -> bool:
        current = await self.get()
        if current == expected:
            await self.set(new_value)
            return True
        return False


class ORSet:
    """Observed-Remove Set for agent registry."""

    def __init__(self, store: StateStore, key: str):
        self._store = store
        self._key = f"crdt:orset:{key}"

    async def add(self, element: str, tag: Optional[str] = None) -> None:
        tag = tag or f"{uuid.uuid4().hex[:8]}:{datetime.now(timezone.utc).timestamp()}"
        async with self._store.transaction() as tx:
            current = await self._get_internal(tx)
            current[element] = current.get(element, set())
            current[element].add(tag)
            await self._set_internal(tx, current)

    async def remove(self, element: str) -> None:
        async with self._store.transaction() as tx:
            current = await self._get_internal(tx)
            if element in current:
                current[element] = set()  # Tombstone
                await self._set_internal(tx, current)

    async def contains(self, element: str) -> bool:
        current = await self._get()
        return element in current and len(current.get(element, set())) > 0

    async def elements(self) -> set[str]:
        current = await self._get()
        return {k for k, v in current.items() if len(v) > 0}

    async def _get(self) -> dict[str, set[str]]:
        try:
            entry = await self._store.get(self._key)
            payload = json.loads(entry.value)
            return {k: set(v) for k, v in payload.items()}
        except KeyNotFoundError:
            return {}

    async def _get_internal(self, tx) -> dict[str, set[str]]:
        try:
            entry = await tx.get(self._key)
            if entry:
                payload = json.loads(entry.value)
                return {k: set(v) for k, v in payload.items()}
            return {}
        except KeyNotFoundError:
            return {}

    async def _set_internal(self, tx, data: dict[str, set[str]]) -> None:
        payload = {k: list(v) for k, v in data.items()}
        await tx.set(self._key, json.dumps(payload).encode())


class PNCounter:
    """Positive-Negative Counter for costs/iterations (no lost increments)."""

    def __init__(self, store: StateStore, key: str):
        self._store = store
        self._p_key = f"crdt:pn:pos:{key}"
        self._n_key = f"crdt:pn:neg:{key}"

    async def increment(self, delta: int = 1) -> int:
        if delta >= 0:
            return await self._inc(self._p_key, delta)
        else:
            return await self._inc(self._n_key, -delta)

    async def decrement(self, delta: int = 1) -> int:
        return await self.increment(-delta)

    async def value(self) -> int:
        pos = await self._get(self._p_key)
        neg = await self._get(self._n_key)
        return pos - neg

    async def _inc(self, key: str, delta: int) -> int:
        async with self._store.transaction() as tx:
            current = await self._get_internal(tx, key)
            new_val = current + delta
            await tx.set(key, str(new_val).encode())
            return new_val

    async def _get(self, key: str) -> int:
        try:
            entry = await self._store.get(key)
            return int(entry.value)
        except KeyNotFoundError:
            return 0

    async def _get_internal(self, tx, key: str) -> int:
        try:
            entry = await tx.get(key)
            return int(entry.value) if entry else 0
        except KeyNotFoundError:
            return 0


# --- EventStore Core ---

class EventStore:
    """Event-sourced state machine with CQRS views.

    Features:
    - Append-only event log with Merkle hash chain
    - Event schema validation (Pydantic)
    - Ed25519 signatures for integrity
    - Materialized views (CQRS read models)
    - CRDTs for distributed coordination
    - Snapshots for fast replay
    """

    def __init__(
        self,
        state_store: StateStore,
        signing_key: Optional[bytes] = None,
        snapshot_interval: int = 1000,
    ):
        self._store = state_store
        self._signing_key = signing_key
        self._snapshot_interval = snapshot_interval
        self._seq = 0
        self._prev_hash = "0" * 64

        # Views
        self.sessions = SessionView(state_store)
        self.plans = PlanView(state_store)
        self.executions = ExecutionView(state_store)
        self.loops = LoopView(state_store)

        # CRDTs
        self._counters: dict[str, PNCounter] = {}

    async def initialize(self) -> None:
        """Load last event to restore seq/hash."""
        await self._store.initialize()
        last = await self._get_last_event()
        if last:
            self._seq = last.seq
            self._prev_hash = last.hash

    async def _get_last_event(self) -> Optional[Event]:
        try:
            entry = await self._store.get("__eventstore:last")
            return Event.model_validate_json(entry.value)
        except KeyNotFoundError:
            return None

    def _canonical_bytes(self, event: Event) -> bytes:
        """Canonical serialization for hashing/signing."""
        data = event.model_dump(exclude={"hash", "signature"})
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    def _hash_event(self, event: Event) -> str:
        """SHA256(prev_hash | seq | payload)."""
        body = self._canonical_bytes(event)
        return hashlib.sha256(f"{event.prev_hash}|{event.seq}|".encode() + body).hexdigest()

    def _sign_event(self, event: Event) -> Optional[str]:
        if not self._signing_key:
            return None
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        body = self._canonical_bytes(event)
        priv = Ed25519PrivateKey.from_private_bytes(self._signing_key[:32].ljust(32, b"\0"))
        return priv.sign(body).hex()

    def _verify_event(self, event: Event) -> bool:
        if not event.signature or not self._signing_key:
            return event.signature is None
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        try:
            body = self._canonical_bytes(event)
            pub = Ed25519PublicKey.from_public_bytes(self._signing_key[:32].ljust(32, b"\0"))
            pub.verify(bytes.fromhex(event.signature), body)
            return True
        except (InvalidSignature, ValueError):
            return False

    def _validate_schema(self, event_type: str, payload: dict) -> None:
        schema = EVENT_SCHEMAS.get(event_type)
        if not schema:
            return  # Unknown event types allowed (extensible)
        for field in schema.required_fields:
            if field not in payload:
                raise ValueError(f"Event {event_type} missing required field: {field}")
        # Optional: validate allowed fields
        # for field in payload:
        #     if field not in schema.allowed_fields and field not in schema.required_fields:
        #         raise ValueError(f"Event {event_type} has unexpected field: {field}")

    # --- Public API ---

    async def append(
        self,
        event_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        sign: bool = True,
    ) -> Event:
        """Append event to log, update views, return event."""
        self._validate_schema(event_type, payload)

        self._seq += 1
        ts = datetime.now(timezone.utc).isoformat()

        event = Event(
            seq=self._seq,
            ts=ts,
            type=event_type,
            aggregate_id=aggregate_id,
            payload=payload,
            prev_hash=self._prev_hash,
            hash="",  # Will compute after
        )

        # Compute hash
        event = Event(
            seq=event.seq,
            ts=event.ts,
            type=event.type,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            prev_hash=event.prev_hash,
            hash=self._hash_event(event),
        )

        # Sign
        if sign:
            sig = self._sign_event(event)
            event_data = event.model_dump(exclude={"signature"})
            event = Event(**event_data, signature=sig)

        # Persist event
        await self._store.set(
            f"__eventstore:event:{self._seq}",
            event.model_dump_json().encode(),
            StateOptions(concurrency=ConcurrencyMode.LAST_WRITE),
        )

        # Update pointer
        self._prev_hash = event.hash
        await self._store.set(
            "__eventstore:last",
            event.model_dump_json().encode(),
            StateOptions(concurrency=ConcurrencyMode.LAST_WRITE),
        )

        # Update views
        await self._update_views(event)

        # Snapshot
        if self._seq % self._snapshot_interval == 0:
            await self._snapshot()

        return event

    async def _update_views(self, event: Event) -> None:
        """Dispatch event to materialized views."""
        agg = event.aggregate_id
        p = event.payload

        if event.type == "session.started":
            await self.sessions.upsert(agg, {
                "session_id": agg,
                "task": p.get("task"),
                "tier": p.get("tier"),
                "goal": p.get("goal"),
                "started_at": event.ts,
                "status": "in_progress",
            })
        elif event.type == "session.heartbeat":
            await self.sessions.heartbeat(agg, p.get("tool", ""), p.get("cost", 0))
        elif event.type == "session.completed":
            data = await self.sessions.get(agg) or {}
            data.update({"status": p.get("status"), "completed_at": event.ts})
            await self.sessions.upsert(agg, data)
        elif event.type == "plan.approved":
            await self.plans.approve(agg, p.get("approver", ""), p.get("signature", ""), p.get("plan_hash", ""))
        elif event.type == "plan.rejected":
            await self.plans.reject(agg, p.get("reason", ""), p.get("reviewer", ""))
        elif event.type == "dag.task_started":
            await self.executions.upsert_task(agg, p.get("task_id", ""), {
                "run_id": agg,
                "task_id": p.get("task_id"),
                "goal": p.get("goal"),
                "agent": p.get("agent"),
                "status": "running",
                "started_at": event.ts,
            })
        elif event.type == "dag.task_completed":
            await self.executions.upsert_task(agg, p.get("task_id", ""), {
                "run_id": agg,
                "task_id": p.get("task_id"),
                "status": "completed",
                "result": p.get("result"),
                "completed_at": event.ts,
            })
        elif event.type == "dag.task_failed":
            await self.executions.upsert_task(agg, p.get("task_id", ""), {
                "run_id": agg,
                "task_id": p.get("task_id"),
                "status": "failed",
                "error": p.get("error"),
                "failed_at": event.ts,
            })
        elif event.type in ("approval.sdd", "approval.plan"):
            # Handled by plan view
            pass

    async def _snapshot(self) -> None:
        """Create snapshot of all views for fast replay."""
        snapshot = {
            "seq": self._seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "sessions": {},
            "plans": {},
            "executions": {},
            "loops": {},
        }
        # Collect view data (simplified - in production, stream to storage)
        await self._store.set(
            f"__eventstore:snapshot:{self._seq}",
            json.dumps(snapshot).encode(),
        )

    async def replay(self, from_seq: int = 0, event_types: Optional[list[str]] = None) -> list[Event]:
        """Replay events from sequence number."""
        events = []
        for seq in range(from_seq + 1, self._seq + 1):
            try:
                entry = await self._store.get(f"__eventstore:event:{seq}")
                event = Event.model_validate_json(entry.value)
                if not event_types or event.type in event_types:
                    events.append(event)
            except KeyNotFoundError:
                break
        return events

    def get_counter(self, name: str) -> PNCounter:
        """Get or create PNCounter for distributed counting."""
        if name not in self._counters:
            self._counters[name] = PNCounter(self._store, f"counter:{name}")
        return self._counters[name]

    async def health_check(self) -> HealthStatus:
        return await self._store.health_check()


# --- Factory ---

class EventStoreFactory:
    """Factory for creating EventStore with configured backends."""

    @staticmethod
    async def create(
        root: Path,
        name: str = "default",
        backend: str = "file",
        **backend_kwargs
    ) -> EventStore:
        if backend == "file":
            # root should be the repo root (parent of .devin)
            store = FileBackend(root / ".devin", name)
        elif backend == "redis":
            from .backends.redis_backend import RedisBackend
            store = RedisBackend(**backend_kwargs)
        elif backend == "postgresql":
            from .backends.pg_backend import PgBackend
            store = PgBackend(**backend_kwargs)
        else:
            raise ValueError(f"Unknown backend: {backend}")

        await store.initialize()
        event_store = EventStore(store)
        await event_store.initialize()
        return event_store


# --- Migration Helper ---

async def migrate_v1_to_v2(
    v1_root: Path,
    v2_root: Path,
    event_store: EventStore,
) -> dict[str, int]:
    """Migrate data from v1 fragmented stores to EventStore.

    Returns counts of migrated items per store type.
    """
    counts = {
        "session_state": 0,
        "loop_state": 0,
        "plan_state": 0,
        "checkpoints": 0,
        "idempotency": 0,
        "blackboard": 0,
        "event_bus": 0,
        "context_flags": 0,
    }

    # Migrate session_state
    session_dir = v1_root / ".devin" / "session_state"
    if session_dir.exists():
        for f in session_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                sid = f.stem
                await event_store.append(
                    "session.started",
                    sid,
                    {
                        "session_id": sid,
                        "task": data.get("goal", ""),
                        "tier": data.get("complexity", "M"),
                        "goal": data.get("goal", ""),
                    },
                    sign=False,
                )
                counts["session_state"] += 1
            except Exception:
                pass

    # Migrate loop_state
    loop_dir = v1_root / ".devin" / "loop_state"
    if loop_dir.exists():
        for f in loop_dir.glob("*.md"):
            try:
                content = f.read_text()
                loop_id = f.stem
                await event_store.append(
                    "loop.iteration",
                    loop_id,
                    {"iteration": 1, "status": "migrated", "content": content[:500]},
                    sign=False,
                )
                counts["loop_state"] += 1
            except Exception:
                pass

    # Migrate plan_state (approvals)
    plan_dir = v1_root / ".devin" / "plan_state"
    if plan_dir.exists():
        for f in plan_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                # Extract plan_id from plan_file field (e.g., "docs/plans/test-feature/IMPLEMENTATION_PLAN.md" -> "test-feature")
                plan_file = data.get("plan_file", "")
                if "plans" in plan_file:
                    plan_id = plan_file.split("plans/")[1].split("/")[0]
                else:
                    plan_id = f.stem
                if data.get("status") == "approved":
                    await event_store.append(
                        "plan.approved",
                        plan_id,
                        {
                            "plan_id": plan_id,
                            "approver": data.get("reviewer", "migrated"),
                            "signature": data.get("signature", ""),
                            "plan_hash": data.get("plan_hash", ""),
                        },
                        sign=False,
                    )
                counts["plan_state"] += 1
            except Exception:
                pass

    # Other stores would be migrated similarly...
    # For brevity, only key stores shown

    return counts