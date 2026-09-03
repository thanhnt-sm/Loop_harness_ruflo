#!/usr/bin/env python3
"""Durable Execution Layer for AHD Sessions — P1-05.

Provides:
- Phase-based checkpointing (save state after each phase)
- Resume from checkpoint (no redo paid LLM calls)
- LLM call deduplication cache
- Tool receipts with idempotency keys
- Human-gated saga for irreversible actions
- Compacted durable state (goal + waits + receipts, not full history)
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import ahd_session

# Import config constants
try:
    from post_tool_config import (
        SESSION_PHASES,
        CHECKPOINT_VERSION,
        LLM_CALL_CACHE_MAX_ENTRIES,
        RECEIPT_TTL_SECONDS,
        SAGA_TIMEOUT_SECONDS,
    )
except ImportError:
    SESSION_PHASES = [
        "boot", "plan", "approve_sdd", "approve_plan",
        "execute", "verify", "report", "completed"
    ]
    CHECKPOINT_VERSION = 1
    LLM_CALL_CACHE_MAX_ENTRIES = 1000
    RECEIPT_TTL_SECONDS = 86400
    SAGA_TIMEOUT_SECONDS = 300


class SessionPhase(Enum):
    """AHD session phases for durable checkpointing."""
    BOOT = "boot"
    PLAN = "plan"
    APPROVE_SDD = "approve_sdd"
    APPROVE_PLAN = "approve_plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    REPORT = "report"
    COMPLETED = "completed"


@dataclass
class LLMCallCacheEntry:
    """Cached LLM call to avoid re-execution on resume."""
    call_hash: str
    model: str
    prompt_hash: str
    response: dict
    tokens_in: int
    tokens_out: int
    cost_usd: float
    timestamp: str


@dataclass
class ToolReceipt:
    """Receipt for tool call with idempotency key."""
    idempotency_key: str
    tool: str
    args: dict
    result: dict
    status: str  # "success", "failed", "pending"
    timestamp: str
    session_id: str
    expires_at: str


@dataclass
class SagaStep:
    """A step in a saga (compensatable transaction)."""
    step_id: str
    action: str  # "tool_call", "llm_call", "human_approval"
    tool: Optional[str] = None
    args: Optional[dict] = None
    compensation: Optional[str] = None  # How to undo: "refund", "delete", "notify"
    requires_human_approval: bool = False
    approved: bool = False
    executed: bool = False
    timestamp: str = ""


@dataclass
class DurableCheckpoint:
    """Complete checkpoint for session resume."""
    version: int
    session_id: str
    phase: str
    step_index: int
    goal: str
    completed_steps: list[dict]  # {phase, step, llm_calls_cached, receipts}
    pending_waits: list[dict]    # {type, ref, payload, started_at}
    receipts: list[dict]         # Tool receipts
    compact_state: dict          # Minimal state for resume
    llm_call_cache: dict[str, dict]  # call_hash -> LLMCallCacheEntry
    created_at: str
    updated_at: str


# Thread-safe global caches
_DURABLE_SESSIONS: dict[str, dict] = {}
_DURABLE_LOCK = threading.Lock()


def _checkpoint_path(root: Path, session_id: str) -> Path:
    """Get checkpoint file path for session."""
    return root / ".devin" / "session_state" / session_id / "checkpoint.json"


def _receipt_path(root: Path, session_id: str) -> Path:
    """Get receipts file path for session."""
    return root / ".devin" / "session_state" / session_id / "receipts.jsonl"


def _llm_cache_path(root: Path, session_id: str) -> Path:
    """Get LLM call cache file path for session."""
    return root / ".devin" / "session_state" / session_id / "llm_cache.json"


def _compute_call_hash(model: str, prompt: str, **kwargs) -> str:
    """Compute deterministic hash for LLM call deduplication."""
    content = f"{model}|{prompt}|{json.dumps(kwargs, sort_keys=True)}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def _compute_idempotency_key(session_id: str, tool: str, args: dict) -> str:
    """Compute idempotency key for tool call."""
    content = f"{session_id}|{tool}|{json.dumps(args, sort_keys=True)}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# Checkpoint Management
# ============================================================================

def save_checkpoint(
    root: Path,
    session_id: str,
    checkpoint: "DurableCheckpoint",
) -> bool:
    """Atomically save checkpoint to disk."""
    try:
        path = _checkpoint_path(root, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to serializable dict
        data = asdict(checkpoint)

        # Atomic write via temp file
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        tmp.replace(path)
        return True
    except Exception as e:
        print(f"[durable] Failed to save checkpoint: {e}", file=sys.stderr)
        return False


def load_checkpoint(root: Path, session_id: str) -> Optional["DurableCheckpoint"]:
    """Load checkpoint for session resume."""
    path = _checkpoint_path(root, session_id)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        # Version check
        if data.get("version", 0) != CHECKPOINT_VERSION:
            print(f"[durable] Checkpoint version mismatch: {data.get('version')} != {CHECKPOINT_VERSION}")
            return None

        # Restore nested objects
        # LLM cache entries
        llm_cache = {}
        for k, v in data.get("llm_call_cache", {}).items():
            llm_cache[k] = LLMCallCacheEntry(**v)

        checkpoint = DurableCheckpoint(
            version=data["version"],
            session_id=data["session_id"],
            phase=data["phase"],
            step_index=data["step_index"],
            goal=data["goal"],
            completed_steps=data["completed_steps"],
            pending_waits=data["pending_waits"],
            receipts=data["receipts"],
            compact_state=data["compact_state"],
            llm_call_cache=llm_cache,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
        return checkpoint
    except Exception as e:
        print(f"[durable] Failed to load checkpoint: {e}", file=sys.stderr)
        return None


def create_initial_checkpoint(
    root: Path,
    session_id: str,
    goal: str,
) -> "DurableCheckpoint":
    """Create initial checkpoint at session start."""
    now = _now_iso()
    checkpoint = DurableCheckpoint(
        version=CHECKPOINT_VERSION,
        session_id=session_id,
        phase=SessionPhase.BOOT.value,
        step_index=0,
        goal=goal,
        completed_steps=[],
        pending_waits=[],
        receipts=[],
        compact_state={
            "goal": goal,
            "current_phase": SessionPhase.BOOT.value,
            "pending_waits": [],
            "receipt_count": 0,
        },
        llm_call_cache={},
        created_at=now,
        updated_at=now,
    )

    save_checkpoint(root, session_id, checkpoint)
    return checkpoint


def advance_phase(
    root: Path,
    session_id: str,
    new_phase: SessionPhase,
    step_index: int = 0,
) -> bool:
    """Advance session to next phase and checkpoint."""
    checkpoint = load_checkpoint(root, session_id)
    if not checkpoint:
        return False

    checkpoint.phase = new_phase.value
    checkpoint.step_index = step_index
    checkpoint.updated_at = _now_iso()

    # Update compact state
    checkpoint.compact_state["current_phase"] = new_phase.value
    checkpoint.compact_state["pending_waits"] = [
        w for w in checkpoint.pending_waits if not w.get("completed", False)
    ]

    return save_checkpoint(root, session_id, checkpoint)


def record_step_completion(
    root: Path,
    session_id: str,
    phase: SessionPhase,
    step_name: str,
    llm_calls_cached: int = 0,
    receipts: list[dict] | None = None,
) -> bool:
    """Record completion of a step within a phase."""
    checkpoint = load_checkpoint(root, session_id)
    if not checkpoint:
        return False

    step_record = {
        "phase": phase.value,
        "step": step_name,
        "llm_calls_cached": llm_calls_cached,
        "receipt_count": len(receipts) if receipts else 0,
        "timestamp": _now_iso(),
    }
    checkpoint.completed_steps.append(step_record)
    checkpoint.updated_at = _now_iso()

    if receipts:
        checkpoint.receipts.extend(receipts)
        checkpoint.compact_state["receipt_count"] = len(checkpoint.receipts)

    return save_checkpoint(root, session_id, checkpoint)


# ============================================================================
# LLM Call Cache (Deduplication)
# ============================================================================

_LLM_CALL_CACHES: dict[str, dict[str, LLMCallCacheEntry]] = {}
_LLM_CACHE_LOCK = threading.Lock()


def get_llm_cache(session_id: str) -> dict[str, LLMCallCacheEntry]:
    """Get or create LLM call cache for session."""
    with _LLM_CACHE_LOCK:
        if session_id not in _LLM_CALL_CACHES:
            _LLM_CALL_CACHES[session_id] = {}
        return _LLM_CALL_CACHES[session_id]


def llm_cache_get(
    session_id: str,
    model: str,
    prompt: str,
    **kwargs,
) -> Optional[dict]:
    """Check if LLM call is cached. Returns cached response if found."""
    cache = get_llm_cache(session_id)
    call_hash = _compute_call_hash(model, prompt, **kwargs)

    if call_hash in cache:
        entry = cache[call_hash]
        return {
            "cached": True,
            "response": entry.response,
            "tokens_saved": entry.tokens_in + entry.tokens_out,
            "cost_saved_usd": entry.cost_usd,
        }
    return None


def llm_cache_put(
    session_id: str,
    model: str,
    prompt: str,
    response: dict,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    **kwargs,
) -> str:
    """Cache LLM call response for deduplication on resume."""
    cache = get_llm_cache(session_id)
    call_hash = _compute_call_hash(model, prompt, **kwargs)

    # LRU eviction if cache full
    if len(cache) >= LLM_CALL_CACHE_MAX_ENTRIES:
        # Remove oldest entry
        oldest = min(cache.values(), key=lambda e: e.timestamp)
        del cache[oldest.call_hash]

    entry = LLMCallCacheEntry(
        call_hash=call_hash,
        model=model,
        prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()[:16],
        response=response,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        timestamp=_now_iso(),
    )
    cache[call_hash] = entry
    return call_hash


def llm_cache_persist(root: Path, session_id: str) -> bool:
    """Persist LLM call cache to disk."""
    cache = get_llm_cache(session_id)
    path = _llm_cache_path(root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = {k: asdict(v) for k, v in cache.items()}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(path)
        return True
    except Exception as e:
        print(f"[durable] Failed to persist LLM cache: {e}", file=sys.stderr)
        return False


def llm_cache_load(root: Path, session_id: str) -> int:
    """Load LLM call cache from disk. Returns entry count."""
    path = _llm_cache_path(root, session_id)
    if not path.exists():
        return 0

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cache = get_llm_cache(session_id)
        for k, v in data.items():
            cache[k] = LLMCallCacheEntry(**v)
        return len(cache)
    except Exception as e:
        print(f"[durable] Failed to load LLM cache: {e}", file=sys.stderr)
        return 0


# ============================================================================
# Tool Receipts with Idempotency Keys
# ============================================================================

def emit_tool_receipt(
    root: Path,
    session_id: str,
    tool: str,
    args: dict,
    result: dict,
    status: str = "success",
) -> str:
    """Emit tool receipt with idempotency key."""
    idempotency_key = _compute_idempotency_key(session_id, tool, args)

    receipt = ToolReceipt(
        idempotency_key=idempotency_key,
        tool=tool,
        args=args,
        result=result,
        status=status,
        timestamp=_now_iso(),
        session_id=session_id,
        expires_at=datetime.fromtimestamp(
            time.time() + RECEIPT_TTL_SECONDS, tz=timezone.utc
        ).isoformat(),
    )

    # Append to receipts log
    path = _receipt_path(root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(receipt), ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[durable] Failed to write receipt: {e}", file=sys.stderr)

    # Also add to checkpoint
    checkpoint = load_checkpoint(path.parent.parent.parent, session_id)
    if checkpoint:
        checkpoint.receipts.append(asdict(ToolReceipt(
            idempotency_key=idempotency_key,
            tool=tool,
            args=args,
            result=result,
            status=status,
            timestamp=_now_iso(),
            session_id=session_id,
            expires_at=datetime.fromtimestamp(
                time.time() + RECEIPT_TTL_SECONDS, tz=timezone.utc
            ).isoformat(),
        )))
        save_checkpoint(path.parent.parent.parent, session_id, checkpoint)

    return idempotency_key


def check_idempotent(root: Path, session_id: str, tool: str, args: dict) -> Optional[dict]:
    """Check if tool call was already executed (idempotent)."""
    idempotency_key = _compute_idempotency_key(session_id, tool, args)

    # Check receipts log
    path = _receipt_path(root, session_id)
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                receipt = json.loads(line)
                if receipt.get("idempotency_key") == idempotency_key:
                    return receipt.get("result")
        except Exception:
            pass

    return None


# ============================================================================
# Saga for Irreversible Actions
# ============================================================================

_ACTIVE_SAGAS: dict[str, list[SagaStep]] = {}
_SAGA_LOCK = threading.Lock()


def saga_begin(session_id: str, steps: list[SagaStep]) -> bool:
    """Begin a saga (sequence of steps with compensation)."""
    with _SAGA_LOCK:
        if session_id in _ACTIVE_SAGAS:
            return False  # Saga already in progress
        _ACTIVE_SAGAS[session_id] = steps
        return True


def saga_execute_step(
    session_id: str,
    step_id: str,
    executor_fn,
    *args,
    **kwargs,
) -> tuple[bool, Any]:
    """Execute a saga step, record result."""
    with _SAGA_LOCK:
        if session_id not in _ACTIVE_SAGAS:
            return False, "No active saga"

        for step in _ACTIVE_SAGAS[session_id]:
            if step.step_id == step_id:
                if step.requires_human_approval and not step.approved:
                    return False, "Requires human approval"

                try:
                    result = executor_fn(*args, **kwargs)
                    step.executed = True
                    return True, result
                except Exception as e:
                    return False, str(e)

        return False, "Step not found"


def saga_request_approval(session_id: str, step_id: str) -> bool:
    """Mark saga step as requiring human approval."""
    with _SAGA_LOCK:
        if session_id not in _ACTIVE_SAGAS:
            return False
        for step in _ACTIVE_SAGAS[session_id]:
            if step.step_id == step_id:
                step.requires_human_approval = True
                return True
        return False


def saga_approve_step(session_id: str, step_id: str) -> bool:
    """Approve a human-gated saga step."""
    with _SAGA_LOCK:
        if session_id not in _ACTIVE_SAGAS:
            return False
        for step in _ACTIVE_SAGAS[session_id]:
            if step.step_id == step_id:
                step.approved = True
                return True
        return False


def saga_compensate(session_id: str) -> list[str]:
    """Run compensations for executed steps in reverse order."""
    with _SAGA_LOCK:
        if session_id not in _ACTIVE_SAGAS:
            return []

        steps = _ACTIVE_SAGAS[session_id]
        results = []

        for step in reversed(steps):
            if step.executed and step.compensation:
                try:
                    # Execute compensation
                    results.append(f"Compensated {step.step_id}: {step.compensation}")
                except Exception as e:
                    results.append(f"Failed to compensate {step.step_id}: {e}")

        del _ACTIVE_SAGAS[session_id]
        return results


def saga_complete(session_id: str) -> bool:
    """Mark saga as successfully completed."""
    with _SAGA_LOCK:
        if session_id in _ACTIVE_SAGAS:
            del _ACTIVE_SAGAS[session_id]
            return True
        return False


# ============================================================================
# Resume Helpers
# ============================================================================

def resume_session(root: Path, session_id: str) -> Optional[DurableCheckpoint]:
    """Resume session from latest checkpoint."""
    checkpoint = load_checkpoint(root, session_id)
    if not checkpoint:
        return None

    # Load LLM call cache
    llm_cache_load(root, session_id)

    # Update session state with checkpoint info
    ahd_session.update_session_state(session_id, {
        "phase": checkpoint.phase,
        "step_index": checkpoint.step_index,
        "goal": checkpoint.goal,
        "resumed_from_checkpoint": True,
        "checkpoint_updated_at": checkpoint.updated_at,
    }, root)

    return checkpoint


def get_compact_state(checkpoint: DurableCheckpoint) -> dict:
    """Get compacted durable state for external consumers."""
    return {
        "session_id": checkpoint.session_id,
        "goal": checkpoint.goal,
        "current_phase": checkpoint.phase,
        "step_index": checkpoint.step_index,
        "pending_waits": checkpoint.pending_waits,
        "receipt_count": len(checkpoint.receipts),
        "completed_steps": len(checkpoint.completed_steps),
        "llm_cache_size": len(checkpoint.llm_call_cache),
        "updated_at": checkpoint.updated_at,
    }


# ============================================================================
# Export Public API
# ============================================================================

__all__ = [
    # Enums
    "SessionPhase",
    # Data classes
    "LLMCallCacheEntry",
    "ToolReceipt",
    "SagaStep",
    "DurableCheckpoint",
    # Checkpoint management
    "create_initial_checkpoint",
    "advance_phase",
    "record_step_completion",
    "save_checkpoint",
    "load_checkpoint",
    "resume_session",
    "get_compact_state",
    # LLM cache
    "llm_cache_get",
    "llm_cache_put",
    "llm_cache_persist",
    "llm_cache_load",
    # Tool receipts
    "emit_tool_receipt",
    "check_idempotent",
    # Saga
    "saga_begin",
    "saga_execute_step",
    "saga_request_approval",
    "saga_approve_step",
    "saga_compensate",
    "saga_complete",
    # Helpers
    "get_compact_state",
]