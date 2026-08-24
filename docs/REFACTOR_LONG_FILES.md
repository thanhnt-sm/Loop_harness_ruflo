# Prompt: Refactor 13 File Quá Dài (>500 Lines)

## Context (Bối cảnh)

Hiện tại workspace có **13 file quá dài** (>500 lines) cần refactor:

| File | Lines | Vị trí |
|------|-------|--------|
| blackboard.py | 530 | .devin/scripts/ |
| checkpoint.py | 605 | .devin/scripts/ |
| ahd_session.py | 667 | .devin/hooks/ |
| harness_upgrade_loop.py | 631 | .devin/scripts/ |
| loop_memory_sync.py | 694 | .devin/scripts/ |
| plan_dispatch.py | 613 | .devin/scripts/ |
| apply_ahd_patch.py | 770 | .devin/scripts/ |
| approval_gate.py | 702 | .devin/scripts/ |
| plan_quality_check.py | 789 | .devin/scripts/ |
| post_tool_use.py | 882 | .devin/hooks/ |
| schema_gate.py | 824 | .devin/hooks/ |
| dag_executor.py | 917 | .devin/scripts/ |
| pre_tool_use.py | 1443 | .devin/hooks/ |

## Rootcause Analysis (Nguyên nhân gốc rễ)

### Tại sao file quá dài là vấn đề?

1. **Maintainability giảm**: File quá dài khó đọc, khó hiểu, khó sửa
2. **Testing khó khăn**: Test coverage thấp, khó test từng phần
3. **Review mệt mỏi**: Code review tốn thời gian, dễ bỏ sót bug
4. **Risk bug cao**: Change一处可能导致多处break (thay đổi一处 có thể làm hỏng nhiều chỗ)
5. **Collaboration kém**: Multiple developers khó merge changes, dễ conflict
6. **Performance suy giảm**: IDE indexing chậm, load file lâu
7. **Code duplication**: Logic trùng lặp khó detect, khó refactor

### Tại sao phải refactor NOW?

- **Security tests pass**: 0 CRITICAL/HIGH → có thể refactor an toàn
- **Test suite stable**: 2913 passed → baseline tốt để verify không regression
- **Architecture clear**: Hooks + scripts separation rõ ràng → dễ tách modules
- **Governance enforced**: Pre-commit gates chặn lỗi → refactor có safety net

## Goals (Mục tiêu)

### Mục tiêu chính

1. **Reduce line count**: Mỗi file <500 lines (theo CLAUDE.md rule)
2. **Maintain API**: Không thay đổi public API, không break downstream consumers
3. **Preserve functionality**: Tất cả logic giữ nguyên, test suite pass
4. **Improve maintainability**: Code dễ đọc, dễ test, dễ review
5. **Follow governance**: Tuân thủ WORKSPACE_GOVERNANCE.md (file vào đúng nơi)

### Mục tiêu phụ

1. **Extract modules**: Tách logic liên quan ra module riêng
2. **Compress comments**: Nén verbose comments, giữ context quan trọng
3. **Merge similar functions**: Gộp functions trùng lặp
4. **Group related code**: Organize code theo functional groups
5. **Add docstrings**: Public functions có docstring (nếu thiếu)

## Strategy (Chiến lược Refactor)

### Chiến lược tổng thể

```
From: Monolithic files (>500 lines)
To: Modular architecture (<500 lines per file)
```

### Chiến lược cụ thể cho từng loại file

#### 1. Hooks (.devin/hooks/)

**Loại file**: `ahd_session.py`, `post_tool_use.py`, `pre_tool_use.py`, `schema_gate.py`

**Chiến lược**:
- Tách constants → `_constants.py`
- Tách utility functions → `_utils.py`
- Tách core logic → `_core.py`
- Giữ main file → entry point + orchestration

**Ví dụ**:
```
pre_tool_use.py (1443 lines)
├── pre_tool_use_constants.py   # Constants, thresholds
├── pre_tool_use_gates.py       # Gate logic (gate 1-8)
├── pre_tool_use_rules.py       # Rule enforcement
└── pre_tool_use.py             # Main entry + orchestration
```

#### 2. Scripts (.devin/scripts/)

**Loại file**: `blackboard.py`, `checkpoint.py`, `dag_executor.py`, v.v.

**Chiến lược**:
- Tách CLI logic → `_cli.py`
- Tách core functions → `_core.py`
- Tách data models → use existing `data_models.py`
- Tách validation → `_validation.py`

**Ví dụ**:
```
dag_executor.py (917 lines)
├── dag_executor_core.py        # Core execution logic
├── dag_executor_cli.py         # CLI interface
├── dag_executor_validation.py   # Schema validation
└── dag_executor.py             # Main entry
```

