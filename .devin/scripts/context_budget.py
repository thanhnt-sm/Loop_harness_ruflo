"""Context budget + Loop guards — P1-03.

Cung cap ContextBudget, RepetitionDetector, TaskStepCounter, ContextBudgetMonitor
va ham check_all_guards cho post_tool_engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# Re-export constants tu post_tool_config de dam bao single source of truth
try:
    from post_tool_config import (
        MAX_TOOL_CALLS_PER_TASK,
        REPETITION_THRESHOLD,
        CONTEXT_BUDGET_ALERT_PCT,
        CONTEXT_BUDGET_KILL_PCT,
        PROGRESSIVE_TOOL_LIMIT,
    )
except ImportError:
    MAX_TOOL_CALLS_PER_TASK = 15
    REPETITION_THRESHOLD = 2
    CONTEXT_BUDGET_ALERT_PCT = 80
    CONTEXT_BUDGET_KILL_PCT = 100
    PROGRESSIVE_TOOL_LIMIT = 4


@dataclass
class ContextBudget:
    window_size: int = 8192
    used_tokens: int = 0
    reserved_tokens: int = 0
    model: str = "default"

    def __init__(self, window_size: int = 8192, used_tokens: int = 0, reserved_tokens: int = 0, model: str = "default"):
        # Ho tro custom model window
        if model != "default" and window_size == 8192:
            # model truyen window_size khac nhau trong test_custom_model_window
            pass
        self.window_size = window_size
        self.used_tokens = used_tokens
        self.reserved_tokens = reserved_tokens
        self.model = model

    @property
    def available_tokens(self) -> int:
        return self.window_size - self.reserved_tokens - self.used_tokens

    @property
    def usage_pct(self) -> float:
        total_used = self.reserved_tokens + self.used_tokens
        if self.window_size == 0:
            return 0.0
        return (total_used / self.window_size) * 100.0

    def is_alert_threshold(self) -> bool:
        return self.usage_pct >= CONTEXT_BUDGET_ALERT_PCT

    def is_kill_threshold(self) -> bool:
        return self.usage_pct >= CONTEXT_BUDGET_KILL_PCT

    def add_usage(self, tokens: int) -> None:
        self.used_tokens += tokens


def estimate_tokens(text: str) -> int:
    if not text:
        return 1
    return max(1, len(text) // 4)


def select_progressive_tools(task_type: str, tools: List[str], limit: int = PROGRESSIVE_TOOL_LIMIT) -> List[str]:
    """Chon toi da limit tools phu hop voi task_type."""
    task_lower = task_type.lower()
    # Priority mapping
    priority = []
    if "read" in task_lower:
        priority = ["Read", "Glob", "Grep", "LS"]
    elif "write" in task_lower:
        priority = ["Write", "Edit", "Read"]
    elif "mcp" in task_lower:
        priority = [t for t in tools if t.startswith("mcp__")]
    else:
        priority = ["Read", "Write", "Bash", "Grep"]

    selected: List[str] = []
    for p in priority:
        if p in tools and p not in selected:
            selected.append(p)
            if len(selected) >= limit:
                break
    # Fill con lai neu chua du limit
    for t in tools:
        if t not in selected and len(selected) < limit:
            selected.append(t)
        if len(selected) >= limit:
            break
    return selected[:limit]


class RepetitionDetector:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._last_tool: str | None = None
        self._last_params: dict | None = None
        self._count: int = 0

    def record(self, tool: str, params: dict) -> int:
        if tool == self._last_tool and params == self._last_params:
            self._count += 1
        else:
            self._count = 1
            self._last_tool = tool
            self._last_params = params
        return self._count

    def is_repetition_exceeded(self, tool: str, params: dict) -> bool:
        # Kiem tra count hien tai co vuot threshold khong (chi khi trung tool+params)
        if tool == self._last_tool and params == self._last_params:
            return self._count > REPETITION_THRESHOLD
        return False


class TaskStepCounter:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._counts: Dict[str, int] = {}
        self._current_task: str | None = None

    def increment(self, task_id: str) -> int:
        if task_id != self._current_task:
            self._current_task = task_id
            # Khong reset counts cu, chi tao entry moi neu chua co
            if task_id not in self._counts:
                self._counts[task_id] = 0
        self._counts[task_id] += 1
        return self._counts[task_id]

    def is_kill_threshold(self) -> bool:
        if self._current_task is None:
            return False
        return self._counts.get(self._current_task, 0) >= MAX_TOOL_CALLS_PER_TASK


class ContextBudgetMonitor:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.budget = ContextBudget()

    def set_model(self, model: str) -> None:
        # Map model -> window size
        windows = {
            "default": 8192,
            "glm-5.2": 200000,
            "kimi-k2.7": 128000,
            "lightning": 200000,
            "small": 8192,
        }
        self.budget.window_size = windows.get(model, 8192)
        self.budget.model = model

    def add_tool_response(self, response: str) -> tuple[bool, bool]:
        tokens = estimate_tokens(response)
        self.budget.add_usage(tokens)
        return self.budget.is_alert_threshold(), self.budget.is_kill_threshold()

    def get_usage_pct(self) -> float:
        return self.budget.usage_pct


# Global registries per session
_REPETITION_DETECTORS: Dict[str, RepetitionDetector] = {}
_STEP_COUNTERS: Dict[str, TaskStepCounter] = {}
_BUDGET_MONITORS: Dict[str, ContextBudgetMonitor] = {}


def get_repetition_detector(session_id: str) -> RepetitionDetector:
    if session_id not in _REPETITION_DETECTORS:
        _REPETITION_DETECTORS[session_id] = RepetitionDetector(session_id)
    return _REPETITION_DETECTORS[session_id]


def get_step_counter(session_id: str) -> TaskStepCounter:
    if session_id not in _STEP_COUNTERS:
        _STEP_COUNTERS[session_id] = TaskStepCounter(session_id)
    return _STEP_COUNTERS[session_id]


def get_budget_monitor(session_id: str) -> ContextBudgetMonitor:
    if session_id not in _BUDGET_MONITORS:
        _BUDGET_MONITORS[session_id] = ContextBudgetMonitor(session_id)
    return _BUDGET_MONITORS[session_id]


def reset_session_guards(session_id: str) -> None:
    _REPETITION_DETECTORS.pop(session_id, None)
    _STEP_COUNTERS.pop(session_id, None)
    _BUDGET_MONITORS.pop(session_id, None)


def check_all_guards(session_id: str, tool_name: str, tool_input: dict, tool_response: Any, task_id: str) -> Dict[str, Any]:
    """Chay tat ca guards, tra ve dict ket qua."""
    detector = get_repetition_detector(session_id)
    counter = get_step_counter(session_id)
    monitor = get_budget_monitor(session_id)

    rep_count = detector.record(tool_name, tool_input or {})
    rep_triggered = detector.is_repetition_exceeded(tool_name, tool_input or {})

    step_count = counter.increment(task_id or "__default__")
    step_triggered = counter.is_kill_threshold()

    # Context budget: estimate tokens tu tool_response
    resp_str = str(tool_response) if tool_response is not None else ""
    monitor.add_tool_response(resp_str)

    return {
        "repetition": {"triggered": rep_triggered, "count": rep_count},
        "step_limit": {"triggered": step_triggered, "count": step_count},
        "context_budget": {
            "alert": monitor.budget.is_alert_threshold(),
            "kill": monitor.budget.is_kill_threshold(),
            "usage_pct": monitor.budget.usage_pct,
        },
    }
