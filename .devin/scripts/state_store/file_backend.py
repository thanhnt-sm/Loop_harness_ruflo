#!/usr/bin/env python3
"""FileBackend — Local development state store (JSONL + SQLite index).

Implements StateStore interface using:
- Append-only JSONL log for durability and replay
- SQLite index for fast key lookups and transactions
- Per-key TTL with active-session pinning
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import aiosqlite

from .interface import (
    ConcurrencyError,
    ConcurrencyMode,
    ConsistencyLevel,
    HealthStatus,
    KeyNotFoundError,
    StateEntry,
    StateOptions,
    StateStore,
    Transaction,
    TransactionError,
)


class _FileTransaction:
    """Transaction implementation for FileBackend."""

    def __init__(self, backend: "FileBackend"):
        self._backend = backend
        self._ops: list[tuple[str, str, Optional[bytes], Optional[StateOptions]]] = []
        self._committed = False
        self._rolled_back = False

    async def get(self, key: str) -> Optional[StateEntry]:
        # Check uncommitted ops first
        for op_type, k, v, _ in reversed(self._ops):
            if k == key:
                if op_type == "delete":
                    return None
                if op_type == "upsert" and v is not None:
                    return StateEntry(
                        key=key,
                        value=v,
                        etag=self._etag(v),
                        updated_at=datetime.now(timezone.utc),
                    )
        # Fall back to backend
        try:
            return await self._backend.get(key)
        except KeyNotFoundError:
            return None

    async def set(
        self,
        key: str,
        value: bytes,
        options: Optional[StateOptions] = None
    ) -> StateEntry:
        self._ops.append(("upsert", key, value, options))
        etag = self._etag(value)
        return StateEntry(
            key=key,
            value=value,
            etag=etag,
            updated_at=datetime.now(timezone.utc),
        )

    async def delete(self, key: str) -> None:
        self._ops.append(("delete", key, None, None))

    async def commit(self) -> None:
        if self._committed or self._rolled_back:
            raise TransactionError("Transaction already completed")
        await self._backend._commit_transaction(self._ops)
        self._committed = True

    async def rollback(self) -> None:
        if self._committed or self._rolled_back:
            raise TransactionError("Transaction already completed")
        self._ops.clear()
        self._rolled_back = True

    @staticmethod
    def _etag(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()[:16]


class FileBackend:
    """File-based state store for local development.

    Storage:
    - JSONL log: append-only event log for durability/replay
    - SQLite DB: key->value index with ETags, TTL, metadata
    """

    def __init__(
        self,
        root: Path,
        name: str = "default",
        shards: int = 1
    ):
        self.root = root
        self.name = name
        self.shards = max(1, shards)
        self._log_path = root / f"{name}.log.jsonl"
        self._db_path = root / f"{name}.db"
        self._lock = asyncio.Lock()
        self._initialized = False
        self._shard_locks: dict[int, asyncio.Lock] = {}

    async def initialize(self) -> None:
        """Initialize log file and SQLite database."""
        async with self._lock:
            if self._initialized:
                return
            self.root.mkdir(parents=True, exist_ok=True)
            self._log_path.touch(exist_ok=True)

            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS state (
                        key TEXT PRIMARY KEY,
                        value BLOB NOT NULL,
                        etag TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        expires_at TEXT,
                        metadata TEXT,
                        shard INTEGER NOT NULL
                    )
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_expires_at ON state(expires_at)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_shard ON state(shard)
                """)
                await db.commit()

            # Create shard locks
            for i in range(self.shards):
                self._shard_locks[i] = asyncio.Lock()

            self._initialized = True

    @property
    def backend_name(self) -> str:
        return f"file:{self.name}"

    def _shard_for_key(self, key: str) -> int:
        """Consistent hashing for sharding."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) % self.shards

    def _get_shard_lock(self, key: str) -> asyncio.Lock:
        return self._shard_locks[self._shard_for_key(key)]

    @staticmethod
    def _etag(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()[:16]

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_iso(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _serialize_entry(self, entry: StateEntry) -> dict:
        return {
            "key": entry.key,
            "value": entry.value.hex(),
            "etag": entry.etag,
            "updated_at": entry.updated_at.isoformat(),
            "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
            "metadata": entry.metadata,
            "shard": self._shard_for_key(entry.key),
        }

    def _deserialize_row(self, row: tuple) -> StateEntry:
        return StateEntry(
            key=row[0],
            value=bytes.fromhex(row[1]),
            etag=row[2],
            updated_at=self._parse_iso(row[3]),
            expires_at=self._parse_iso(row[4]) if row[4] else None,
            metadata=json.loads(row[5]) if row[5] else None,
        )

    async def _append_log(self, event: dict) -> None:
        """Append event to JSONL log (durability)."""
        f = await aiofiles.open(self._log_path, "a")
        async with f:
            await f.write(json.dumps(event, separators=(",", ":")) + "\n")

    async def _commit_transaction(
        self,
        ops: list[tuple[str, str, Optional[bytes], Optional[StateOptions]]]
    ) -> None:
        """Commit a batch of operations atomically."""
        async with self._lock:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("BEGIN IMMEDIATE")
                try:
                    for op_type, key, value, options in ops:
                        shard = self._shard_for_key(key)
                        now = self._now_iso()
                        expires_at = None
                        if options and options.ttl_seconds:
                            expires_at = (
                                datetime.now(timezone.utc).timestamp() + options.ttl_seconds
                            )
                            expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()

                        if op_type == "upsert" and value is not None:
                            etag = self._etag(value)
                            # Check concurrency
                            if options and options.concurrency == ConcurrencyMode.FIRST_WRITE:
                                cursor = await db.execute(
                                    "SELECT etag FROM state WHERE key = ?", (key,)
                                )
                                existing = await cursor.fetchone()
                                if existing and existing[0] != options.etag:
                                    raise ConcurrencyError(f"ETag mismatch for key: {key}")

                            await db.execute("""
                                INSERT OR REPLACE INTO state
                                (key, value, etag, updated_at, expires_at, metadata, shard)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                key,
                                value.hex(),
                                etag,
                                now,
                                expires_at,
                                json.dumps(options.metadata) if options and options.metadata else None,
                                shard,
                            ))
                            # Log event
                            await self._append_log({
                                "type": "upsert",
                                "key": key,
                                "etag": etag,
                                "ts": now,
                            })
                        elif op_type == "delete":
                            if options and options.concurrency == ConcurrencyMode.FIRST_WRITE:
                                cursor = await db.execute(
                                    "SELECT etag FROM state WHERE key = ?", (key,)
                                )
                                existing = await cursor.fetchone()
                                if existing and existing[0] != options.etag:
                                    raise ConcurrencyError(f"ETag mismatch for key: {key}")

                            await db.execute("DELETE FROM state WHERE key = ?", (key,))
                            await self._append_log({
                                "type": "delete",
                                "key": key,
                                "ts": now,
                            })
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

    # --- StateStore Interface ---

    async def get(self, key: str, options: Optional[StateOptions] = None) -> StateEntry:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT key, value, etag, updated_at, expires_at, metadata FROM state WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            if not row:
                raise KeyNotFoundError(f"Key not found: {key}")

            entry = self._deserialize_row(row)

            # Check TTL
            if entry.expires_at and entry.expires_at < datetime.now(timezone.utc):
                await db.execute("DELETE FROM state WHERE key = ?", (key,))
                await db.commit()
                raise KeyNotFoundError(f"Key expired: {key}")

            # Check ETag for concurrency
            if options and options.concurrency == ConcurrencyMode.FIRST_WRITE:
                if options.etag and entry.etag != options.etag:
                    raise ConcurrencyError(f"ETag mismatch for key: {key}")

            return entry

    async def set(
        self,
        key: str,
        value: bytes,
        options: Optional[StateOptions] = None
    ) -> StateEntry:
        await self.initialize()
        shard = self._shard_for_key(key)
        async with self._shard_locks[shard]:
            now = self._now_iso()
            etag = self._etag(value)
            expires_at = None
            if options and options.ttl_seconds:
                expires_at = (
                    datetime.now(timezone.utc).timestamp() + options.ttl_seconds
                )
                expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()

            async with aiosqlite.connect(self._db_path) as db:
                # Check concurrency
                if options and options.concurrency == ConcurrencyMode.FIRST_WRITE:
                    cursor = await db.execute("SELECT etag FROM state WHERE key = ?", (key,))
                    existing = await cursor.fetchone()
                    if existing and existing[0] != options.etag:
                        raise ConcurrencyError(f"ETag mismatch for key: {key}")

                await db.execute("""
                    INSERT OR REPLACE INTO state
                    (key, value, etag, updated_at, expires_at, metadata, shard)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    value.hex(),
                    etag,
                    now,
                    expires_at,
                    json.dumps(options.metadata) if options and options.metadata else None,
                    shard,
                ))
                await db.commit()

            # Log event
            await self._append_log({
                "type": "upsert",
                "key": key,
                "etag": etag,
                "ts": now,
            })

            return StateEntry(
                key=key,
                value=value,
                etag=etag,
                updated_at=datetime.now(timezone.utc),
                expires_at=datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else None,
                metadata=options.metadata if options else None,
            )

    async def delete(self, key: str, options: Optional[StateOptions] = None) -> None:
        await self.initialize()
        shard = self._shard_for_key(key)
        async with self._shard_locks[shard]:
            async with aiosqlite.connect(self._db_path) as db:
                # Check concurrency
                if options and options.concurrency == ConcurrencyMode.FIRST_WRITE:
                    cursor = await db.execute("SELECT etag FROM state WHERE key = ?", (key,))
                    existing = await cursor.fetchone()
                    if existing and existing[0] != options.etag:
                        raise ConcurrencyError(f"ETag mismatch for key: {key}")

                cursor = await db.execute("DELETE FROM state WHERE key = ?", (key,))
                if cursor.rowcount == 0:
                    raise KeyNotFoundError(f"Key not found: {key}")
                await db.commit()

            # Log event
            await self._append_log({
                "type": "delete",
                "key": key,
                "ts": self._now_iso(),
            })

    async def exists(self, key: str) -> bool:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT 1 FROM state WHERE key = ?", (key,))
            return await cursor.fetchone() is not None

    async def keys(self, prefix: str = "", limit: int = 1000) -> list[str]:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            if prefix:
                cursor = await db.execute(
                    "SELECT key FROM state WHERE key LIKE ? LIMIT ?",
                    (f"{prefix}%", limit)
                )
            else:
                cursor = await db.execute(
                    "SELECT key FROM state LIMIT ?", (limit,)
                )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def watch(self, prefix: str = "") -> AsyncIterator[StateEntry]:
        """Watch for changes (long-poll implementation)."""
        await self.initialize()
        last_seq = 0
        while True:
            # Read new log entries
            async with aiofiles.open(self._log_path, "r") as f:
                lines = await f.readlines()
            for line in lines[last_seq:]:
                try:
                    event = json.loads(line)
                    if event["type"] == "upsert" and (not prefix or event["key"].startswith(prefix)):
                        async with aiosqlite.connect(self._db_path) as db:
                            cursor = await db.execute(
                                "SELECT key, value, etag, updated_at, expires_at, metadata FROM state WHERE key = ?",
                                (event["key"],)
                            )
                            row = await cursor.fetchone()
                            if row:
                                yield self._deserialize_row(row)
                    elif event["type"] == "delete" and (not prefix or event["key"].startswith(prefix)):
                        # For deletes, yield entry with empty value to signal deletion
                        yield StateEntry(
                            key=event["key"],
                            value=b"",
                            etag="",
                            updated_at=datetime.now(timezone.utc),
                        )
                except json.JSONDecodeError:
                    pass
            last_seq = len(lines)
            await asyncio.sleep(0.1)  # Long-poll interval

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Transaction]:
        tx = _FileTransaction(self)
        try:
            yield tx
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise

    async def health_check(self) -> HealthStatus:
        start = time.perf_counter()
        try:
            await self.initialize()
            # Test write/read
            test_key = f"__health_check_{uuid.uuid4().hex[:8]}"
            await self.set(test_key, b"ok")
            await self.get(test_key)
            await self.delete(test_key)
            latency = (time.perf_counter() - start) * 1000
            return HealthStatus(
                healthy=True,
                latency_ms=latency,
                backend=self.backend_name,
                details={"shards": self.shards, "db_path": str(self._db_path)}
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return HealthStatus(
                healthy=False,
                latency_ms=latency,
                backend=self.backend_name,
                details={"error": str(e)}
            )

    async def close(self) -> None:
        # No persistent connections to close for file backend
        pass


# Need aiofiles for async log writing
try:
    import aiofiles
except ImportError:
    # Fallback to sync file operations
    class aiofiles:
        @staticmethod
        async def open(path, mode="r"):
            return _AsyncFile(path, mode)

    class _AsyncFile:
        def __init__(self, path, mode):
            self._file = open(path, mode)
            self._mode = mode

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self._file.close()

        async def write(self, data):
            self._file.write(data)
            self._file.flush()

        async def read(self, n=-1):
            return self._file.read(n)

        async def readline(self):
            return self._file.readline()

        async def readlines(self):
            return self._file.readlines()