### Chiến lược nén comments

1. **Remove verbose Vietnamese comments**: Giữ chỉ context quan trọng
2. **Compress multi-line comments**: Tóm tắt thành 1-2 lines
3. **Keep security comments**: CVE, security context phải giữ
4. **Remove redundancy**: Lặp lại context → delete

**Ví dụ**:
```python
# Before
# Đây là function để xử lý việc đọc file JSON từ đĩa cứng.
# Nó sử dụng read_text() để đọc file và try/except để xử lý lỗi.
# Nếu file không tồn tại, nó trả về default value.
# Nếu file có lỗi JSON decode, nó cũng trả về default value.

# After
# Load JSON safely (return default on error)
```

### Chiến lược tách modules

1. **Identify cohesive groups**: Group functions theo functionality
2. **Extract constants**: Constants → top-level file
3. **Extract utilities**: Helper functions → _utils.py
4. **Extract core logic**: Main logic → _core.py
5. **Keep imports clean**: Avoid circular imports

## Constraints (Ràng buộc)

### Ràng buộc MANDATORY (BẮT BUỘC)

1. **NO API CHANGES**: Public functions giữ nguyên signature
2. **NO BEHAVIOR CHANGES**: Logic giữ nguyên, test suite pass
3. **NO HOOK INTEGRITY BREAK**: hook_hashes.json phải regenerate sau khi refactor
4. **NO GOVERNANCE VIOLATION**: File mới vào đúng thư mục (WORKSPACE_GOVERNANCE.md)
5. **NO JUNK FILES**: Không tạo scratch files, file tạm
6. **NO CIRCULAR IMPORTS**: Module tách phải avoid circular dependencies
7. **NO TEST REGRESSION**: Run full test suite sau mỗi file refactor

### Ràng buộc RECOMMENDED (Khuyến nghị)

1. **Preserve comments**: Security context (CVE, security patterns) phải giữ
2. **Add docstrings**: Public functions mới phải có docstring
3. **Type hints**: New functions có type hints (nếu phù hợp)
4. **Error handling**: I/O operations có try/except
5. **Naming consistency**: Follow existing naming conventions

## Execution Plan (Kế hoạch thực hiện)

### Phase 1: Preparation (Chuẩn bị)

1. **Baseline test suite**: Run `pytest tests/` → save baseline (2913 passed)
2. **Hook integrity baseline**: Save `hook_hashes.json` current state
3. **Create backup**: Backup toàn bộ 13 files trước refactor
4. **Read all files**: Đọc chi tiết từng file để hiểu logic

### Phase 2: Refactor từng file (Sequential)

**Order**: Từ dễ → khó (small → large)

1. **blackboard.py** (530 lines) → test → verify
2. **checkpoint.py** (605 lines) → test → verify
3. **ahd_session.py** (667 lines) → test → verify
4. **harness_upgrade_loop.py** (631 lines) → test → verify
5. **loop_memory_sync.py** (694 lines) → test → verify
6. **plan_dispatch.py** (613 lines) → test → verify
7. **apply_ahd_patch.py** (770 lines) → test → verify
8. **approval_gate.py** (702 lines) → test → verify
9. **plan_quality_check.py** (789 lines) → test → verify
10. **post_tool_use.py** (882 lines) → test → verify
11. **schema_gate.py** (824 lines) → test → verify
12. **dag_executor.py** (917 lines) → test → verify
13. **pre_tool_use.py** (1443 lines) → test → verify

### Phase 3: Verification sau mỗi file

**Sau khi refactor MỖI file**:

1. **Run specific tests**: `pytest tests/test_<file>.py` (nếu có)
2. **Run integration tests**: `pytest tests/ -k <file>` (nếu có)
3. **Run hook integrity**: `python .devin/scripts/hook_integrity.py --verify`
4. **Run governance check**: `python tools/check_governance.py`
5. **Commit file**: Git commit với message rõ ràng

### Phase 4: Final Verification

1. **Run full test suite**: `pytest tests/` → phải pass (2913 passed)
2. **Regenerate hook_hashes**: `python .devin/scripts/hook_integrity.py --generate`
3. **Run CI simulation**: Chạy các steps trong `.github/workflows/ci.yml`
4. **Generate report**: Update `docs/reports/SELF_CHECK_2026-08-23.md`

## Output Format (Định dạng output)

### Commit message pattern

```
refactor: split <file> into modules (reduce <old> → <new> lines)

- Extract constants → <file>_constants.py
- Extract core logic → <file>_core.py
- Extract CLI/entry → <file>_cli.py
- Compress verbose comments (keep security context)
- Maintain API, no behavior changes
- Test suite: <x> passed

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>
```

