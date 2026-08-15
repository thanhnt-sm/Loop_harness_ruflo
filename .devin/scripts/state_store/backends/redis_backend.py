#!/usr/bin/env python3
"""RedisBackend — Redis-backed StateStore implementation.

Provides distributed, horizontally scalable state storage with
Redis Streams for event log and Redis JSON for key-value index.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import redis.asyncio as redis
from pydantic import BaseModel, ConfigDict

from ..interface import (
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

logger = logging.getLogger("redis_backend")


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    max_connections: int = 50
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False


class RedisBackend:
    """Redis-backed StateStore implementation.

    Uses Redis Streams for event log and Redis JSON for key-value index.
    Supports clustering, replication, and high availability.
    """

    def __init__(self, config: RedisConfig | None = None, url: str | None = None, shards: int = 10):
        self.config = config or RedisConfig()
        self.url = url
        self.shards = max(1, shards)
        self._redis: redis.Redis | None = None
        self._pool: redis.ConnectionPool | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        async with self._lock:
            if self._initialized:
                return

            if self.url:
                self._pool = redis.ConnectionPool.from_url(
                    self.url,
                    max_connections=self.config.max_connections,
                    decode_responses=False,
                )
            else:
                self._pool = redis.ConnectionPool(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    ssl=self.config.ssl,
                    max_connections=self.config.max_connections,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    decode_responses=self.config.decode_responses,
                )
            self._redis = redis.Redis(connection_pool=self._pool)
            self._initialized = True
            logger.info(f"Redis backend initialized (shards={self.shards})")

    @property
    def backend_name(self) -> str:
        return f"redis:{self.shards}shards"

    def _shard_for_key(self, key: str) -> int:
        """Consistent hashing for sharding."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) % self.shards

    def _shard_key(self, key: str) -> str:
        """Add shard prefix to key."""
        shard = self._shard_for_key(key)
        return f"shard:{shard}:{key}"

    def _lua_script_set(self) -> str:
        """Lua script for atomic set with ETag and TTL."""
        return """
        local key = KEYS[1]
        local value = ARGV[1]
        local etag = ARGV[2]
        local ttl = tonumber(ARGV[3])
        local concurrency = ARGV[4]
        local old_etag = ARGV[5]

        if concurrency == "first_write" then
            local current = redis.call("HGET", key, "etag")
            if current and current ~= "" and current ~= old_etag then
                return {err = "ETag mismatch"}
            end
        end

        local data = cjson.decode(value)
        data.etag = etag
        data.updated_at = ARGV[6]
        if ttl > 0 then
            data.expires_at = ARGV[6] + ttl
        end

        redis.call("HSET", key, "data", cjson.encode(data), "etag", etag, "updated_at", ARGV[6])
        if ttl > 0 then
            redis.call("EXPIRE", key, ttl)
        end

        return {ok = true, etag = etag}
        """

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._initialized:
            return
        if self.url:
            self._pool = redis.ConnectionPool.from_url(
                self.url,
                max_connections=50,
                decode_responses=False,
            )
        else:
            self._pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                ssl=self.config.ssl,
                max_connections=self.config.max_connections,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                decode_responses=self.config.decode_responses,
            )
        self._redis = redis.Redis(connection_pool=self._pool)
        await self._redis.ping()
        self._initialized = True
        logger.info(f"Redis backend initialized (shards={self.shards})")

    @property
    def backend_name(self) -> str:
        return f"redis:{self.shards}shards"

    def _shard_for_key(self, key: str) -> int:
        """Consistent hashing for sharding."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) % self.shards

    def _shard_key(self, key: str) -> str:
        """Add shard prefix to key."""
        shard = self._shard_for_key(key)
        return f"shard:{shard}:{key}"

    def _lua_script_set(self) -> str:
        """Lua script for atomic set with ETag and TTL."""
        return """
        local key = KEYS[1]
        local value = ARGV[1]
        local etag = ARGV[2]
        local ttl = tonumber(ARGV[3])
        local concurrency = ARGV[4]
        local old_etag = ARGV[5]

        if concurrency == "first_write" then
            local current = redis.call("HGET", key, "etag")
            if current and current ~= "" and current ~= old_etag then
                return {err = "ETag mismatch"}
            end
        end

        local data = cjson.decode(value)
        data.etag = etag
        data.updated_at = ARGV[6]
        if ttl > 0 then
            data.expires_at = ARGV[6] + ttl
        end

        redis.call("HSET", key, "data", cjson.encode(data), "etag", etag, "updated_at", ARGV[6])
        if ttl > 0 then
            redis.call("EXPIRE", key, ttl)
        end

        return {ok = true, etag = etag}
        """

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._initialized:
            return
        if self.url:
            self._pool = redis.ConnectionPool.from_url(
                self.url,
                max_connections=50,
                decode_responses=False,
            )
        else:
            self._pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                ssl=self.config.ssl,
                max_connections=self.config.max_connections,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                decode_responses=self.config.decode_responses,
            )
        self._redis = redis.Redis(connection_pool=self._pool)
        await self._redis.ping()
        self._initialized = True
        logger.info(f"Redis backend initialized (shards={self.shards})")

    @property
    def backend_name(self) -> str:
        return f"redis:{self.shards}shards"

    def _shard_for_key(self, key: str) -> int:
        """Consistent hashing for sharding."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) % self.shards

    def _shard_key(self, key: str) -> str:
        """Add shard prefix to key."""
        shard = self._shard_for_key(key)
        return f"shard:{shard}:{key}"

    async def get(self, key: str, options: StateOptions | None = None) -> StateEntry:
        key = self._shard_key(key)
        data = await self._redis.hgetall(self._shard_key(key))
        if not data:
            raise KeyNotFoundError(f"Key not found: {key}")

        # Parse stored data
        stored = json.loads(data[b"data"])
        entry = StateEntry(
            key=key,
            value=json.dumps(stored["value"]).encode() if isinstance(stored["value"], dict) else stored["value"],
            etag=stored["etag"],
            updated_at=datetime.fromisoformat(stored["updated_at"]),
            expires_at=datetime.fromisoformat(stored["expires_at"]) if stored.get("expires_at") else None,
            metadata=stored.get("metadata"),
        )

        # Check TTL
        if entry.expires_at and entry.expires_at < datetime.now(timezone.utc):
            await self.delete(key)
            raise KeyNotFoundError(f"Key expired: {key}")

        # Check ETag for concurrency
        if options and options.concurrency == "first_write":
            if options.etag and entry.etag != options.etag:
                raise ConcurrencyError(f"ETag mismatch for key: {key}")

        return entry

    async def set(
        self,
        key: str,
        value: bytes,
        options: StateOptions | None = None,
    ) -> StateEntry:
        key = self._shard_key(key)
        etag = hashlib.sha256(value).hexdigest()[:16]
        now = datetime.now(timezone.utc).isoformat()

        # Prepare data
        if isinstance(value, bytes):
            try:
                value_str = value.decode("utf-8")
                value_json = json.loads(value_str)
            except (UnicodeDecodeError, json.JSONDecodeError):
                value_json = value.hex()
        else:
            value_json = value

        data = {
            "value": value_json,
            "etag": etag,
            "updated_at": now,
            "metadata": options.metadata if options else None,
        }

        if options and options.ttl_seconds:
            data["expires_at"] = (datetime.now(timezone.utc).timestamp() + options.ttl_seconds)
            data["expires_at"] = datetime.fromtimestamp(data["expires_at"], tz=timezone.utc).isoformat()

        # Use Lua script for atomic write
        lua = self._lua_script_set()
        script = self._redis.register_script(lua)
        await script(
            keys=[self._shard_key(key)],
            args=[
                json.dumps(value_json),
                etag,
                str(options.ttl_seconds) if options and options.ttl_seconds else "0",
                "first_write" if options and options.concurrency == "first_write" else "last_write",
                options.etag if options and options.etag else "",
                datetime.now(timezone.utc).isoformat(),
            ],
        )

        entry = StateEntry(
            key=key,
            value=value,
            etag=etag,
            updated_at=datetime.now(timezone.utc),
            expires_at=datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00")) if data.get("expires_at") else None,
            metadata=options.metadata if options else None,
        )
        return entry

    async def delete(self, key: str, options: StateOptions | None = None) -> None:
        key = self._shard_key(key)
        deleted = await self._redis.delete(key)
        if deleted == 0:
            raise KeyNotFoundError(f"Key not found: {key}")

    async def exists(self, key: str) -> bool:
        key = self._shard_key(key)
        return await self._redis.exists(key) > 0

    async def keys(self, prefix: str = "", limit: int = 1000) -> list[str]:
        pattern = self._shard_key(f"{prefix}*")
        keys = []
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str.startswith("shard:"):
                    key_str = ":".join(key_str.split(":")[2:])
                keys.append(key_str)
                if len(keys) >= limit:
                    break
            if cursor == 0:
                break
        return keys

    async def watch(self, prefix: str = "") -> AsyncIterator[StateEntry]:
        """Watch for key changes (Redis keyspace notifications)."""
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe(f"__keyspace@*:{self._shard_key(prefix)}*")
        try:
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    key = message["channel"].decode().split(":", 2)[-1]
                    try:
                        entry = await self.get(key)
                        yield entry
                    except KeyNotFoundError:
                        pass
        finally:
            await pubsub.punsubscribe(f"__keyspace@*:{self._shard_key(prefix)}*")
            await pubsub.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["RedisTransaction"]:
        """Create a transaction."""
        tx = RedisTransaction(self)
        try:
            yield tx
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise


