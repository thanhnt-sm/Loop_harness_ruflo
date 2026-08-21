# Execution Report — Root Markdown Cleanup

## Summary

Dọn dẹp các file `.md` rác ở root workspace theo yêu cầu user. Giữ lại `AGENTS.md`, `CLAUDE.md`, `SECURITY.md`, `REPOS.md` tại root. Xóa 19 file work/report/plan/map đã lỗi thời. Cập nhật source map, governance, skill references, và output path của các script để tránh tái tạo file ở root.

## Files Changed

### Deleted

- `ARCHITECTURAL_ATTACK_REPORT.md`
- `COST_DASHBOARD.md`
- `EXECUTION_RED_TEAM_REPORT.md`
- `EXECUTION_ROOT_CAUSE_ANALYSIS.md`
- `HARNESS_UPGRADE_REPORT.md`
- `ITERATION_4_COMPONENT_MAP.md`
- `MIGRATION_COMPONENT_MAP.md`
- `MIGRATION_IMPLEMENTATION_PLAN.md`
- `MIGRATION_RED_TEAM_REPORT.md`
- `MIGRATION_ROOT_CAUSE_ANALYSIS.md`
- `MIGRATION_SOLUTION_MATRIX.md`
- `SECURITY_AUDIT_REPORT.md`
- `SECURITY_REMEDIATION_PLAN.md`
- `STRUCTURAL_COMPONENT_MAP.md`
- `STRUCTURAL_IMPLEMENTATION_PLAN.md`
- `STRUCTURAL_RED_TEAM_REPORT.md`
- `STRUCTURAL_SOLUTION_MATRIX.md`
- `UPDATES_REPORT.md`
- `harness-upgrade-log.md`

### Modified

- `.clinerules/00-source-map.md` (regenerated)
- `.clinerules/01-orientation.md`
- `.clinerules/03-load-on-demand.md`
- `.devin/rules/WORKSPACE_GOVERNANCE.md`
- `.devin/scripts/check_updates.py`
- `.devin/scripts/cost_dashboard.py`
- `.devin/scripts/harness_upgrade_loop.py`
- `.devin/scripts/qa_doc_audit.py`
- `.devin/skills/harness-upgrade/SKILL.md`
- `.devin/skills/harness-upgrade/detail/learn.md`
- `.devin/skills/harness-upgrade/detail/redteam-v5.md`
- `.devin/skills/harness-upgrade/detail/redteam.md`
- `.devin/skills/harness-upgrade/detail/review.md`
- `.devin/skills/harness-upgrade/detail/verify.md`
- `.devin/skills/harness-upgrade/detail/v5-redteam-prompt.md`
- `.devin/skills/update_from_repos/SKILL.md`
- `.opencode/command/harness-upgrade.md`
- `.opencode/skills/harness-upgrade/SKILL.md`
- `tools/source_map_data.py`

## Verification

- `python tools/gen_source_map.py` chạy thành công.
- `python tools/check_governance.py` với `PYTHONIOENCODING=utf-8`: `errors=0`, còn warning do plan chưa có report (đã tạo report này).
- `git status --short` xác nhận các file đã xóa/marker `D`.

## Residual Risks

- Các script đã được chuyển output sang `docs/reports/`; nếu chạy lại với `--output` tùy chỉnh vẫn có thể ghi root — cần user tuân thủ governance.
- `SECURITY.md` và `REPOS.md` vẫn ở root theo lựa chọn của user.
