"""Tests for P1-03: Loop + Context Guards."""

from __future__ import annotations

import pytest

from context_budget import (
    MAX_TOOL_CALLS_PER_TASK,
    REPETITION_THRESHOLD,
    CONTEXT_BUDGET_ALERT_PCT,
    CONTEXT_BUDGET_KILL_PCT,
    PROGRESSIVE_TOOL_LIMIT,
    ContextBudget,
    estimate_tokens,
    select_progressive_tools,
    RepetitionDetector,
    TaskStepCounter,
    ContextBudgetMonitor,
    check_all_guards,
    reset_session_guards,
    get_repetition_detector,
    get_step_counter,
    get_budget_monitor,
)


class TestContextBudget:
    """Test ContextBudget dataclass."""

    def test_default_window(self):
        budget = ContextBudget()
        assert budget.window_size == 8192
        assert budget.used_tokens == 0
        assert budget.reserved_tokens == 0

    def test_custom_model_window(self):
        budget = ContextBudget(model="glm-5.2", window_size=200000)
        assert budget.window_size == 200000

    def test_available_tokens(self):
        budget = ContextBudget(window_size=10000, reserved_tokens=1000, used_tokens=2000)
        assert budget.available_tokens == 7000

    def test_usage_pct(self):
        budget = ContextBudget(window_size=10000, reserved_tokens=1000, used_tokens=4000)
        # (1000 + 4000) / 10000 = 50%
        assert budget.usage_pct == 50.0

    def test_alert_threshold(self):
        budget = ContextBudget(window_size=10000, used_tokens=8500)
        assert budget.is_alert_threshold() is True  # 85% >= 80%

    def test_kill_threshold(self):
        budget = ContextBudget(window_size=10000, used_tokens=10000)
        assert budget.is_kill_threshold() is True  # 100% >= 100%

    def test_add_usage(self):
        budget = ContextBudget(window_size=10000)
        budget.add_usage(1000)
        assert budget.used_tokens == 1000


class TestEstimateTokens:
    """Test token estimation."""

    def test_short_text(self):
        # 5 chars // 4 = 1, max(1, 1) = 1
        assert estimate_tokens("hello") == 1

    def test_long_text(self):
        text = "x" * 4000
        assert estimate_tokens(text) == 1000

    def test_empty_string(self):
        assert estimate_tokens("") == 1  # max(1, 0)


class TestSelectProgressiveTools:
    """Test progressive tool selection."""

    def test_read_task(self):
        tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "LS", "mcp__aide-memory__aide_recall"]
        selected = select_progressive_tools("read", tools)
        assert len(selected) <= PROGRESSIVE_TOOL_LIMIT
        assert "Read" in selected
        assert "Glob" in selected

    def test_write_task(self):
        tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "LS"]
        selected = select_progressive_tools("write", tools)
        assert len(selected) <= PROGRESSIVE_TOOL_LIMIT
        assert "Write" in selected
        assert "Edit" in selected

    def test_mcp_task(self):
        tools = ["mcp__aide-memory__aide_recall", "mcp__aide-memory__aide_remember", "Read", "Write"]
        selected = select_progressive_tools("mcp", tools)
        assert len(selected) <= PROGRESSIVE_TOOL_LIMIT
        assert any(t.startswith("mcp__") for t in selected)

    def test_general_task(self):
        tools = ["Read", "Write", "Bash", "Grep", "Glob", "LS"]
        selected = select_progressive_tools("general", tools)
        assert len(selected) <= PROGRESSIVE_TOOL_LIMIT

    def test_limit_respected(self):
        tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "LS", "Task"]
        selected = select_progressive_tools("read", tools, limit=3)
        assert len(selected) == 3


