#!/usr/bin/env python3
"""Utility functions for ahd_session.

Provides:
- now_utc: Current UTC time in ISO format
"""
from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> str:
    """Return current UTC time as ISO format string with seconds precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")