class RedisTransaction:
    """Redis transaction with optimistic locking."""

    def __init__(self, backend: RedisBackend):
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
                        etag=hashlib.sha256(v).hexdigest()[:16],
                        updated_at=datetime.now(timezone.utc),
                    )
        try:
            return await self._backend.get(key)
        except KeyNotFoundError:
            return None

    async def set(
        self,
        key: str,
        value: bytes,
        options: Optional[StateOptions] = None,
    ) -> StateEntry:
        self._ops.append(("upsert", key, value, options))
        etag = hashlib.sha256(value).hexdigest()[:16]
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

        # Execute all operations in a pipeline
        pipe = self._backend._redis.pipeline()
        for op_type, key, value, options in self._ops:
            key = self._backend._shard_key(key)
            if op_type == "upsert" and value is not None:
                etag = hashlib.sha256(value).hexdigest()[:16]
                # Check concurrency
                if options and options.concurrency == ConcurrencyMode.FIRST_WRITE:
                    existing = await self._backend._redis.hget(self._backend._shard_key(key), "etag")
                    if existing and existing != options.etag:
                        raise ConcurrencyError(f"ETag mismatch for key: {key}")

                data = {
                    "value": value.hex() if isinstance(value, bytes) else value,
                    "etag": etag,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                if options and options.ttl_seconds:
                    expires_at = datetime.now(timezone.utc).timestamp() + options.ttl_seconds
                    data["expires_at"] = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()

                await self._backend._redis.hset(
                    self._backend._shard_key(key),
                    mapping={
                        "data": json.dumps(data),
                        "etag": etag,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            elif op_type == "delete":
                await self._backend._redis.delete(self._backend._shard_key(key))
        await pipe.execute()
        self._committed = True

    async def rollback(self) -> None:
        if self._committed or self._rolled_back:
            raise TransactionError("Transaction already completed")
        self._rolled_back = True


# Factory for creating backends
class BackendFactory:
    """Factory for creating StateStore backends."""

    @staticmethod
    async def create(
        backend: str = "file",
        **kwargs
    ):
        if backend == "file":
            from .file_backend import FileBackend
            root = kwargs.get("root", Path("."))
            name = kwargs.get("name", "default")
            store = FileBackend(root, name)
        elif backend == "redis":
            config = RedisConfig(**{k: v for k, v in kwargs.items() if k in RedisConfig.__dataclass_fields__})
            store = RedisBackend(config=config)
        elif backend == "postgresql":
            from .pg_backend import PgBackend
            store = PgBackend(**kwargs)
        elif backend == "etcd":
            from .etcd_backend import EtcdBackend
            store = EtcdBackend(**kwargs)
        else:
            raise ValueError(f"Unknown backend: {backend}")

        await store.initialize()
        return store