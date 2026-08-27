# Documentation Index — Bản đồ Tài liệu Workspace

> Master index cho toàn bộ documentation trong workspace AHD.
> Dùng để tìm nhanh tài liệu theo chủ đề, theo loại, hoặc theo trạng thái.

---

## Quick Navigation

| Tôi cần... | Document |
|------------|----------|
| **Tổng quan hệ thống** | [README.md](../README.md) |
| **Quy tắc agent** | [AGENTS.md](../AGENTS.md) |
| **Hướng dẫn sử dụng** | [docs/USAGE_GUIDE.md](USAGE_GUIDE.md) |
| **Kiến trúc chi tiết** | [docs/AGENTS_full_reference.md](AGENTS_full_reference.md) |
| **Plan orchestrator** | [docs/PLAN_ORCHESTRATOR_GUIDE.md](PLAN_ORCHESTRATOR_GUIDE.md) |
| **Loop engineering** | [docs/CONTINUOUS_LOOP_GUIDE.md](CONTINUOUS_LOOP_GUIDE.md) |
| **3-Phase proposal** | [docs/PROPOSAL.md](PROPOSAL.md) |
| **Plan redesign** | [docs/PROPOSAL_PLAN_PHASE_REDESIGN.md](PROPOSAL_PLAN_PHASE_REDESIGN.md) |
| **Hard stops/redlines** | [docs/REDLINES_full.md](REDLINES_full.md) |
| **Red team audit** | [docs/REDTEAM_AUDIT.md](REDTEAM_AUDIT.md) |
| **Refactoring guide** | [docs/REFACTOR_LONG_FILES.md](REFACTOR_LONG_FILES.md) |
| **Constraint ledger** | [docs/CONSTRAINT_LEDGER.md](CONSTRAINT_LEDGER.md) |
| **Reference repos** | [REPOS.md](../REPOS.md) |
| **Security policy** | [SECURITY.md](../SECURITY.md) |

---

## Documents by Category

### Core Entry Files (Root)

| File | Lines | Purpose |
|------|-------|---------|
| [AGENTS.md](../AGENTS.md) | 245 | Agent harness rules + governance — entry point chính |
| [CLAUDE.md](../CLAUDE.md) | 45 | Claude Code entry file |
| [REPOS.md](../REPOS.md) | 193 | Master reference list (50+ repos) |
| [SECURITY.md](../SECURITY.md) | — | Security policy |
| [README.md](../README.md) | — | System overview + quick start |

### Guides (How-to)

| File | Lines | Purpose |
|------|-------|---------|
| [USAGE_GUIDE.md](USAGE_GUIDE.md) | 411 | Hướng dẫn đầy đủ cách sử dụng — skills, agents, flows |
| [CONTINUOUS_LOOP_GUIDE.md](CONTINUOUS_LOOP_GUIDE.md) | 397 | Loop engineering — 3 chế độ, GoalSpec, anti-patterns |
| [BOOT_PROTOCOL_full.md](BOOT_PROTOCOL_full.md) | 180 | Startup sequence 17 bước, 3-tier lazy-load |

### Technical Reference

| File | Lines | Purpose |
|------|-------|---------|
| [AGENTS_full_reference.md](AGENTS_full_reference.md) | 464 | Kiến trúc AHD layer — Canon, Orchestrator, Skills, Hooks |
| [PLAN_ORCHESTRATOR_GUIDE.md](PLAN_ORCHESTRATOR_GUIDE.md) | 759 | Plan orchestrator FSM — 13 states, CLI, troubleshooting |
| [REDLINES_full.md](REDLINES_full.md) | 294 | 18 hard stops + mechanical enforcement + L0-L4 permissions |
| [CONSTRAINT_LEDGER.md](CONSTRAINT_LEDGER.md) | 234 | Bảng ràng buộc cho test remediation |
| [REFACTOR_LONG_FILES.md](REFACTOR_LONG_FILES.md) | 361 | Prompt refactor 13 file quá dài (>500 lines) |

### Proposals

| File | Lines | Status | Purpose |
|------|-------|--------|---------|
| [PROPOSAL.md](PROPOSAL.md) | 1068 | DRAFT | Đề xuất kiến trúc 3-Phase |
| [PROPOSAL_PLAN_PHASE_REDESIGN.md](PROPOSAL_PLAN_PHASE_REDESIGN.md) | 568 | DRAFT | Tái kiến trúc Phase Plan |

### Audit & Quality

| File | Lines | Purpose |
|------|-------|---------|
| [REDTEAM_AUDIT.md](REDTEAM_AUDIT.md) | 723 | Red team audit — 70+ findings (score 6.5/10) |

### Research (docs/research/)

| File | Lines | Purpose |
|------|-------|---------|
| [AI_AGENT_HARNESS_LANDSCAPE_2026.md](research/AI_AGENT_HARNESS_LANDSCAPE_2026.md) | — | Competitive landscape — 8+ frameworks |
| [AI_CODING_PAIN_POINTS_2026.md](research/AI_CODING_PAIN_POINTS_2026.md) | — | 11 pain points AI coding |
| [AI_AGENT_SOLUTIONS_2026.md](research/AI_AGENT_SOLUTIONS_2026.md) | — | 15 solutions với AHD mapping |
| [orchestration_patterns.md](research/orchestration_patterns.md) | 175 | 18 actionable patterns orchestration |
| [planning_best_practices.md](research/planning_best_practices.md) | 896 | Planning phase best practices |
| [qc_enforcement_mechanisms.md](research/qc_enforcement_mechanisms.md) | 872 | QC & execution enforcement |

