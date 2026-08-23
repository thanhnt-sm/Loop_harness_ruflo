"""Cau hinh chung cho post_tool_use hook (tach tu post_tool_use.py).

Chua cac hang so, bo dem (caches) va pattern nhan dien bi mat.
"""
from __future__ import annotations

import re

HOOK_TIMEOUT_SECONDS = 4.0

MAX_ITERATIONS_WITHOUT_STATE_WRITE = 5

MIN_COMPRESSION_THRESHOLD = 3

MAX_OUTPUT_SIZE_COMPRESSION = 70

DEFAULT_COMPRESSION_THRESHOLD = 5

MAX_FAILURE_THRESHOLD = 3

_CONTEXT_FLAGS_CACHE: dict[str, dict] = {}

_CONTEXT_FLAGS_LOADED: set[str] = set()

_STATE_WRITE_COUNTER: dict[str, int] = {}

_STATE_WRITE_BATCH = 5

CONTEXT_OVERSIZE_THRESHOLD = 3000  # characters in response

CANDIDATE_MEMORY_MAX = 50

VALID_CORRECT_ACTIONS = frozenset({
    "check file permissions or use a command that does not require elevation",
    "verify the path exists before running the command",
    "recheck the command syntax and flags",
})

CANDIDATE_MEMORY_PER_HOUR = 5

CANDIDATE_MEMORY_WINDOW_SECONDS = 3600

_SECRET_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"\b(token|key|password|api_key|secret)\s*=\s*[^\s&;|]+", re.IGNORECASE),
]
