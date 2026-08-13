# Security Audit Report — Round 2 (2026-08-13)

**Phạm vi:** Full-loop red-team lần 2 sau Round 1 (đã vá R-01..R-10, commit `d2fea7f`).
**Phương pháp:** bandit SAST + review thủ công toàn bộ `.devin/scripts/`, `.devin/hooks/`, `tools/*.ps1`, `HLK/git-tools`, skills content + verify pipeline (hook_integrity, hlk-verify-integrity, hlk-git-doctor, npm audit, qa_doc_audit, pre_task_audit, abc_checklist).
**Kết quả tổng:** 5 findings mới (1 P1, 1 P2, 3 P3). Không có High từ SAST.

## 1. Trạng thái baseline (công cụ tự động — đều sạch)

| Công cụ | Kết quả |
|---|---|
| bandit (.devin/scripts + hooks + tools) | **0 High** / 2 Medium (false-positive quen thuộc: B104 `0.0.0.0` trong SSRF blocklist `pre_tool_use.py:369`, B310 urlopen đã guard https `check_updates.py:65`) / 43 Low |
| npm audit (root + HLK) | 0 vulnerabilities |
| hook_integrity --verify | PASS — 13 hooks, không tamper |
| qa_doc_audit | `hardcoded_paths: []`, không stale refs |
| pre_task_audit | không conflict session |
| hlk-git-doctor | 0 lỗi, 11 warnings (toàn bộ test fixture giả) |
| tools/*.ps1 | không Invoke-Expression, không hardcoded credential/path, https-only, Remove-Item đều guarded (temp/stage dirs cố định) |
| cross_platform.py, plan_dispatch.py, state_router.py, dag_executor.py, apply_ahd_patch.py | subprocess dùng argv (shell=False), map_path resolve+relative_to, slugify chặn traversal |

## 2. Findings mới (Round 2)

### R2-01 — [P1] `worktree.py`: path traversal qua `worker_id` + `rmtree` ngoài `.worktrees/`

**File:** `.devin/scripts/worktree.py` (cmd_create L180-219, cmd_merge L236-288, cmd_remove L291-330)

**Mô tả:**
- `worker_id` từ CLI đi thẳng vào `target = WORKTREE_DIR / prefixed_id` (L188) và `branch_name = f"agent-harness-deploy/{prefixed_id}"` (L194) — không validate.
- Đã chứng minh: `worker_id = "../../../../tmp/evil"` → `target.resolve() = /tmp/evil`, **VIOLATED** containment trong `.worktrees/`.
- `git worktree add -b <branch> <target> <base>` sẽ tạo worktree tại path ngoài `.worktrees/`; state ghi lại path này.
- `cmd_merge`/`cmd_remove` đọc path từ state rồi `git worktree remove --force <path>` + fallback `shutil.rmtree(wt_path)` (L275, L315) **không kiểm tra path nằm trong `.worktrees/`**.
- Tác động: LLM/agent (hoặc state bị tác động) có thể tạo worktree ở vị trí tuỳ ý và xoá nó — arbitrary dir create/delete ngoài workspace.

**Fix:**
1. Validate `worker_id` bằng allowlist `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$` trong `cmd_create`.
2. Guard containment `target.resolve().relative_to(WORKTREE_DIR.resolve())` trước khi create/merge/remove.
3. Trong `cmd_merge`/`cmd_remove`, chỉ `shutil.rmtree` khi `wt_path.resolve()` nằm trong `.worktrees/`, ngược lại báo lỗi + không xoá.

### R2-02 — [P2] `session_manager.py`: `_count_active_sessions` fail-open → vượt session limit

**File:** `.devin/scripts/session_manager.py` (L31-48)

**Mô tả:** `_count_active_sessions` bọc toàn bộ vòng lặp trong `except Exception: print; pass` → khi bất kỳ lỗi nội bộ nào xảy ra, hàm trả 0 → `cmd_init` thấy `active_count=0 < 3` → tạo session không kiểm soát. Fail-open trên gate giới hạn tài nguyên (đúng pattern Round 1 R-01, nhưng ở scripts chưa được xử lý).

**Fix:** áp dụng pattern `_gate_error` (fail-closed): unexpected exception → in lỗi + coi như đạt limit (return MAX_ACTIVE_SESSIONS) hoặc `sys.exit(2)`.

### R2-03 — [P3] `worktree.py`: dead/duplicate `except Exception` blocks trong `_load_state`/`_save_state`

**File:** `.devin/scripts/worktree.py` (L100-104, L110-113, L126-154)

**Mô tả:** các khối `except Exception as e: print; pass` lồng nhau, duplicated, unreachable (fallback được catch lặp 2 lần) — cùng pattern botched đã dọn ở `coverage_enforce.py` Round 1. Ngoài ra fallback ghi trực tiếp khi lock fail là fail-open (bỏ qua lock) — cần log cảnh báo rõ.

**Fix:** dọn dead code, giữ 1 fallback hợp lý + cảnh báo rõ khi bypass lock.

### R2-04 — [P3] Thiếu test cho `worktree.py` + `session_manager.py`

**Mô tả:** `test_cli_entrypoints.py` chỉ kiểm tra exit code/`--help`; chưa có test cho: validate worker_id, containment trước create/merge/remove, rmtree guard, `_count_active_sessions` fail-closed, limit session.

**Fix:** thêm `tests/test_worktree.py` + `tests/test_session_manager.py` (TDD cùng fix R2-01/R2-02/R2-03).

### R2-05 — [P3] `HLK/config/secrets.env.example` — verify yêu cầu nhưng bị `.gitignore` chặn

**File:** `.gitignore:163` (`HLK/config/secrets.*`) vs `HLK/wrappers/hlk-verify-integrity.js:29` (require `config/secrets.env.example`)

**Mô tả:** file `.example` KHÔNG tồn tại (chưa từng commit, bị ignore `secrets.*`). `hlk-verify-integrity.js` báo **1 check FAILED** → verify pipeline (kể cả `merge_updates.verify_after_update`) luôn FAIL trên clone mới. Inconsistency giữa verify contract và ignore rule.

**Fix:** thêm rule un-ignore `!HLK/config/secrets.env.example` vào `.gitignore` + tạo file template placeholder (`EXAMPLE` values, không secret thật). Lưu ý: đụng `HLK/config/` (vùng nhạy cảm) — chỉ thêm file template, không sửa policy.

## 3. Đánh giá tổng

- Attack surface còn lại sau Round 1: 2 finding thực sự về logic (R2-01 traversal, R2-02 fail-open), 3 finding về chất lượng/consistency.
- Không phát hiện shell injection (mọi subprocess argv), không credential leak mới, không hardcode path mới, hooks integrity OK.
- Cần đưa `worktree.py`/`session_manager.py` vào vòng coverage (Round 1 chỉ phủ qua `test_cli_entrypoints`).

## 4. Cách tái lập

```bash
# R2-01 proof (không tạo gì):
python -c "
from pathlib import Path
WT = Path('.worktrees'); t = WT / '../../../../tmp/evil'
print(t.resolve())  # /tmp/evil — ngoài .worktrees
"
# R2-05:
node HLK/wrappers/hlk-verify-integrity.js   # 1 check FAILED (secrets.env.example)
```

## 5. Trạng thái sau khi vá (EXECUTED 2026-08-13)

| ID | Fix | Trạng thái |
|---|---|---|
| R2-01 | `worktree.py`: `WORKER_ID_RE` allowlist (`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`), `_worktree_target()` resolve+containment trước create, `_path_within_worktrees()` guard trước merge/remove/rmtree (status `path-error`) | ✅ |
| R2-02 | `session_manager._count_active_sessions`: unexpected exception → `return MAX_ACTIVE_SESSIONS` (fail-closed) thay vì 0 | ✅ |
| R2-03 | `worktree._load_state`/`_save_state`: dọn duplicated dead except, 1 fallback duy nhất + cảnh báo rõ khi bypass lock | ✅ |
| R2-04 | `tests/test_worktree.py` (16 tests) + `tests/test_session_manager.py` (5 tests) — 21 tests mới | ✅ |
| R2-05 | `.gitignore` thêm `!HLK/config/secrets.env.example` + tạo file template placeholder → `hlk-verify-integrity` PASS | ✅ |

**Gate cuối:**
- Full pytest: **2129 passed / 0 failed**, coverage **83.82%** (≥80%).
- bandit: 0 High / 2 Medium (FP B104+B310) / 43 Low — không regression.
- `hlk-verify-integrity`: **All checks PASSED** (trước: 1 FAILED).
- `hook_integrity`: không đổi hooks nên baseline giữ nguyên.
- `git check-ignore`: `secrets.env.example` không còn bị ignore; `secrets.env` thật vẫn ignore.