class TestRepetitionDetector:
    """Test repetition detection."""

    def setup_method(self):
        reset_session_guards("test-session")

    def test_first_call_count_1(self):
        detector = get_repetition_detector("test-session")
        count = detector.record("Read", {"path": "file.txt"})
        assert count == 1

    def test_consecutive_identical_increments(self):
        detector = get_repetition_detector("test-session")
        detector.record("Read", {"path": "file.txt"})
        count = detector.record("Read", {"path": "file.txt"})
        assert count == 2

    def test_three_identical_exceeds_threshold(self):
        detector = get_repetition_detector("test-session")
        detector.record("Read", {"path": "file.txt"})
        detector.record("Read", {"path": "file.txt"})
        count = detector.record("Read", {"path": "file.txt"})
        assert count == 3
        assert detector.is_repetition_exceeded("Read", {"path": "file.txt"}) is True

    def test_different_params_not_consecutive(self):
        detector = get_repetition_detector("test-session")
        detector.record("Read", {"path": "file1.txt"})
        count = detector.record("Read", {"path": "file2.txt"})
        assert count == 1  # Different params = not consecutive

    def test_different_tool_resets(self):
        detector = get_repetition_detector("test-session")
        detector.record("Read", {"path": "file.txt"})
        detector.record("Read", {"path": "file.txt"})
        count = detector.record("Write", {"path": "file.txt", "content": "x"})
        assert count == 1  # Different tool = not consecutive


class TestTaskStepCounter:
    """Test step counter."""

    def setup_method(self):
        reset_session_guards("test-session")

    def test_increment(self):
        counter = get_step_counter("test-session")
        count = counter.increment("task-1")
        assert count == 1

    def test_kill_at_max(self):
        counter = get_step_counter("test-session")
        for i in range(MAX_TOOL_CALLS_PER_TASK):
            counter.increment("task-1")
        assert counter.is_kill_threshold() is True

    def test_new_task_resets(self):
        counter = get_step_counter("test-session")
        for _ in range(5):
            counter.increment("task-1")
        count = counter.increment("task-2")
        assert count == 1  # Reset for new task


class TestContextBudgetMonitor:
    """Test context budget monitor."""

    def setup_method(self):
        reset_session_guards("test-session")

    def test_alert_at_80_percent(self):
        monitor = get_budget_monitor("test-session")
        monitor.set_model("default")  # 8192 window
        # Add enough to trigger 80% alert: 8192 * 0.8 = 6553.6, need >= 6554
        monitor.budget.add_usage(6554)
        assert monitor.budget.is_alert_threshold() is True

    def test_kill_at_100_percent(self):
        monitor = get_budget_monitor("test-session")
        monitor.set_model("default")
        monitor.budget.add_usage(8192)
        assert monitor.budget.is_kill_threshold() is True

    def test_add_tool_response(self):
        monitor = get_budget_monitor("test-session")
        monitor.set_model("default")
        alert, kill = monitor.add_tool_response("x" * 4000)  # ~1000 tokens
        assert alert is False
        assert kill is False

    def test_usage_pct(self):
        monitor = get_budget_monitor("test-session")
        monitor.set_model("default")
        monitor.budget.add_usage(4096)  # 50%
        assert monitor.get_usage_pct() == 50.0


class TestCheckAllGuards:
    """Test integrated guard checks."""

    def setup_method(self):
        reset_session_guards("test-session")

    def test_no_guards_triggered_normal(self):
        results = check_all_guards(
            "test-session",
            "Read",
            {"path": "file.txt"},
            "some response",
            "task-1"
        )
        assert results["step_limit"]["triggered"] is False
        assert results["repetition"]["triggered"] is False
        assert results["context_budget"]["kill"] is False

    def test_step_limit_triggered(self):
        for i in range(MAX_TOOL_CALLS_PER_TASK):
            check_all_guards("test-session", "Read", {"path": "file.txt"}, "resp", "task-1")
        results = check_all_guards("test-session", "Read", {"path": "file.txt"}, "resp", "task-1")
        assert results["step_limit"]["triggered"] is True
        assert results["step_limit"]["count"] == MAX_TOOL_CALLS_PER_TASK + 1

    def test_repetition_triggered(self):
        for _ in range(REPETITION_THRESHOLD + 1):
            check_all_guards("test-session", "Read", {"path": "file.txt"}, "resp", "task-1")
        results = check_all_guards("test-session", "Read", {"path": "file.txt"}, "resp", "task-1")
        assert results["repetition"]["triggered"] is True

    def test_context_kill_triggered(self):
        check_all_guards("test-session", "Read", {"path": "file.txt"}, "x" * 32000, "task-1")  # ~8000 tokens
        results = check_all_guards("test-session", "Read", {"path": "file.txt"}, "x" * 32000, "task-1")
        assert results["context_budget"]["kill"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])