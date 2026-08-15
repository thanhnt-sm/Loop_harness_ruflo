#!/usr/bin/env python3
"""StateStore — Abstract interface for pluggable state persistence.

Dapr-inspired model: applications talk to StateStore ABC,
backends (File/Redis/PostgreSQL/etcd) implement the interface.
"""
from __future__ import annotations

import abc
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional, Protocol
from typing import runtime_checkable

from pydantic import BaseModel, ConfigDict


class ConsistencyLevel(str, Enum):
    """Consistency guarantee for read/write operations."""
    STRONG = "strong"       # Linearizable: read sees latest write
    EVENTUAL = "eventual"   # May see stale data, lower latency


class ConcurrencyMode(str, Enum):
    """Optimistic concurrency control mode."""
    FIRST_WRITE = "first_write"   # Fail if ETag mismatch
    LAST_WRITE = "last_write"     # Overwrite (no ETag check)


@dataclass(frozen=True, slots=True)
class StateOptions:
    """Options for state operations."""
    consistency: ConsistencyLevel = ConsistencyLevel.STRONG
    concurrency: ConcurrencyMode = ConcurrencyMode.FIRST_WRITE
    ttl_seconds: Optional[int] = None
    etag: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class StateEntry:
    """A single key-value state entry with metadata."""
    key: str
    value: bytes
    etag: str
    updated_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class TransactionOperation:
    """Single operation within a transaction."""
    operation: str  # "upsert" | "delete"
    key: str
    value: Optional[bytes] = None
    options: Optional[StateOptions] = None


class HealthStatus(BaseModel):
    """Health check result for a state store."""
    model_config = ConfigDict(frozen=True)

    healthy: bool
    latency_ms: float
    backend: str
    details: dict[str, Any] = {}


class StateStoreError(Exception):
    """Base exception for state store errors."""
    pass


class KeyNotFoundError(StateStoreError):
    """Raised when key does not exist."""
    pass


class ConcurrencyError(StateStoreError):
    """Raised on optimistic concurrency failure (ETag mismatch)."""
    pass


class TransactionError(StateStoreError):
    """Raised when transaction fails."""
    pass


class StateStore(Protocol):
    """Abstract interface for state persistence.

    All implementations must provide:
    - CRUD operations with consistency/concurrency control
    - Watch/subscription for key changes
    - Transactional multi-key operations
    - Health checking
    """

    @property
    def backend_name(self) -> str:
        """Human-readable backend identifier (e.g., 'file', 'redis', 'postgresql')."""
        ...

    async def get(self, key: str, options: Optional[StateOptions] = None) -> StateEntry:
        """Get a single key.

        Args:
            key: State key
            options: Consistency, concurrency, TTL options

        Returns:
            StateEntry with value and metadata

        Raises:
            KeyNotFoundError: If key doesn't exist (unless concurrency=LAST_WRITE)
            ConcurrencyError: If ETag mismatch with FIRST_WRITE
        """
        ...

    async def set(
        self,
        key: str,
        value: bytes,
        options: Optional[StateOptions] = None
    ) -> StateEntry:
        """Set a key (upsert).

        Args:
            key: State key
            value: Serialized value (bytes)
            options: Consistency, concurrency, TTL options

        Returns:
            StateEntry with new ETag and timestamp

        Raises:
            ConcurrencyError: If ETag mismatch with FIRST_WRITE
        """
        ...

    async def delete(self, key: str, options: Optional[StateOptions] = None) -> None:
        """Delete a key.

        Args:
            key: State key
            options: Concurrency options (ETag)

        Raises:
            KeyNotFoundError: If key doesn't exist
            ConcurrencyError: If ETag mismatch
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists (lightweight)."""
        ...

    async def keys(self, prefix: str = "", limit: int = 1000) -> list[str]:
        """List keys with optional prefix."""
        ...

    def watch(self, prefix: str = "") -> AsyncIterator[StateEntry]:
        """Subscribe to key changes (long-poll or push).

        Yields StateEntry for each change matching prefix.
        """
        ...

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["Transaction"]:
        """Begin a transaction for atomic multi-key operations.

        Usage:
            async with store.transaction() as tx:
                await tx.set("key1", b"value1")
                await tx.set("key2", b"value2")
                await tx.commit()

        Yields:
            Transaction object with set/delete/commit/rollback
        """
        ...

    async def health_check(self) -> HealthStatus:
        """Check store health: connectivity, latency, errors."""
        ...

    async def close(self) -> None:
        """Close connections, cleanup resources."""
        ...


class Transaction(Protocol):
    """Transactional context for atomic multi-key operations."""

    async def get(self, key: str) -> Optional[StateEntry]:
        """Get within transaction (sees uncommitted writes)."""
        ...

    async def set(
        self,
        key: str,
        value: bytes,
        options: Optional[StateOptions] = None
    ) -> StateEntry:
        """Set within transaction."""
        ...

    async def delete(self, key: str) -> None:
        """Delete within transaction."""
        ...

    async def commit(self) -> None:
        """Commit all operations atomically.

        Raises:
            TransactionError: If commit fails (concurrency, constraint)
        """
        ...

    async def rollback(self) -> None:
        """Rollback all operations."""
        ...


# Runtime validation helpers
def validate_state_store(store: Any) -> StateStore:
    """Validate that an object implements StateStore protocol."""
    required_methods = [
        "get", "set", "delete", "exists", "keys",
        "watch", "transaction", "health_check", "close"
    ]
    for method in required_methods:
        if not hasattr(store, method):
            raise TypeError(f"StateStore missing method: {method}")
    return store