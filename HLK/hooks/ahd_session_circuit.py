#!/usr/bin/env python3
"""Circuit breaker utilities for ahd_session (U67 antifragility).

Provides:
- record_failure: Record a component failure, trips circuit breaker on 3 failures
- is_circuit_open: Check if circuit breaker is tripped for a component
- reset_circuit: Reset circuit breaker for a component (manual override)
- get_failure_stats: Get current failure counts for all components
- auto_minimal_mode: Auto-activate minimal mode if critical components fail
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from ahd_session_id import get_repo_root
from ahd_session_paths import get_session_state_path
from ahd_session_state import _locked_json_update


# In-memory failure counters per component
_FAILURE_COUNTERS: dict[str, int] = {}
_CIRCUIT_BREAKER_THRESHOLD = 3
_TRIPPED_BREAKERS: set[str] = set()
_CIRCUIT_LOCK = threading.RLock()


def record_failure(component: str, session_id: str = "") -> None:
    """Record a component failure. Trips circuit breaker on 3 failures."""
    with _CIRCUIT_LOCK:
        _FAILURE_COUNTERS[component] = _FAILURE_COUNTERS.get(component, 0) + 1
        if _FAILURE_COUNTERS[component] >= _CIRCUIT_BREAKER_THRESHOLD:
            _TRIPPED_BREAKERS.add(component)
        tripped = list(_TRIPPED_BREAKERS)
        counts = dict(_FAILURE_COUNTERS)

    # Also persist to session_state for cross-session visibility
    try:
        root = get_repo_root()
        state_path = get_session_state_path(session_id, root)
        _locked_json_update(
            state_path,
            lambda existing: {
                **(existing or {}),
                "circuit_breakers_tripped": tripped,
                "failure_counts": counts,
            },
            default={},
            session_id=session_id,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        pass


def is_circuit_open(component: str) -> bool:
    """Check if circuit breaker is tripped for a component."""
    with _CIRCUIT_LOCK:
        return component in _TRIPPED_BREAKERS


def reset_circuit(component: str) -> None:
    """Reset circuit breaker for a component (manual override)."""
    with _CIRCUIT_LOCK:
        _TRIPPED_BREAKERS.discard(component)
        _FAILURE_COUNTERS.pop(component, None)


def get_failure_stats() -> dict[str, int]:
    """Get current failure counts for all components."""
    with _CIRCUIT_LOCK:
        return dict(_FAILURE_COUNTERS)


def auto_minimal_mode(session_id: str, root: Optional[Path] = None) -> bool:
    """Auto-activate minimal mode if critical components fail.

    Returns True if minimal mode should be activated.
    """
    critical_components = ["ahd_session", "pre_tool_use", "post_tool_use"]
    failed_critical = [c for c in critical_components if is_circuit_open(c)]
    if failed_critical:
        try:
            state_path = get_session_state_path(session_id, root)
            _locked_json_update(
                state_path,
                lambda existing: {
                    **(existing or {}),
                    "minimal_mode_auto": True,
                    "minimal_mode_reason": f"Circuit breakers tripped: {failed_critical}",
                },
                default={},
                session_id=session_id,
            )
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return True
    return False