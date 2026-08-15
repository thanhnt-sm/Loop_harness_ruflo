#!/usr/bin/env python3
"""Edge classes for graph routing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, ConfigDict


class Edge(ABC):
    """Abstract base class for graph edges."""

    @abstractmethod
    def evaluate(self, state: Any) -> Optional[str]:
        """Evaluate edge condition and return target node name.

        Returns:
            Target node name, or None if edge not taken.
        """
        pass

    @abstractmethod
    def get_targets(self) -> list[str]:
        """Get all possible target nodes."""
        pass


@dataclass
class DirectEdge(Edge):
    """Unconditional edge - always taken."""

    target: str

    def evaluate(self, state: Any) -> str:
        return self.target

    def get_targets(self) -> list[str]:
        return [self.target]


@dataclass
class ConditionalEdge(Edge):
    """Conditional edge - predicate determines target."""

    condition: Callable[[Any], Union[str, dict]]
    targets: dict[str, str]  # condition_value -> target_node

    def evaluate(self, state: Any) -> Optional[str]:
        try:
            result = self.condition(state)
            if isinstance(result, str):
                return self.targets.get(result)
            elif isinstance(result, dict):
                for cond, target in self.targets.items():
                    if cond in result:
                        return target
        except Exception:
            pass
        return None

    def get_targets(self) -> list[str]:
        return list(self.targets.values())


@dataclass
class FanOutEdge(Edge):
    """Parallel fan-out edge - all targets execute simultaneously."""

    targets: list[str]
    reducer: Optional[Callable[[list[Any]], Any]] = None

    def evaluate(self, state: Any) -> list[str]:
        return self.targets

    def get_targets(self) -> list[str]:
        return self.targets


@dataclass
class FanInEdge(Edge):
    """Fan-in edge - joins parallel branches."""

    target: str
    reducer: Optional[Callable[[list[Any]], Any]] = None

    def evaluate(self, state: Any) -> str:
        return self.target

    def get_targets(self) -> list[str]:
        return [self.target]


@dataclass
class InterruptEdge(Edge):
    """Edge that interrupts for human input."""

    target: str
    human_prompt: str
    resume_key: str = "human_input"

    def evaluate(self, state: Any) -> str:
        return self.target

    def get_targets(self) -> list[str]:
        return [self.target]


class EdgeBuilder:
    """Fluent builder for creating edges."""

    @staticmethod
    def direct(target: str) -> DirectEdge:
        return DirectEdge(target=target)

    @staticmethod
    def conditional(
        condition: Callable[[Any], Union[str, dict]],
        targets: dict[str, str],
    ) -> ConditionalEdge:
        return ConditionalEdge(condition=condition, targets=targets)

    @staticmethod
    def fanout(
        targets: list[str],
        reducer: Optional[Callable[[list[Any]], Any]] = None,
    ) -> FanOutEdge:
        return FanOutEdge(targets=targets, reducer=reducer)

    @staticmethod
    def fanin(target: str, reducer: Optional[Callable[[list[Any]], Any]] = None) -> FanInEdge:
        return FanInEdge(target=target, reducer=reducer)

    @staticmethod
    def interrupt(
        target: str,
        human_prompt: str,
        resume_key: str = "human_input",
    ) -> InterruptEdge:
        return InterruptEdge(target=target, human_prompt=human_prompt, resume_key=resume_key)


# Predefined common conditions
class CommonConditions:
    @staticmethod
    def has_key(key: str, expected: Any = True) -> Callable[[Any], str]:
        def check(state: Any) -> str:
            if hasattr(state, key):
                val = getattr(state, key)
            elif isinstance(state, dict):
                val = state.get(key)
            else:
                val = None
            return "true" if val == expected else "false"
        return check

    @staticmethod
    def greater_than(key: str, threshold: float) -> Callable[[Any], str]:
        def check(state: Any) -> str:
            if hasattr(state, key):
                val = getattr(state, key)
            elif isinstance(state, dict):
                val = state.get(key)
            else:
                return "false"
            return "true" if val > threshold else "false"
        return check

    @staticmethod
    def contains(key: str, substring: str) -> Callable[[Any], str]:
        def check(state: Any) -> str:
            if hasattr(state, key):
                val = getattr(state, key)
            elif isinstance(state, dict):
                val = state.get(key)
            else:
                return "false"
            return "true" if substring in str(val) else "false"
        return check

    @staticmethod
    def status_equals(key: str, expected_status: str) -> Callable[[Any], str]:
        def check(state: Any) -> str:
            if hasattr(state, key):
                val = getattr(state, key)
            elif isinstance(state, dict):
                val = state.get(key)
            else:
                return "false"
            return "true" if val == expected_status else "false"
        return check