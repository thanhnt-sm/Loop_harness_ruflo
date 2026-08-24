#!/usr/bin/env python3
"""blackboard_constants.py — Constants and patterns for blackboard.

REGION_RULES, RESOLVERS, patterns, sanitization.
"""
from __future__ import annotations

import re
from typing import Any, Callable

# Pattern allowlist cho region: chỉ chữ số, chữ cái, dấu chấm, gạch dưới, gạch ngang.
_REGION_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")


def _sanitize_region(region: str) -> str:
    """Làm sạch region để chống path traversal qua tên file.

    Bước 1: Thay path separator ('/', '\\') bằng '_'.
    Bước 2: Loại bỏ ký tự ngoài allowlist.
    Bước 3: Sụp đổ nhiều dấu '_' liên tiếp và cắt đầu/cuối.
    Bước 4: Nếu chứa '..' hoặc không khớp pattern -> 'invalid'.
    """
    if not region:
        return "invalid"
    safe = region.replace("/", "_").replace("\\", "_")
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    safe = re.sub(r"_+", "_", safe).strip("_-. ")
    if not safe or ".." in safe or not _REGION_PATTERN.match(safe):
        return "invalid"
    return safe


# Định nghĩa region + quy tắc giải quyết xung đột.
REGION_RULES: dict[str, str] = {
    "hypotheses": "append_only",
    "evidence": "single_writer",
    "decisions": "crdt_union",
    "state": "versioned",
    "findings": "append_only",
    "metrics": "last_write_wins",
}

# Type cho resolver functions
ResolverFunc = Callable[[str, str, str, dict, Any], tuple[bool, str, dict]]

# Forward references - sẽ được gán sau khi import resolver functions
RESOLVERS: dict[str, ResolverFunc] = {}

# Export public API
__all__ = [
    "REGION_RULES",
    "RESOLVERS",
    "_sanitize_region",
    "_REGION_PATTERN",
]