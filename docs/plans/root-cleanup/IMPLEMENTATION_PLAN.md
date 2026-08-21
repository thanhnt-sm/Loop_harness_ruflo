# Implementation Plan — Root Markdown Cleanup

## Metadata

| Trường | Giá trị |
|--------|---------|
| **Status** | Approved |
| **Risk Tier** | P2 |
| **Quality Score** | 8.0 |
| **SDD Reference** | N/A (cleanup task) |

## 1. Context Analysis

Root workspace chứa nhiều file `.md` là báo cáo/plan/map từ các iteration trước, gây rối và vi phạm quy tắc "không để file work/report ở root". Cần dọn dẹp, cập nhật tham chiếu, và chuyển output path của các script sang `docs/reports/` để tránh tái phạm.

## 2. Implementation Phases

### 2.1 Phase 1: Xóa file work/report/map đã lỗi thời

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T1.1 | Xóa các file report/plan/map ở root | `ARCHITECTURAL_ATTACK_REPORT.md`, `COST_DASHBOARD.md`, `EXECUTION_RED_TEAM_REPORT.md`, `EXECUTION_ROOT_CAUSE_ANALYSIS.md`, `HARNESS_UPGRADE_REPORT.md`, `ITERATION_4_COMPONENT_MAP.md`, `MIGRATION_COMPONENT_MAP.md`, `MIGRATION_IMPLEMENTATION_PLAN.md`, `MIGRATION_RED_TEAM_REPORT.md`, `MIGRATION_ROOT_CAUSE_ANALYSIS.md`, `MIGRATION_SOLUTION_MATRIX.md`, `SECURITY_AUDIT_REPORT.md`, `SECURITY_REMEDIATION_PLAN.md`, `STRUCTURAL_COMPONENT_MAP.md`, `STRUCTURAL_IMPLEMENTATION_PLAN.md`, `STRUCTURAL_RED_TEAM_REPORT.md`, `STRUCTURAL_SOLUTION_MATRIX.md`, `UPDATES_REPORT.md`, `harness-upgrade-log.md` | N/A | Các file không còn tồn tại ở root; `git status` hiển thị `D` | Low |

### 2.2 Phase 2: Cập nhật source map, orientation, governance

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T2.1 | Loại bỏ root entries đã xóa | `tools/source_map_data.py` | `ROOT_NOTES` | Không còn mô tả các file đã xóa | Low |
| T2.2 | Cập nhật load-on-demand guide | `.clinerules/03-load-on-demand.md` | N/A | Tham chiếu đúng `docs/reports/` | Low |
| T2.3 | Cập nhật orientation | `.clinerules/01-orientation.md` | N/A | Bỏ component map đã xóa | Low |
| T2.4 | Cập nhật root file list | `.devin/rules/WORKSPACE_GOVERNANCE.md` | N/A | Chỉ còn entry files hiện tại | Low |
| T2.5 | Refresh source map | `.clinerules/00-source-map.md` | N/A | `tools/gen_source_map.py` chạy thành công | Low |

### 2.3 Phase 3: Cập nhật script output và audit exclude list

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T3.1 | Chuyển output `check_updates.py` sang `docs/reports/` | `.devin/scripts/check_updates.py` | `DEFAULT_OUTPUT` | Path mặc định là `docs/reports/UPDATES_REPORT.md` | Low |
| T3.2 | Chuyển output `cost_dashboard.py` sang `docs/reports/` | `.devin/scripts/cost_dashboard.py` | `_load_upgrade_log`, `main` | Đọc/ghi từ `docs/reports/` | Low |
| T3.3 | Chuyển output `harness_upgrade_loop.py` sang `docs/reports/` | `.devin/scripts/harness_upgrade_loop.py` | `LOG_FILE` | Path log là `docs/reports/harness-upgrade-log.md` | Low |
| T3.4 | Dọn EXCLUDE_GLOB audit | `.devin/scripts/qa_doc_audit.py` | `EXCLUDE_GLOB` | Không còn exclude các file đã xóa | Low |

### 2.4 Phase 4: Cập nhật skill references

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T4.1 | Cập nhật `update_from_repos` skill | `.devin/skills/update_from_repos/SKILL.md` | N/A | `docs/reports/UPDATES_REPORT.md` | Low |
| T4.2 | Cập nhật `harness-upgrade` skill và details | `.devin/skills/harness-upgrade/SKILL.md`, `.devin/skills/harness-upgrade/detail/*.md` | N/A | `docs/reports/HARNESS_UPGRADE_REPORT.md`, `docs/reports/harness-upgrade-log.md` | Low |
| T4.3 | Cập nhật opencode wrappers | `.opencode/command/harness-upgrade.md`, `.opencode/skills/harness-upgrade/SKILL.md` | N/A | Cùng path mới | Low |

## 3. Rollback Plan

- Nếu cần khôi phục file đã xóa: `git checkout HEAD -- <filename>`.
- Các thay đổi script là path-only, có thể revert bằng `git checkout` hoặc `git revert`.

## 4. Approval Checklist

| ID | Tiêu chí | Trạng thái |
|----|----------|------------|
| D4 | Mỗi Task có acceptance criteria rõ ràng | [✓] |
| D9 | Không có thao tác phá hủy không có guard | [✓] đã xin xác nhận user trước khi xóa |
