# Implementation Plan — Workspace Governance Enforcement

## Metadata

| Trường | Giá trị |
|--------|---------|
| **Status** | Approved |
| **Risk Tier** | P2 |
| **Quality Score** | 8.5 |
| **SDD Reference** | N/A (governance hardening) |

## 1. Context Analysis

Dọn dẹp root chỉ là giải pháp tạm thời. Để không bao giờ phải định kì dọn file rác hoặc cập nhật lại tham chiếu, cần:

- Một source of truth duy nhất cho phép/không phép ghi file.
- Hook chặn runtime trước mọi write/edit/Bash tạo file sai chỗ.
- Quy tắc được cập nhật trong governance cho mọi provider.
- CI và pre-commit reject commit chứa file rác.

## 2. Implementation Phases

### 2.1 Phase 1: Single source of truth cho path zones

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T1.1 | Thêm root allowlist, junk patterns, workspace validator | `.devin/scripts/path_zones.py` | `ALLOWED_ROOT_FILES`, `ALLOWED_ROOT_PATTERNS`, `JUNK_EXTENSIONS`, `is_junk_path`, `is_allowed_root_file`, `validate_workspace_path` | Validator hoạt động đúng cho allowed/blocked/safe/junk/traversal | Low |
| T1.2 | Mở rộng safe zones cho reports và tmp | `.devin/scripts/path_zones.py` | `SAFE_ZONES` | `docs/reports/`, `.devin/reports/`, `tmp/` được coi là safe | Low |

### 2.2 Phase 2: Runtime hook guards

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T2.1 | Thêm workspace layout gate cho write/edit/notebook_edit | `.devin/hooks/pre_tool_use.py` | `_check_workspace_layout_gate` | Block root markdown/junk, allow allowed-root/safe-zone | Low |
| T2.2 | Thêm bash root-write guard | `.devin/hooks/pre_tool_use.py` | `_check_bash_workspace_layout_gate` | Block `> REPORT.md`, `touch file.tmp`, v.v. | Low |
| T2.3 | Tích hợp layout check vào plan_enforce | `.devin/hooks/plan_enforce.py` | workspace layout enforcement block | Write tool bị chặn nếu path vi phạm governance | Low |

### 2.3 Phase 3: Tests

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T3.1 | Test path_zones mới | `tests/test_path_validation.py` | `test_is_junk_path_detects_junk`, `test_is_allowed_root_file`, `test_validate_workspace_path_*` | Pass | Low |
| T3.2 | Test pre_tool_use layout gates | `tests/test_pre_tool_use.py` | workspace layout gate tests | Pass | Low |

### 2.4 Phase 4: Governance docs và cross-provider rules

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T4.1 | Cập nhật canonical governance | `.devin/rules/WORKSPACE_GOVERNANCE.md` | runtime enforcement section | Ghi rõ root allowlist và hậu quả vi phạm | Low |
| T4.2 | Cập nhật Cline file governance | `.clinerules/05-file-governance.md` | runtime enforcement note | Agent Cline biết rule | Low |
| T4.3 | Cập nhật Devin entry | `AGENTS.md` | workspace governance bullet | Agent Devin biết rule | Low |
| T4.4 | Cập nhật opencode README | `.opencode/README.md` | workspace governance section | Agent opencode biết rule | Low |

### 2.5 Phase 5: CI/CD và git hooks

| Task ID | Description | File Path | Function | Acceptance Criteria | Risk |
|---------|-------------|-----------|----------|---------------------|------|
| T5.1 | Thêm governance check vào CI | `.github/workflows/ci.yml` | Workspace governance check step | CI chạy `tools/check_governance.py` | Low |
| T5.2 | Thêm `--layout-only` flag cho pre-commit | `tools/check_governance.py` | `--layout-only` arg | Pre-commit có thể chạy layout-only | Low |
| T5.3 | Cập nhật pre-commit hook | `.githooks/pre-commit` | governance check | Block commit nếu có root markdown/junk | Low |
| T5.4 | Regenerate hook hash baseline | `.devin/hook_hashes.json`, `.devin/hook_hashes_generated.json` | `hook_integrity.py --generate` | Baseline khớp hook mới | Low |

## 3. Rollback Plan

- Revert file changed bằng `git checkout HEAD -- <file>`.
- Nếu hook gây false positive, tạm set `AHD_FAIL_OPEN=1` và sửa `path_zones.py`.

## 4. Approval Checklist

| ID | Tiêu chí | Trạng thái |
|----|----------|------------|
| D4 | Mỗi Task có acceptance criteria rõ ràng | [✓] |
| D9 | Không có thao tác phá hủy không có guard | [✓] |
