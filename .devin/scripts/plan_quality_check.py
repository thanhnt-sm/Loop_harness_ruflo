#!/usr/bin/env python3
"""plan_quality_check.py — entry point kiểm tra chất lượng implementation plan.

Script gộp 10(+1) dimension (DeepEval + Plan-Build-Run). Đã refactor theo
plan section 2.9: logic parse → plan_quality_parse.py, dimension checks →
plan_quality_dimensions.py, báo cáo → plan_quality_report.py, CLI →
plan_quality_cli.py. File này chỉ là entry point mỏng, re-export mọi API
cũ để đảm bảo backwards-compat (`from plan_quality_check import _parse_tasks` ...).

Dimension:
  D1  Requirement Coverage       — mọi requirement có task tương ứng?
  D2  Task Completeness          — mỗi task có file path + function + acceptance criteria?
  D3  Dependency Correctness     — DAG trong Mermaid có acyclic?
  D4  Key Links Planned          — mọi integration point từ SDD có task?
  D5  Scope Sanity               — không có orphan task (task ngoài requirement)?
  D6  Must-Haves Derivation      — acceptance criteria có falsifiable (không mơ hồ)?
  D7  Context Compliance         — plan tuân theo AGENTS.md/CLAUDE.md?
  D8  Risk Assessment            — mọi task R3+ có mitigation?
  D9  Test Coverage              — mọi requirement có test case?
  D10 Rollback Plan              — mọi task R2+ có rollback?
  D11 REQ Traceability to SDD    — mọi plan REQ ID có trong SDD đã approved?
                                  (CVE-2026-AHD-009; active khi có SDD approval)

Usage:
    python .devin/scripts/plan_quality_check.py <plan_file.md>

Exit codes:
    0 = mọi dimension PASS
    1 = có ít nhất một dimension FAIL
    2 = thiếu tham số (usage)
"""
from __future__ import annotations

import sys

# Danh sách 10 dimension với mô tả ngắn gọn (giữ nguyên API cũ)
DIMENSIONS = [
    ("D1", "Requirement Coverage", "Mọi requirement có task tương ứng"),
    ("D2", "Task Completeness", "Mỗi task có file path + function + acceptance criteria"),
    ("D3", "Dependency Correctness", "DAG trong Mermaid acyclic"),
    ("D4", "Key Links Planned", "Mọi integration point từ SDD có task"),
    ("D5", "Scope Sanity", "Không có orphan task ngoài requirement"),
    ("D6", "Must-Haves Derivation", "Acceptance criteria falsifiable, không mơ hồ"),
    ("D7", "Context Compliance", "Plan tuân theo AGENTS.md/CLAUDE.md"),
    ("D8", "Risk Assessment", "Mọi task R3+ có mitigation"),
    ("D9", "Test Coverage", "Mọi requirement có test case"),
    ("D10", "Rollback Plan", "Mọi task R2+ có rollback"),
]

# Re-export mọi symbol public từ các module con để giữ nguyên API.
from plan_quality_parse import (  # noqa: E402,F401
    VAGUE_WORDS,
    _COL_KEYS,
    _RISK_LABELS,
    _extract_file_path,
    _extract_function,
    _extract_section,
    _is_acyclic,
    _parse_coverage_table,
    _parse_mermaid_edges,
    _parse_req_ids,
    _parse_risk_table,
    _parse_task_tables,
    _parse_tasks,
    _risk_fallback,
    _risk_label_to_int,
    _strip_backticks,
)
from plan_quality_dimensions import (  # noqa: E402,F401
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
    _is_falsifiable,
    _repo_root,
    _sdd_trace_info,
    _task_slug,
)
from plan_quality_report import _render_markdown_report  # noqa: E402,F401
from plan_quality_cli import (  # noqa: E402,F401
    _ensure_utf8,
    _read_plan,
    main,
    run_checks,
)


if __name__ == "__main__":
    sys.exit(main())
