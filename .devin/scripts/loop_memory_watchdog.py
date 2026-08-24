#!/usr/bin/env python3
"""loop_memory_watchdog.py — Task 3.9: dead man's switch heartbeat status.

This module provides watchdog_status to report heartbeat status of running loops.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

try:
    import ahd_session
except ImportError:  # pragma: no cover
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session

STALE_THRESHOLD_SECONDS = 1800  # 30 minutes


def watchdog_status(root: Path, stale_seconds: int = STALE_THRESHOLD_SECONDS) -> dict:
    """Task 3.9: dead man's switch — báo cáo heartbeat status các loop đang chạy."""
    sessions = {}
    state_dir = ahd_session.get_config_root(root) / "session_state"
    if not state_dir.exists():
        return {"loops": 0, "stale": [], "ok": True}
    now = time.time()
    stale = []
    for f in sorted(state_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = data.get("last_heartbeat", "") or data.get("last_state_write", "")
        if not ts:
            continue
        try:
            age = now - datetime.fromisoformat(ts).timestamp()
        except (TypeError, ValueError):
            continue
        sid = f.stem
        sessions[sid] = {"age_seconds": round(age, 1), "stale": age > stale_seconds}
        if age > stale_seconds:
            stale.append(sid)
    return {"loops": len(sessions), "stale": stale, "ok": not stale}