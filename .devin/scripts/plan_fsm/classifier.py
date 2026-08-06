#!/usr/bin/env python3
"""Phân loại task tier dựa trên mô tả."""
from __future__ import annotations


def classify_tier(task_description: str) -> str:
    """Phân loại task tier S/M/L/XL dựa trên description.

    S: <50 chars, 1 file, no verification, no destructive op
    M: 1-3 files, simple logic, 30min-2h
    L: Multiple files, needs research, 2h+
    XL: Architecture change, security-critical, multi-system
    Default: M (fail-closed).
    """
    if not task_description:
        return "M"
    desc = task_description.lower().strip()
    s_indicators = [
        len(desc) < 50,
        any(kw in desc for kw in ["typo", "rename", "update date", "fix spelling"]),
        any(kw in desc for kw in ["s-tier", "trivial", "one line", "1 line"]),
    ]
    xl_indicators = [
        any(kw in desc for kw in ["architecture", "refactor", "migrate", "rewrite"]),
        any(kw in desc for kw in ["security", "auth", "encryption", "compliance"]),
        any(kw in desc for kw in ["multi-system", "cross-service", "distributed"]),
        len(desc) > 300,
    ]
    l_indicators = [
        any(kw in desc for kw in ["multiple files", "several files", "multiple modules", "integration", "database"]),
        any(kw in desc for kw in ["performance", "cache", "migration", "api design"]),
        len(desc) > 150,
    ]
    if sum(xl_indicators) >= 2:
        return "XL"
    if sum(l_indicators) >= 2:
        return "L"
    if sum(s_indicators) >= 2:
        return "S"
    return "M"