### Final report format

Update `docs/reports/SELF_CHECK_2026-08-23.md`:

```markdown
## Refactor Long Files Progress

| File | Before | After | Status |
|------|--------|-------|--------|
| blackboard.py | 530 | 320 | ✅ Done |
| checkpoint.py | 605 | 380 | ✅ Done |
| ... | ... | ... | ... |

**Total**: 13/13 files refactored
**Test suite**: 2913 passed (no regression)
**Hook integrity**: ✅ All hooks verified
```

## Risk Mitigation (Giảm thiểu rủi ro)

### Rủi ro 1: API changes → break downstream

**Mitigation**:
- Trước refactor: Generate API baseline (inspect public functions)
- Sau refactor: Run `pytest tests/` → verify no API break
- Nếu downstream consumers: Run integration tests

### Rủi ro 2: Hook integrity break

**Mitigation**:
- Trước refactor: Save `hook_hashes.json` baseline
- Sau refactor: Regenerate `hook_hashes.json`
- Compare diff → verify only intended changes

### Rủi ro 3: Circular imports

**Mitigation**:
- Tách modules theo dependency direction (no circular deps)
- Use lazy imports (import inside function) nếu cần
- Run `python -m py_compile` → verify no import errors

### Rủi ro 4: Test regression

**Mitigation**:
- Run test suite sau MỖI file refactor
- Nếu test fail: IMMEDIATELY revert file → investigate
- Use git bisect nếu cần debug

## Success Criteria (Tiêu chí thành công)

### Minimum success (Tối thiểu)

- ✅ All 13 files <500 lines
- ✅ Test suite pass (2913 passed)
- ✅ Hook integrity verified
- ✅ No governance violations

### Ideal success (Lý tưởng)

- ✅ All 13 files <400 lines (20% buffer)
- ✅ Code coverage tăng (nếu có)
- ✅ New modules well-documented
- ✅ CI pass all gates

## Tools & Commands (Công cụ & lệnh)

### Essential commands

```bash
# Baseline test suite
pytest tests/ -q --tb=short --override-ini="addopts="

# Hook integrity verify
python .devin/scripts/hook_integrity.py --verify

# Hook integrity generate
python .devin/scripts/hook_integrity.py --generate

# Governance check
python tools/check_governance.py

# Count lines in file
python -c "import sys; from pathlib import Path; print(len(Path('file.py').read_text(encoding='utf-8').splitlines()))"

# Check circular imports
python -m py_compile file.py
```

### Git workflow

```bash
# Backup before refactor
git checkout -b refactor-long-files

# Commit each file refactor
git add <file> <new_modules>
git commit -m "refactor: split <file> into modules..."

# After all done
git checkout main
git merge refactor-long-files
```

## Escalation Criteria (Khi nào cần human intervention)

### Must escalate (BẮT BUỘC)

1. **Test fail > 10**: >10 tests fail sau refactor → investigate with human
2. **Hook integrity break**: hook_hashes.json verify fail → revert → escalate
3. **Circular import**: Module tách gây circular import → redesign → escalate
4. **API change detected**: Public function signature change → revert → escalate

### Should escalate (Nên escalate)

1. **Test fail 1-10**: 1-10 tests fail → try fix, nếu không được → escalate
2. **File still >500 lines**: Refactor xong vẫn >500 lines → need more aggressive split → escalate
3. **Logic bug**: Behavior change detected → revert → escalate
4. **Governance violation**: File ở sai thư mục → fix → escalate

## Prompt cho AI Executor

Sử dụng prompt này cho:

- **lightning-executor**: Nhanh, parallel refactor (sau khi plan approved)
- **glm-executor**: Free tier, reasoning cao (phân tích logic trước refactor)
- **kimi-executor**: Open-source, cost-efficient (refactor từng file)

### Command pattern

```bash
# Sử dụng lightning (fastest)
/lightning "Refactor blackboard.py (<500 lines) theo docs/prompts/REFACTOR_LONG_FILES.md"

# Sử dụng glm (free, reasoning)
/glm "Refactor checkpoint.py (<500 lines) theo docs/prompts/REFACTOR_LONG_FILES.md"

# Sử dụng kimi (open-source)
/kimi "Refactor ahd_session.py (<500 lines) theo docs/prompts/REFACTOR_LONG_FILES.md"
```

---

**Lưu ý**: Đây là prompt KỸ THUẬT, không phải task trực tiếp. AI cần đọc prompt → plan → execute → verify. Human cần approve plan trước khi execute.
