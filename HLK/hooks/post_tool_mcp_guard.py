"""MCP Guard — Structured Error Response Format (SERF) + Circuit Breaker.

Wraps MCP tool calls to enforce:
  1. Structured response: {ok, error, detail, completeness}
  2. Client-side circuit breaker (trip on N consecutive failures)
  3. No silent null responses

Integration: called from post_tool_engine for tool_name starting with 'mcp__'.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from pathlib import Path


# Config constants — nguồn duy nhất là post_tool_config (tránh drift)
try:
    from post_tool_config import (
        MCP_CIRCUIT_BREAKER_THRESHOLD,
        MCP_CIRCUIT_BREAKER_COOLDOWN,
        MCP_DEFAULT_COMPLETENESS,
    )
except ImportError:
    # Fallback khi chạy standalone (pytest)
    MCP_CIRCUIT_BREAKER_THRESHOLD = 3
    MCP_CIRCUIT_BREAKER_COOLDOWN = 60  # seconds
    MCP_DEFAULT_COMPLETENESS = 1.0


@dataclass
class CircuitBreakerState:
    """Thread-safe circuit breaker state per MCP server."""
    failures: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed, open, half-open
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.state = "closed"

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= MCP_CIRCUIT_BREAKER_THRESHOLD:
                self.state = "open"

    def can_execute(self) -> bool:
        with self._lock:
            if self.state == "closed":
                return True
            if self.state == "open":
                if time.time() - self.last_failure_time >= MCP_CIRCUIT_BREAKER_COOLDOWN:
                    self.state = "half-open"
                    return True
                return False
            # half-open
            return True


# Global circuit breakers per MCP server
_MCP_CIRCUIT_BREAKERS: dict[str, CircuitBreakerState] = {}
_CB_LOCK = threading.Lock()


def _get_breaker(server_name: str) -> CircuitBreakerState:
    """Get or create circuit breaker for MCP server."""
    with _CB_LOCK:
        if server_name not in _MCP_CIRCUIT_BREAKERS:
            _MCP_CIRCUIT_BREAKERS[server_name] = CircuitBreakerState()
        return _MCP_CIRCUIT_BREAKERS[server_name]


def enforce_structured_response(
    server_name: str,
    tool_name: str,
    raw_response: Any,
) -> dict:
    """Convert any MCP response to SERF format: {ok, error, detail, completeness}."""
    # If already structured, validate and return
    if isinstance(raw_response, dict) and "ok" in raw_response:
        result = {
            "ok": bool(raw_response.get("ok", False)),
            "error": raw_response.get("error"),
            "detail": raw_response.get("detail"),
            "completeness": float(raw_response.get("completeness", MCP_DEFAULT_COMPLETENESS)),
        }
        # Clamp completeness to [0.0, 1.0]
        result["completeness"] = max(0.0, min(1.0, result["completeness"]))
        return result

    # Null response → structured error (critical: prevents silent success interpretation)
    if raw_response is None:
        return {
            "ok": False,
            "error": "null_response",
            "detail": f"MCP server '{server_name}' tool '{tool_name}' returned null",
            "completeness": 0.0,
        }

    # Primitive/other → wrap as success with detail
    return {
        "ok": True,
        "error": None,
        "detail": raw_response,
        "completeness": MCP_DEFAULT_COMPLETENESS,
    }


def mcp_guard_call(
    server_name: str,
    tool_name: str,
    call_fn: Callable[[], Any],
) -> dict:
    """Execute MCP tool call with circuit breaker and SERF enforcement."""
    breaker = _get_breaker(server_name)

    # Check circuit breaker
    if not breaker.can_execute():
        return {
            "ok": False,
            "error": "circuit_breaker_open",
            "detail": f"Circuit breaker OPEN for MCP server '{server_name}' (failures: {breaker.failures})",
            "completeness": 0.0,
        }

    try:
        raw = call_fn()
        structured = enforce_structured_response(server_name, tool_name, raw)

        if structured["ok"]:
            breaker.record_success()
        else:
            breaker.record_failure()

        return structured

    except Exception as e:
        breaker.record_failure()
        return {
            "ok": False,
            "error": "exception",
            "detail": f"MCP call failed: {type(e).__name__}: {e}",
            "completeness": 0.0,
        }


def get_circuit_breaker_status(server_name: str) -> dict:
    """Get current circuit breaker status for monitoring/debugging."""
    breaker = _get_breaker(server_name)
    with breaker._lock:
        return {
            "server": server_name,
            "state": breaker.state,
            "failures": breaker.failures,
            "last_failure": breaker.last_failure_time,
        }


def reset_circuit_breaker(server_name: str) -> None:
    """Manually reset circuit breaker (for testing/admin)."""
    with _CB_LOCK:
        if server_name in _MCP_CIRCUIT_BREAKERS:
            _MCP_CIRCUIT_BREAKERS[server_name] = CircuitBreakerState()


# Export public API
__all__ = [
    "MCP_CIRCUIT_BREAKER_THRESHOLD",
    "MCP_CIRCUIT_BREAKER_COOLDOWN",
    "MCP_DEFAULT_COMPLETENESS",
    "CircuitBreakerState",
    "enforce_structured_response",
    "mcp_guard_call",
    "get_circuit_breaker_status",
    "reset_circuit_breaker",
]