# Execution Report — Workspace Governance Enforcement

## Summary

Triển khai hệ thống chặn runtime để mọi AI agent/provider không thể tạo file rác ở root, không cần định kì dọn dẹp hay cập nhật tham chiếu.

## Files Changed

### Core enforcement source of truth
- `.devin/scripts/path_zones.py` — thêm `ALLOWED_ROOT_FILES`, `ALLOWED_ROOT_PATTERNS`, `JUNK_EXTENSIONS`, `is_junk_path`, `is_allowed_root_file`, `validate_workspace_path`, mở rộng `SAFE_ZONES` (`docs/reports/`, `.devin/reports/`, `tmp/`).

### Runtime hooks
- `.devin/hooks/pre_tool_use.py` — Gate 1.8 `_check_workspace_layout_gate` cho `write`/`edit`/`notebook_edit`; Gate 2.0a `_check_bash_workspace_layout_gate` chặn Bash redirection/touch/cp/mv tạo root `.md`/junk.
- `.devin/hooks/plan_enforce.py` — workspace layout enforcement trước khi xét plan/session.

### Tests
- `tests/test_path_validation.py` — test junk, allowed root, workspace validator.
- `tests/test_pre_tool_use.py` — test trực tiếp các gate mới.

### Governance docs
- `.devin/rules/WORKSPACE_GOVERNANCE.md` — section 3b: runtime enforcement + root allowlist.
- `.clinerules/05-file-governance.md` — runtime enforcement note.
- `AGENTS.md` — bullet runtime enforcement.
- `.opencode/README.md` — workspace governance section cho opencode agents.

### CI/CD + git hooks
- `.github/workflows/ci.yml` — thêm `Workspace governance check` step.
- `tools/check_governance.py` — thêm `--layout-only` flag.
- `.githooks/pre-commit` — chạy `tools/check_governance.py --layout-only` sau redaction check.
- `.devin/hook_hashes.json`, `.devin/hook_hashes_generated.json` — regenerated.

## Verification

- `python tools/check_governance.py`: **Sạch — 0 lỗi, 0 warning.**
- `python .devin/scripts/hook_integrity.py --verify`: OK.
- `python -m pytest tests/test_path_validation.py tests/test_pre_tool_use.py -k "path or workspace or bash or allowed_root or junk or blocked or safe or normalize or schema or coverage or dangerous or root or gate" --no-cov`: **40 passed, 4 pre-existing subprocess failures unrelated to new gates** (call-graph gate blocks bare subprocess tests).
- `python tools/gen_source_map.py`: OK.

## Residual Risks

- Pre-commit/CI chỉ kiểm tra file đã staged/committed; hook runtime mới là tuyến phòng thủ chính.
- Các provider không chạy Devin hooks (Cline, Claude Code mặc định) dựa vào rules text + CI. Cline auto-load `.clinerules/05-file-governance.md`.
- Nếu root allowlist cần thay đổi, cập nhật `.devin/scripts/path_zones.py` và đồng bộ WORKSPACE_GOVERNANCE.md.
