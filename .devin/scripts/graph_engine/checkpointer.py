#!/usr/bin/env python3
"""Checkpointer implementations for graph persistence."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


@dataclass
class Checkpoint:
    """Checkpoint data for graph execution."""
    thread_id: str
    state: dict
    history: list[dict]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)


class BaseCheckpointer(ABC):
    """Abstract base class for checkpoint persistence."""

    @abstractmethod
    async def get(self, thread_id: str) -> Optional[Checkpoint]:
        """Load checkpoint for thread."""
        pass

    @abstractmethod
    async def put(self, thread_id: str, state: dict, history: list[dict]) -> None:
        """Save checkpoint for thread."""
        pass

    @abstractmethod
    async def list_threads(self) -> list[str]:
        """List all thread IDs with checkpoints."""
        pass

    @abstractmethod
    async def delete(self, thread_id: str) -> None:
        """Delete checkpoint for thread."""
        pass


class MemoryCheckpointer(BaseCheckpointer):
    """In-memory checkpointer for development/testing."""

    def __init__(self):
        self._checkpoints: dict[str, Checkpoint] = {}
        self._lock = asyncio.Lock()

    async def get(self, thread_id: str) -> Optional[Checkpoint]:
        async with self._lock:
            return self._checkpoints.get(thread_id)

    async def put(self, thread_id: str, state: dict, history: list[dict]) -> None:
        async with self._lock:
            self._checkpoints[thread_id] = Checkpoint(
                thread_id=thread_id,
                state=state,
                history=history,
            )

    async def list_threads(self) -> list[str]:
        async with self._lock:
            return list(self._checkpoints.keys())

    async def delete(self, thread_id: str) -> None:
        async with self._lock:
            self._checkpoints.pop(thread_id, None)


class SQLiteCheckpointer(BaseCheckpointer):
    """SQLite-based checkpointer for persistent storage."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        async with self._lock:
            if self._initialized:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    history TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            conn.commit()
            conn.close()
            self._initialized = True

    async def get(self, thread_id: str) -> Optional[Checkpoint]:
        await self.initialize()
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return Checkpoint(
                    thread_id=row["thread_id"],
                    state=json.loads(row["state"]),
                    history=json.loads(row["history"]),
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
            return None

    async def put(self, thread_id: str, state: dict, history: list[dict]) -> None:
        await self.initialize()
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints
                (thread_id, state, history, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                thread_id,
                json.dumps(state),
                json.dumps(history),
                datetime.now(timezone.utc).isoformat(),
                json.dumps({}),
            ))
            conn.commit()
            conn.close()

    async def list_threads(self) -> list[str]:
        await self.initialize()
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT thread_id FROM checkpoints")
            threads = [row[0] for row in cursor.fetchall()]
            conn.close()
            return threads

    async def delete(self, thread_id: str) -> None:
        await self.initialize()
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            conn.commit()
            conn.close()


class RedisCheckpointer(BaseCheckpointer):
    """Redis-based checkpointer for distributed deployments."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", prefix: str = "checkpoint:"):
        self.redis_url = redis_url
        self.prefix = prefix
        self._redis = None
        self._lock = asyncio.Lock()

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _key(self, thread_id: str) -> str:
        return f"{self.prefix}{thread_id}"

    async def get(self, thread_id: str) -> Optional[Checkpoint]:
        r = await self._get_redis()
        data = await r.get(self._key(thread_id))
        if data:
            return Checkpoint.model_validate_json(data)
        return None

    async def put(self, thread_id: str, state: dict, history: list[dict]) -> None:
        r = await self._get_redis()
        checkpoint = Checkpoint(
            thread_id=thread_id,
            state=state,
            history=history,
        )
        await r.set(self._key(thread_id), checkpoint.model_dump_json())

    async def list_threads(self) -> list[str]:
        r = await self._get_redis()
        keys = await r.keys(f"{self.prefix}*")
        return [k.replace(self.prefix, "") for k in keys]

    async def delete(self, thread_id: str) -> None:
        r = await self._get_redis()
        await r.delete(self._key(thread_id))

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None


class CheckpointerFactory:
    """Factory for creating checkpointers."""

    @staticmethod
    async def create(backend: str = "memory", **kwargs) -> BaseCheckpointer:
        if backend == "memory":
            return MemoryCheckpointer()
        elif backend == "sqlite":
            db_path = kwargs.get("db_path", Path("checkpoints.db"))
            checkpointer = SQLiteCheckpointer(db_path)
            await checkpointer.initialize()
            return checkpointer
        elif backend == "redis":
            redis_url = kwargs.get("redis_url", "redis://localhost:6379/0")
            return RedisCheckpointer(redis_url)
        else:
            raise ValueError(f"Unknown checkpointer backend: {backend}")