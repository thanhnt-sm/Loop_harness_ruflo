#!/usr/bin/env python3
"""TokenBudget & CostOptimizer — Budget management and model routing."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ModelInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    capabilities: list[str] = field(default_factory=list)
    max_tokens: int = 4096
    streaming: bool = True


class TokenBudget(BaseModel):
    """Per-session/task/agent token budget with atomic reservations."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    budget_usd: float
    cost_per_1k_input: float = 0.002
    cost_per_1k_output: float = 0.002
    _spent_usd: float = field(default=0.0)
    _reserved_usd: float = field(default=0.0)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1000 * self.cost_per_1k_input +
                output_tokens / 1000 * self.cost_per_1k_output)

    async def reserve(self, estimated_input: int, estimated_output: int) -> bool:
        """Atomically reserve budget for estimated tokens."""
        estimated = self.estimate_cost(estimated_input, estimated_output)
        async with self._lock:
            if self._spent_usd + self._reserved_usd + estimated > self.budget_usd:
                return False
            self._reserved_usd += estimated
            return True

    async def record_actual(self, input_tokens: int, output_tokens: int) -> None:
        """Record actual usage, adjusting reservation."""
        actual = self.estimate_cost(input_tokens, output_tokens)
        async with self._lock:
            # Release reservation, charge actual
            self._reserved_usd = max(0, self._reserved_usd - actual)
            self._spent_usd += actual

    async def release_reservation(self, estimated_input: int, estimated_output: int) -> None:
        """Release a reservation (e.g., task cancelled)."""
        estimated = self.estimate_cost(estimated_input, estimated_output)
        async with self._lock:
            self._reserved_usd = max(0, self._reserved_usd - estimated)

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    @property
    def reserved_usd(self) -> float:
        return self._reserved_usd

    @property
    def remaining_usd(self) -> float:
        return max(0, self.budget_usd - self._spent_usd - self._reserved_usd)

    @property
    def percent_used(self) -> float:
        if self.budget_usd <= 0:
            return 0.0
        return min(100, (self._spent_usd + self._reserved_usd) / self.budget_usd * 100)

    @property
    def is_exceeded(self) -> bool:
        return self._spent_usd >= self.budget_usd

    def reset(self) -> None:
        self._spent_usd = 0.0
        self._reserved_usd = 0.0


class GlobalTokenBudget(TokenBudget):
    """Global org/repo budget aggregating across sessions."""

    _sessions: dict[str, TokenBudget] = field(default_factory=dict)

    def get_session(self, session_id: str) -> TokenBudget:
        if session_id not in self._sessions:
            self._sessions[session_id] = TokenBudget(
                budget_usd=self.budget_usd,
                cost_per_1k_input=self.cost_per_1k_input,
                cost_per_1k_output=self.cost_per_1k_output,
            )
        return self._sessions[session_id]

    async def record_session_usage(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int
    ) -> None:
        session = self.get_session(session_id)
        await session.record_actual(input_tokens, output_tokens)
        # Also record in global
        await self.record_actual(input_tokens, output_tokens)

    @property
    def total_sessions(self) -> int:
        return len(self._sessions)

    def get_top_spenders(self, n: int = 5) -> list[tuple[str, float]]:
        return sorted(
            [(sid, b.spent_usd) for sid, b in self._sessions.items()],
            key=lambda x: x[1],
            reverse=True
        )[:n]


class CostOptimizer:
    """Route tasks to cheapest capable model."""

    def __init__(self, models: Optional[list[ModelInfo]] = None):
        self._models = models or [
            ModelInfo(
                name="lightning",
                cost_per_1k_input=0.002,
                cost_per_1k_output=0.006,
                capabilities=["fast", "code", "analysis"],
                max_tokens=8192,
            ),
            ModelInfo(
                name="glm",
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                capabilities=["free", "reasoning", "analysis"],
                max_tokens=32768,
            ),
            ModelInfo(
                name="kimi",
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                capabilities=["free", "open_source", "code"],
                max_tokens=128000,
            ),
        ]
        self._model_by_name = {m.name: m for m in self._models}

    def select_model(
        self,
        required_capabilities: list[str],
        max_cost_per_1k: Optional[float] = None,
        prefer_streaming: bool = True,
    ) -> str:
        """Select cheapest model that has all required capabilities."""
        candidates = []

        for model in self._models:
            if not all(cap in model.capabilities for cap in required_capabilities):
                continue
            if prefer_streaming and not model.streaming:
                continue
            if max_cost_per_1k is not None:
                if model.cost_per_1k_input > max_cost_per_1k:
                    continue
            candidates.append((model.cost_per_1k_input + model.cost_per_1k_output, model.name))

        if not candidates:
            # Fallback: return first model with required capabilities (any cost)
            for model in self._models:
                if all(cap in model.capabilities for cap in required_capabilities):
                    return model.name
            # Ultimate fallback
            return self._models[0].name

        candidates.sort()  # Sort by total cost
        return candidates[0][1]

    def estimate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        model = self._model_by_name.get(model_name)
        if not model:
            # Default pricing
            return (input_tokens / 1000 * 0.002) + (output_tokens / 1000 * 0.006)
        return (input_tokens / 1000 * model.cost_per_1k_input +
                output_tokens / 1000 * model.cost_per_1k_output)

    def get_model_info(self, name: str) -> Optional[ModelInfo]:
        return self._model_by_name.get(name)

    def list_models(self) -> list[ModelInfo]:
        return self._models.copy()


class SemanticCache:
    """Semantic cache for repeated prompts (exact + fuzzy matching)."""

    def __init__(self, max_entries: int = 1000, similarity_threshold: float = 0.95):
        self._max_entries = max_entries
        self._threshold = similarity_threshold
        self._cache: dict[str, tuple[str, int, float]] = {}  # prompt_hash -> (response, tokens, timestamp)
        self._embeddings: dict[str, list[float]] = {}  # For future fuzzy matching

    def _hash(self, prompt: str) -> str:
        import hashlib
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def get(self, prompt: str) -> Optional[tuple[str, int]]:
        """Get cached response if available."""
        key = self._hash(prompt)
        if key in self._cache:
            response, tokens, _ = self._cache[key]
            return response, tokens
        return None

    def set(self, prompt: str, response: str, tokens: int) -> None:
        key = self._hash(prompt)
        # Evict if at capacity (simple FIFO)
        if len(self._cache) >= self._max_entries:
            oldest = min(self._cache.items(), key=lambda x: x[1][2])
            del self._cache[oldest[0]]

        self._cache[key] = (response, tokens, datetime.now(timezone.utc).timestamp())

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> dict:
        return {
            "entries": len(self._cache),
            "max_entries": self._max_entries,
            "hit_rate": getattr(self, "_hits", 0) / max(1, getattr(self, "_lookups", 1)),
        }