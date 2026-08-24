#!/usr/bin/env python3
"""approval_gate_summary.py — Parse plan/SDD và quality report summaries."""

from __future__ import annotations

import re
from pathlib import Path


def _parse_plan_summary(plan_path: Path) -> dict:
    """Trích tóm tắt plan từ Markdown file — dùng cho interactive mode."""
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    summary = {
        "feature": "",
        "complexity": "",
        "risk_tier": "",
        "files_count": 0,
        "requirements_count": 0,
        "tasks_count": 0,
    }
    # Trích Metadata table
    # Risk Tier — match cả [FILL IN: R2] và giá trị thực R2/P0/P1/P2/P3
    m = re.search(r"Risk Tier.*?\|\s*`?\*?\*?\s*(?:\[FILL IN:\s*)?([A-Za-z]\d+)\s*\]?\*?`?\s*\|", text, re.IGNORECASE)
    if m:
        summary["risk_tier"] = m.group(1).strip()
    elif "[FILL IN:" in text and "Risk Tier" in text:
        m2 = re.search(r"Risk Tier.*?\[FILL IN:\s*(.*?)\]", text, re.IGNORECASE)
        if m2:
            summary["risk_tier"] = m2.group(1).strip()
    # Đếm task IDs (T1.1, T1.2, T2.1, v.v.)
    task_ids = re.findall(r"\bT\d+\.\d+\b", text)
    summary["tasks_count"] = len(set(task_ids))
    # Đếm REQ IDs
    req_ids = re.findall(r"\bREQ-\d+\b", text)
    summary["requirements_count"] = len(set(req_ids))
    # Đếm file paths (đường dẫn có / hoặc \)
    file_paths = re.findall(r"`([^`]*[/\\][^`]*)`", text)
    summary["files_count"] = len(set(file_paths))
    # Feature = task_slug nếu file nằm trong docs/plans/<task_slug>/; fallback = tên file
    parts = plan_path.parts
    if "docs" in parts and "plans" in parts:
        try:
            idx = parts.index("plans")
            if idx + 1 < len(parts):
                summary["feature"] = parts[idx + 1].replace("-", " ")
                return summary
        except ValueError:
            pass
    summary["feature"] = plan_path.stem.replace("IMPLEMENTATION_PLAN_", "").replace("SOLUTION_DESIGN_", "").replace("_", " ")
    return summary


def _parse_quality_report(qr_path: Path) -> dict:
    """Trích tóm tắt quality report từ Markdown file."""
    if not qr_path or not qr_path.exists():
        return {}
    try:
        text = qr_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    result = {"scorecard": "", "passed": 0, "failed": 0, "all_pass": False}
    # Overall PASS/FAIL
    if "**Overall**: **PASS**" in text or "**Overall**: PASS" in text:
        result["all_pass"] = True
    # Đếm PASS/FAIL trong table
    passes = len(re.findall(r"\|\s*PASS\s*\|", text))
    fails = len(re.findall(r"\|\s*FAIL\s*\|", text))
    result["passed"] = passes
    result["failed"] = fails
    result["scorecard"] = f"{passes} PASS, {fails} FAIL"
    return result