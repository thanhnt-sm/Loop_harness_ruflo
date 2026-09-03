"""Tests for post_tool_mcp_guard — SERF enforcement + circuit breaker."""

from __future__ import annotations

import time
import pytest

from post_tool_mcp_guard import (
    MCP_CIRCUIT_BREAKER_THRESHOLD,
    MCP_CIRCUIT_BREAKER_COOLDOWN,
    MCP_DEFAULT_COMPLETENESS,
    CircuitBreakerState,
    enforce_structured_response,
    mcp_guard_call,
    get_circuit_breaker_status,
    reset_circuit_breaker,
)


class TestCircuitBreakerState:
    """Test CircuitBreakerState core logic."""

    def test_initial_state_closed(self):
        cb = CircuitBreakerState()
        assert cb.state == "closed"
        assert cb.failures == 0
        assert cb.can_execute() is True

    def test_record_success_resets_failures(self):
        cb = CircuitBreakerState()
        cb.failures = 2
        cb.state = "open"
        cb.record_success()
        assert cb.failures == 0
        assert cb.state == "closed"

    def test_record_failure_increments(self):
        cb = CircuitBreakerState()
        cb.record_failure()
        assert cb.failures == 1
        assert cb.state == "closed"

    def test_trips_after_threshold(self):
        cb = CircuitBreakerState()
        for _ in range(MCP_CIRCUIT_BREAKER_THRESHOLD):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_half_open_after_cooldown(self):
        cb = CircuitBreakerState()
        # Trip it
        for _ in range(MCP_CIRCUIT_BREAKER_THRESHOLD):
            cb.record_failure()
        assert cb.state == "open"
        # Manually set last_failure_time to past
        cb.last_failure_time = time.time() - MCP_CIRCUIT_BREAKER_COOLDOWN - 1
        assert cb.can_execute() is True  # Should transition to half-open
        assert cb.state == "half-open"

    def test_half_open_success_closes(self):
        cb = CircuitBreakerState()
        for _ in range(MCP_CIRCUIT_BREAKER_THRESHOLD):
            cb.record_failure()
        cb.last_failure_time = time.time() - MCP_CIRCUIT_BREAKER_COOLDOWN - 1
        cb.can_execute()  # Transitions to half-open
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failures == 0


class TestEnforceStructuredResponse:
    """Test SERF format enforcement."""

    def test_already_structured_ok(self):
        raw = {"ok": True, "error": None, "detail": "data", "completeness": 0.9}
        result = enforce_structured_response("server", "tool", raw)
        assert result["ok"] is True
        assert result["error"] is None
        assert result["detail"] == "data"
        assert result["completeness"] == 0.9

    def test_already_structured_error(self):
        raw = {"ok": False, "error": "timeout", "detail": "upstream timeout", "completeness": 0.3}
        result = enforce_structured_response("server", "tool", raw)
        assert result["ok"] is False
        assert result["error"] == "timeout"
        assert result["completeness"] == 0.3

    def test_null_response_becomes_error(self):
        raw = None
        result = enforce_structured_response("aide-memory", "aide_recall", raw)
        assert result["ok"] is False
        assert result["error"] == "null_response"
        assert "null" in result["detail"]
        assert result["completeness"] == 0.0

    def test_primitive_wrapped_as_success(self):
        raw = "some string result"
        result = enforce_structured_response("server", "tool", raw)
        assert result["ok"] is True
        assert result["error"] is None
        assert result["detail"] == "some string result"
        assert result["completeness"] == MCP_DEFAULT_COMPLETENESS

    def test_list_wrapped_as_success(self):
        raw = [1, 2, 3]
        result = enforce_structured_response("server", "tool", raw)
        assert result["ok"] is True
        assert result["detail"] == [1, 2, 3]

    def test_completeness_clamped_to_bounds(self):
        # Over 1.0
        raw = {"ok": True, "completeness": 1.5}
        result = enforce_structured_response("server", "tool", raw)
        assert result["completeness"] == 1.0

        # Under 0.0
        raw = {"ok": True, "completeness": -0.5}
        result = enforce_structured_response("server", "tool", raw)
        assert result["completeness"] == 0.0


class TestMcpGuardCall:
    """Test mcp_guard_call integration."""

    def setup_method(self):
        # Reset breakers before each test
        reset_circuit_breaker("test-server")

    def test_successful_call_records_success(self):
        def call_fn():
            return {"ok": True, "detail": "success"}

        result = mcp_guard_call("test-server", "test_tool", call_fn)
        assert result["ok"] is True
        assert result["detail"] == "success"
        status = get_circuit_breaker_status("test-server")
        assert status["state"] == "closed"
        assert status["failures"] == 0

    def test_failed_call_records_failure(self):
        def call_fn():
            return {"ok": False, "error": "timeout", "detail": "upstream timeout"}

        result = mcp_guard_call("test-server", "test_tool", call_fn)
        assert result["ok"] is False
        assert result["error"] == "timeout"
        status = get_circuit_breaker_status("test-server")
        assert status["failures"] == 1

    def test_exception_records_failure(self):
        def call_fn():
            raise ConnectionError("connection refused")

        result = mcp_guard_call("test-server", "test_tool", call_fn)
        assert result["ok"] is False
        assert result["error"] == "exception"
        assert "ConnectionError" in result["detail"]
        status = get_circuit_breaker_status("test-server")
        assert status["failures"] == 1

    def test_null_response_handled(self):
        def call_fn():
            return None

        result = mcp_guard_call("test-server", "test_tool", call_fn)
        assert result["ok"] is False
        assert result["error"] == "null_response"
        status = get_circuit_breaker_status("test-server")
        assert status["failures"] == 1

    def test_circuit_breaker_blocks_after_threshold(self):
        def failing_call():
            return {"ok": False, "error": "timeout"}

        # Trip the breaker
        for _ in range(MCP_CIRCUIT_BREAKER_THRESHOLD):
            mcp_guard_call("test-server", "test_tool", failing_call)

        # Next call should be blocked
        result = mcp_guard_call("test-server", "test_tool", failing_call)
        assert result["ok"] is False
        assert result["error"] == "circuit_breaker_open"
        assert "OPEN" in result["detail"]


class TestIntegration:
    """Integration-style tests."""

    def setup_method(self):
        reset_circuit_breaker("aide-memory")

    def test_aide_memory_recall_flow(self):
        """Simulate aide-memory recall call."""
        def recall_fn():
            # Simulate successful response
            return {"memories": ["fact1", "fact2"]}

        result = mcp_guard_call("aide-memory", "aide_recall", recall_fn)
        assert result["ok"] is True
        assert result["detail"] == {"memories": ["fact1", "fact2"]}
        assert result["completeness"] == MCP_DEFAULT_COMPLETENESS

    def test_aide_memory_remember_flow(self):
        """Simulate aide-memory remember call."""
        def remember_fn():
            return None  # Some MCP tools return None on success

        result = mcp_guard_call("aide-memory", "aide_remember", remember_fn)
        # Null becomes structured error — this is CORRECT behavior per SERF
        assert result["ok"] is False
        assert result["error"] == "null_response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])