### Prompts (docs/prompts/)

| File | Purpose |
|------|---------|
| [TECH_TRENDS_RESEARCH_PROMPT.md](prompts/TECH_TRENDS_RESEARCH_PROMPT.md) | Prompt template nghiên cứu định kỳ |

### Templates (docs/templates/)

| File | Lines | Purpose |
|------|-------|---------|
| [PLAN_TEMPLATE.md](templates/PLAN_TEMPLATE.md) | 215 | Mẫu Implementation Plan |
| [SDD_TEMPLATE.md](templates/SDD_TEMPLATE.md) | 283 | Mẫu Solution Design Document |

### Reports (docs/reports/) — 14 files

| File | Date | Purpose |
|------|------|---------|
| [COMPREHENSIVE_QUALITY_AUDIT_2026-08-11.md](reports/COMPREHENSIVE_QUALITY_AUDIT_2026-08-11.md) | 2026-08-11 | Audit toàn diện 7 trục, 19 findings |
| [SECURITY_HARDENING_2026-08-13.md](reports/SECURITY_HARDENING_2026-08-13.md) | 2026-08-13 | Vá lỗ hổng an ninh |
| [SECURITY_HARDENING_ROUND2_2026-08-13.md](reports/SECURITY_HARDENING_ROUND2_2026-08-13.md) | 2026-08-13 | Red-team lần 2 |
| [CLINE_CLI_MAX_PERFORMANCE_2026-08-18.md](reports/CLINE_CLI_MAX_PERFORMANCE_2026-08-18.md) | 2026-08-18 | Knowledge base Cline CLI |
| [HARNESS_ISSUES_2026-08-22.md](reports/HARNESS_ISSUES_2026-08-22.md) | 2026-08-22 | 18 MEDIUM + 120 LOW issues |
| [HARNESS_ISSUES_2026-08-23.md](reports/HARNESS_ISSUES_2026-08-23.md) | 2026-08-23 | 3 MEDIUM + 115 LOW |
| [SELF_CHECK_2026-08-23.md](reports/SELF_CHECK_2026-08-23.md) | 2026-08-23 | Self-check toàn diện |
| [UPDATES_REPORT.md](reports/UPDATES_REPORT.md) | 2026-08-22 | Upstream update tracking |
| [HARNESS_ISSUES_2026-08-24.md](reports/HARNESS_ISSUES_2026-08-24.md) | 2026-08-24 | 0 CRITICAL/HIGH, 115 LOW |
| [COVERAGE_GAP_REPORT_2026-08-24.md](reports/COVERAGE_GAP_REPORT_2026-08-24.md) | 2026-08-24 | Coverage gap analysis |
| [COMPETITIVE_ANALYSIS_TEST_REMEDIATION_2026-08-24.md](reports/COMPETITIVE_ANALYSIS_TEST_REMEDIATION_2026-08-24.md) | 2026-08-24 | Phân tích 6 approaches remediation |
| [CI_FIX_HANDOFF_2026-08-24.md](reports/CI_FIX_HANDOFF_2026-08-24.md) | 2026-08-24 | Session handoff fix CI |
| [NEXT_SESSION_EXECUTE_PROMPT.md](reports/NEXT_SESSION_EXECUTE_PROMPT.md) | — | Prompt chuyển giao remediation |
| [COST_DASHBOARD.md](reports/COST_DASHBOARD.md) | 2026-08-24 | Cost tracking dashboard |

### Plans (docs/plans/) — 36 feature directories

| Status | Count | Description |
|--------|-------|-------------|
| **Complete** (SDD + Plan + Exec Report) | 8 | harness-hardening, security-hardening, v5-01-*, v5-04-*, hlk-auto-review, iteration-11, refactor-*, post-tool-use-refactor |
| **Partial** (some artifacts) | 12 | root-cleanup, source-audit-fix, workspace-governance, refactor-*, various test dirs |
| **SDD only** | 12 | add-jwt-auth, test dirs, continuous-self-improvement, etc. |
| **Empty** | 2 | step-task, test-task |

---

## Document Statistics

| Category | Count | Total Lines |
|----------|-------|-------------|
| Core entry files | 5 | ~522 |
| Guides | 3 | ~988 |
| Technical reference | 5 | ~2,152 |
| Proposals | 2 | ~1,636 |
| Audit | 1 | ~723 |
| Research | 6 | ~2,500+ |
| Prompts | 1 | — |
| Templates | 2 | ~498 |
| Reports | 14 | ~2,000+ |
| Plans | 36 dirs | N/A |
| **Total docs/*.md** | **~40** | **~11,000+** |

---

## Maintaining This Index

Khi thêm document mới:
1. Thêm vào category tương ứng trong index này
2. Cập nhật Quick Navigation nếu là tài liệu quan trọng
3. Cập nhật statistics
4. Chạy `python tools/check_governance.py` để verify file đúng vị trí

---

*Cập nhật: 2026-08-27*
