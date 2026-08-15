"""StateStore package — Pluggable state persistence interface."""
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
    validate_state_store,
)
from .file_backend import FileBackend
from .backends import RedisBackend, RedisConfig, RedisTransaction

__all__ = [
    "ConcurrencyError",
    "ConcurrencyMode",
    "ConsistencyLevel",
    "HealthStatus",
    "KeyNotFoundError",
    "StateEntry",
    "StateOptions",
    "StateStore",
    "Transaction",
    "TransactionError",
    "validate_state_store",
    "FileBackend",
    "RedisBackend",
    "RedisConfig",
    "RedisTransaction",
]