#!/usr/bin/env python3
"""plan_quality_cli.py — entry logic (CLI main, read plan, run checks).

Tách từ plan_quality_check.py (789 dòng) theo plan section 2.9.
Phụ thuộc: plan_quality_parse (parse), plan_quality_dimensions (checks),
plan_quality_report (render). Các symbol main, _read_plan, run_checks,
_ensure_utf8 được re-export bởi plan_quality_check.py.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from plan_quality_parse import _parse_req_ids, _parse_tasks
from plan_quality_dimensions import (
    _approved_sdd_state,
    _check_d1,
    _check_d10,
    _check_d11,
    _check_d2,
    _check_d3,
    _check_d4,
    _check_d5,
    _check_d6,
    _check_d7,
    _check_d8,
    _check_d9,
    _sdd_trace_info,
)
from plan_quality_report import _render_markdown_report


# Bước 0: Ép stdout/stderr dùng UTF-8 khi chạy CLI (tránh lỗi cp1258 trên Windows console)
def _ensure_utf8() -> None:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def _read_plan(plan_path: Path) -> str:
    """Đọc nội dung plan file, ném lỗi nếu file không tồn tại hoặc rỗng."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Không tìm thấy plan file: {plan_path}")
    text = plan_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Plan file rỗng (không có nội dung)")
    return text


def run_checks(plan_path: Path) -> dict:
    """Chạy toàn bộ 10 dimension check (+ D11 khi có SDD approval), trả scorecard dict."""
    text = _read_plan(plan_path)
    req_ids = _parse_req_ids(text)
    tasks = _parse_tasks(text)

    results = [
        _check_d1(req_ids, tasks),
        _check_d2(tasks),
        _check_d3(text),
        _check_d4(text, tasks),
        _check_d5(req_ids, tasks),
        _check_d6(tasks),
        _check_d7(text),
        _check_d8(tasks),
        _check_d9(text, req_ids),
        _check_d10(tasks),
    ]

    # CVE-2026-AHD-009: D11 — REQ traceability với SDD approved.
    # Chỉ active khi có SDD approval state (legacy flow không có SDD vẫn 10D).
    if _approved_sdd_state(plan_path) is not None:
        sdd_info = _sdd_trace_info(plan_path)
        results.append(_check_d11(req_ids, sdd_info))
        results[-1]["detail"] += f" (sdd: {sdd_info.get('sdd_path', '?')})"

    passed = sum(1 for r in results if r["pass"])
    scorecard = {
        "plan_file": str(plan_path),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total_dimensions": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "dimensions": results,
        "all_pass": passed == len(results),
    }
    return scorecard


def main() -> int:
    """Entry point CLI. Trả exit code 0 nếu PASS, 1 nếu FAIL."""
    _ensure_utf8()
    if len(sys.argv) < 2:
        print("Usage: python plan_quality_check.py <plan_file.md>", file=sys.stderr)
        return 2
    plan_path = Path(sys.argv[1]).resolve()
    try:
        scorecard = run_checks(plan_path)
    except (FileNotFoundError, ValueError) as e:
        # Edge case: file thiếu hoặc rỗng
        print(json.dumps({"error": str(e), "plan_file": str(plan_path)}, ensure_ascii=False, indent=2))
        return 1

    # In JSON scorecard ra stdout
    print(json.dumps(scorecard, ensure_ascii=False, indent=2))

    # Ghi báo cáo Markdown vào docs/plans/QUALITY_REPORT_<plan_name>.md
    repo_root = plan_path.parent
    # Tìm repo root: đi lên cho tới khi thấy .devin hoặc .git
    for parent in [plan_path.parent, *plan_path.parents]:
        if (parent / ".devin").exists() or (parent / ".git").exists():
            repo_root = parent
            break
    report_dir = repo_root / "docs" / "plans"
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"QUALITY_REPORT_{plan_path.stem}.md"
        report_path.write_text(_render_markdown_report(scorecard), encoding="utf-8")
        print(f"\n[REPORT] {report_path}", file=sys.stderr)
    except OSError as e:
        # Edge case: không ghi được report (chỉ cảnh báo, không fail)
        print(f"[WARN] Không ghi được report: {e}", file=sys.stderr)

    return 0 if scorecard["all_pass"] else 1
