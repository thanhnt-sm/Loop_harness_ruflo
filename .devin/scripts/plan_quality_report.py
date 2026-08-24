#!/usr/bin/env python3
"""plan_quality_report.py — sinh báo cáo Markdown từ scorecard.

Tách từ plan_quality_check.py (789 dòng) theo plan section 2.9.
Chỉ phụ thuộc standard library, không import module plan_quality_* khác.
Symbol _render_markdown_report được re-export bởi plan_quality_check.py.
"""
from __future__ import annotations

from pathlib import Path


def _render_markdown_report(scorecard: dict) -> str:
    """Tạo báo cáo Markdown từ scorecard."""
    lines = [
        f"# Quality Report — {Path(scorecard['plan_file']).name}",
        "",
        f"- **Checked at**: {scorecard['checked_at']}",
        f"- **Total dimensions**: {scorecard['total_dimensions']}",
        f"- **Passed**: {scorecard['passed']}",
        f"- **Failed**: {scorecard['failed']}",
        f"- **Overall**: {'PASS' if scorecard['all_pass'] else 'FAIL'}",
        "",
        "## Dimension Results",
        "",
        "| ID | Name | Status | Detail |",
        "|----|------|--------|--------|",
    ]
    for d in scorecard["dimensions"]:
        status = "PASS" if d["pass"] else "FAIL"
        detail = d["detail"].replace("|", "\\|")
        lines.append(f"| {d['id']} | {d['name']} | {status} | {detail} |")
    lines.append("")
    return "\n".join(lines)
