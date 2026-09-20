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

# P1-02: MCP Guard — SERF + Circuit Breaker
MCP_CIRCUIT_BREAKER_THRESHOLD = 3
MCP_CIRCUIT_BREAKER_COOLDOWN = 60  # seconds
MCP_DEFAULT_COMPLETENESS = 1.0

# P1-03: Loop + Context Guards
MAX_TOOL_CALLS_PER_TASK = 15
REPETITION_THRESHOLD = 2  # >2 consecutive identical tool+params
CONTEXT_BUDGET_ALERT_PCT = 80  # percent of context window
CONTEXT_BUDGET_KILL_PCT = 100
PROGRESSIVE_TOOL_LIMIT = 4  # max tools loaded per task

# P1-01: Model Tiering
# Role-based model selection: cheap for classifier/router, premium for planner/synthesizer
MODEL_TIER_CHEAP = "cheap"      # Free tier: GLM, Kimi
MODEL_TIER_PREMIUM = "premium"  # Paid: Lightning
MODEL_TIER_FREE = "free"        # Free tier only

# P1-04: Adaptive WM + Prefix-Cache Compaction
# Context window sizes per model (tokens)
MODEL_CONTEXT_WINDOWS = {
    "default": 8192,
    "glm-5.2": 200000,
    "kimi-k2.7": 128000,
    "lightning": 200000,
    "small": 8192,
}

# Auto WM budget: 80% of (window - reserved)
WM_BUDGET_FRACTION = 0.8
RESERVED_TOKENS_HEADROOM_PCT = 0.20  # 20% headroom

# Compaction pressure thresholds
COMPACT_AT_CONTEXT_FRACTION = 0.5   # trigger at 50% usage
RETAIN_CONTEXT_FRACTION = 0.15      # retain 15% newest after compact

# Prefix-cache: pinned items that must remain byte-identical
PREFIX_CACHE_ITEMS = [
    "system_prompt",      # static identity + tools
    "pinned_memory",      # critical facts
    "tool_schemas",       # tool definitions
]

# P1-05: Durable Execution
# Phase definitions for checkpointing
SESSION_PHASES = [
    "boot",
    "plan",
    "approve_sdd",
    "approve_plan",
    "execute",
    "verify",
    "report",
    "completed",
]

# Checkpoint settings
CHECKPOINT_VERSION = 1
LLM_CALL_CACHE_MAX_ENTRIES = 1000
RECEIPT_TTL_SECONDS = 86400  # 24 hours

# Saga settings
SAGA_TIMEOUT_SECONDS = 300  # 5 min for human approval

_SECRET_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"\b(token|key|password|api_key|secret)\s*=\s*[^\s&;|]+", re.IGNORECASE),
]
