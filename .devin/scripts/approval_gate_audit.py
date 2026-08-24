#!/usr/bin/env python3
"""approval_gate_audit.py — Audit logging append-only (CVE-2026-AHD-010)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from approval_gate_constants import TELEMETRY_DIR_NAME, AUDIT_LOG_NAME


def _append_approval_audit(root: Path, record: dict) -> None:
    """Ghi approval vào telemetry append-only (JSONL).

    Append-only: luôn mở mode 'a' (không bao giờ ghi đè/truncate). Mỗi
    approval/reject ghi 1 dòng mới — không thể sửa lịch sử.
    """
    try:
        telemetry_dir = root / TELEMETRY_DIR_NAME
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        audit_path = telemetry_dir / AUDIT_LOG_NAME
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        # Audit lỗi KHÔNG chặn approval — nhưng cảnh báo rõ ràng.
        print(f"[approval_gate] WARN: không thể ghi audit log: {audit_path}", file=sys.stderr)