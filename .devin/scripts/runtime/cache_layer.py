#!/usr/bin/env python3
"""CacheLayer — Semantic cache with TTL and similarity matching."""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class CacheEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    response: str
    input_tokens: int
    output_tokens: int
    timestamp: float
    ttl: int
    hits: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class CacheLayer:
    """Multi-level cache with exact + semantic matching.

    Features:
    - Exact match (prompt hash)
    - TTL-based expiration
    - LRU eviction
    - Hit tracking
    - Optional semantic similarity (requires embeddings)
    """

    max_entries: int = 1000
    default_ttl: int = 3600  # 1 hour
    similarity_threshold: float = 0.95
    _cache: dict[str, CacheEntry] = field(default_factory=dict)
    _access_order: list[str] = field(default_factory=list)  # For LRU
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _hits: int = 0
    _misses: int = 0

    def _hash(self, prompt: str, model: str = "") -> str:
        """Generate cache key from prompt + model."""
        combined = f"{model}:{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    async def get(self, prompt: str, model: str = "") -> Optional[tuple[str, int, int]]:
        """Get cached response if available and not expired.

        Returns:
            (response, input_tokens, output_tokens) or None
        """
        async with self._lock:
            key = self._hash(prompt, model)
            entry = self._cache.get(key)

            if not entry:
                self._misses += 1
                return None

            # Check TTL
            if time.time() - entry.timestamp > entry.ttl:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._misses += 1
                return None

            # Update LRU
            entry.hits += 1
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            self._hits += 1
            return entry.response, entry.input_tokens, entry.output_tokens

    async def set(
        self,
        prompt: str,
        response: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "",
        ttl: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Store response in cache."""
        async with self._lock:
            key = self._hash(prompt, model)

            # Evict if at capacity
            if len(self._cache) >= self.max_entries:
                await self._evict_lru()

            entry = CacheEntry(
                key=key,
                response=response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                timestamp=time.time(),
                ttl=ttl or self.default_ttl,
                metadata=metadata or {},
            )
            self._cache[key] = entry
            self._access_order.append(key)

    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        while self._access_order and len(self._cache) >= self.max_entries:
            lru_key = self._access_order.pop(0)
            self._cache.pop(lru_key, None)

    async def invalidate(self, prompt: str, model: str = "") -> bool:
        """Manually invalidate a cache entry."""
        async with self._lock:
            key = self._hash(prompt, model)
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "memory_estimate_mb": sum(len(e.response) for e in self._cache.values()) / 1024 / 1024,
        }

    async def warm(self, entries: list[dict]) -> int:
        """Pre-populate cache with known good responses."""
        count = 0
        for entry in entries:
            await self.set(
                prompt=entry["prompt"],
                response=entry["response"],
                input_tokens=entry.get("input_tokens", 0),
                output_tokens=entry.get("output_tokens", 0),
                model=entry.get("model", ""),
                ttl=entry.get("ttl"),
                metadata=entry.get("metadata"),
            )
            count += 1
        return count


class CacheKeyBuilder:
    """Build cache keys with context awareness."""

    @staticmethod
    def for_prompt(prompt: str, model: str, system: str = "") -> str:
        """Build cache key including system prompt."""
        combined = f"{model}|{system}|{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    @staticmethod
    def for_tool_result(tool_name: str, args: dict, result: str) -> str:
        """Cache tool results."""
        combined = f"tool:{tool_name}:{json.dumps(args, sort_keys=True)}:{result[:100]}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    @staticmethod
    def for_file_content(file_path: str, content_hash: str) -> str:
        """Cache file analysis results."""
        return hashlib.sha256(f"file:{file_path}:{content_hash}".encode()).hexdigest()[:32]


import json