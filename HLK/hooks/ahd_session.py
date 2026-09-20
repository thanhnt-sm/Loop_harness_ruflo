#!/usr/bin/env python3
"""Shared session helpers for Agent Harness Deploy runtime hooks and scripts.

Entry point re-exporting all public APIs from submodules.

Provides:
- session_id resolution with fallback chain
- filesystem-safe slugification
- repo root discovery
- locked read/write of session_state JSON
- locked file read/write utilities
- circuit breaker antifragility (U67)
"""
from __future__ import annotations

# Lock utilities
from ahd_session_lock import LockAcquireError, _acquire_lock, _release_lock, _safe_mkdir

# Path utilities
from ahd_session_paths import (
    _get_lock_path,
    _get_session_lock_path,
    get_config_root,
    get_context_flags_path,
    get_loop_state_path,
    get_session_state_path,
    get_shared_state_root,
    resolve_shared_state_file,
)

# Session ID utilities
from ahd_session_id import get_repo_root, get_session_id, slugify_session_id

# State utilities
from ahd_session_state import (
    _check_memory_cap,
    _locked_json_read,
    _locked_json_update,
    _locked_json_write,
    _locked_text_write,
    append_jsonl,
    read_context_flags,
    read_session_state,
    update_session_state,
    write_context_flags,
    write_session_state,
)

# Circuit breaker utilities
from ahd_session_circuit import (
    auto_minimal_mode,
    get_failure_stats,
    is_circuit_open,
    record_failure,
    reset_circuit,
)

# Utility functions
from ahd_session_utils import now_utc

# Durable execution layer (P1-05)
try:
    from ahd_session_durable import (
        SessionPhase,
        DurableCheckpoint,
        LLMCallCacheEntry,
        ToolReceipt,
        SagaStep,
        create_initial_checkpoint,
        advance_phase,
        record_step_completion,
        save_checkpoint,
        load_checkpoint,
        resume_session,
        get_compact_state,
        llm_cache_get,
        llm_cache_put,
        llm_cache_persist,
        llm_cache_load,
        emit_tool_receipt,
        check_idempotent,
        saga_begin,
        saga_execute_step,
        saga_request_approval,
        saga_approve_step,
        saga_compensate,
        saga_complete,
    )
except ImportError:
    pass

# Back-compat: expose internal functions that may be imported by other hooks
__all__ = [
    # Lock
    "LockAcquireError",
    "_safe_mkdir",
    "_acquire_lock",
    "_release_lock",
    # Paths
    "get_config_root",
    "get_shared_state_root",
    "resolve_shared_state_file",
    "get_session_state_path",
    "get_context_flags_path",
    "get_loop_state_path",
    "_get_lock_path",
    "_get_session_lock_path",
    # Session ID
    "get_repo_root",
    "slugify_session_id",
    "get_session_id",
    # State
    "_locked_json_read",
    "_locked_json_write",
    "_locked_json_update",
    "_locked_text_write",
    "read_session_state",
    "write_session_state",
    "update_session_state",
    "write_context_flags",
    "read_context_flags",
    "append_jsonl",
    "_check_memory_cap",
    # Circuit
    "record_failure",
    "is_circuit_open",
    "reset_circuit",
    "get_failure_stats",
    "auto_minimal_mode",
    # Durable execution (P1-05)
    "SessionPhase",
    "DurableCheckpoint",
    "LLMCallCacheEntry",
    "ToolReceipt",
    "SagaStep",
    "create_initial_checkpoint",
    "advance_phase",
    "record_step_completion",
    "save_checkpoint",
    "load_checkpoint",
    "resume_session",
    "get_compact_state",
    "llm_cache_get",
    "llm_cache_put",
    "llm_cache_persist",
    "llm_cache_load",
    "emit_tool_receipt",
    "check_idempotent",
    "saga_begin",
    "saga_execute_step",
    "saga_request_approval",
    "saga_approve_step",
    "saga_compensate",
    "saga_complete",
    "get_compact_state",
    # Utils
    "now_utc",
]