#!/usr/bin/env python3
"""approval_gate_constants.py — Constants và định nghĩa trạng thái cho approval gate."""

from __future__ import annotations

import sys

# Bước 0: Ép stdout/stderr dùng UTF-8 khi chạy CLI (tránh lỗi cp1258 trên Windows console)
def _ensure_utf8() -> None:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


# Các trạng thái hợp lệ
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CHANGES_REQUESTED = "changes_requested"

VALID_STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_CHANGES_REQUESTED)


# Artifact types
ARTIFACT_PLAN = "plan"
ARTIFACT_SD = "sd"

VALID_ARTIFACTS = (ARTIFACT_PLAN, ARTIFACT_SD)


# Exit codes
EXIT_APPROVED = 0
EXIT_PENDING_OR_REJECTED = 1
EXIT_USAGE_ERROR = 2


# Default paths
STATE_DIR_NAME = ".devin/plan_state"
TELEMETRY_DIR_NAME = ".devin/telemetry"
ARTIFACTS_DIR_NAME = ".devin/artifacts"
AUDIT_LOG_NAME = "approvals.jsonl"
HLK_CONFIG_PATH = "HLK/config/hlk.config.json"

# Signature config env var
REVIEWER_KEYS_ENV = "AHD_REVIEWER_KEYS"

# Crypto availability flag (set by crypto module)
CRYPTO_AVAILABLE = False

# Chunk size for large file hashing (CVE-2026-AHD-010)
HASH_CHUNK_SIZE = 65536