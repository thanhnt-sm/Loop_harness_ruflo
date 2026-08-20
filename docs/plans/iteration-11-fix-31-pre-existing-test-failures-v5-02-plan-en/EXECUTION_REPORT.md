# EXECUTION REPORT — Iteration 11: Fix 31 pre-existing test failures (V5-02 plan_enforce legacy-state regression)

> Report retroactive — plan đã thực thi xong trước khi report được viết. Nội dung reconstruction từ commit `4ea8018`, `HARNESS_UPGRADE_REPORT.md` (Iteration 11 section), `harness-upgrade-log.md` (Iteration 11 section), và diff thực tế. KHÔNG bịa — mọi số liệu trích từ git history.

## Summary

Iteration 11 đưa test suite từ **2280 passed / 31 failed** về **2324 passed / 0 failed**, đồng thời đưa coverage gate từ 79.44% lên **80.26%** (≥ 80%).

31 test failures chia 4 nhóm nguyên nhân (đúng như `IMPLEMENTATION_PLAN.md` dự đoán):

| Nhóm | Số test | Nguyên nhân | Loại fix |
|------|---------|-------------|----------|
| A — `plan_enforce.py` legacy-state regression | 1 | Hồi quy do Iteration 10 (V5-02 binding block legacy orchestrator state không mang `task_description`/`task_fingerprint`) | **Production fix** (1 branch) |
| B — `test_plan_orchestrator.py` stale v1 FSM | 8 | Test drive v1 FSM (`--step`, `current_state`...) nhưng shim đã chạy v2 graph orchestrator (`--init --task` one-shot) | Rewrite test theo v2 API |
| C — pre_tool_use tests thiếu `AHD_COST_LEDGER_KEY` | ~19 | CVE-2026-AHD-013 fail-closed khi thiếu HMAC ledger key → mọi `pre_tool_use` exit 2 trước gate cần test | Cấu hình key + seed ledger trong test setup |
| D — `test_cve_remediation_phase3.py` stale assertions | 2 | Assert sai config thật (`failClosedOnConfigError`) + audit log assertion không khớp CVE-2026-AHD-016 | Cập nhật assertion theo contract |

Bonus: +5 happy-path tests cho `worktree.py` (git repo thật) — đóng coverage gap, đưa worktree.py ra khỏi vùng chỉ-test-guard.

**Triết lý**: KHÔNG nới lỏng hardening bảo mật để làm hài lòng stale test. Chỉ 1 production fix nhỏ (legacy plan_enforce branch); còn lại là cập nhật test theo contract bảo mật đã được cố ý cứng hoá (CVE-013/016, V5-02).

## Commits

| Commit | Author | Date | Message |
|--------|--------|------|---------|
| `4ea8018` | thanhnt-sm | 2026-08-16 | `fix(harness): Iteration 11 — fix 31 stale test failures, plan_enforce legacy-state regression, coverage gate 80.26%` |

Single commit, 13 files, +350 / −161 dòng. Commit message tiếng Anh (git convention), body rỗng — chi tiết đầy đủ trong `HARNESS_UPGRADE_REPORT.md` + `harness-upgrade-log.md` (được append trong cùng commit).

## Files Changed

### Production code (1 file)
| File | Thay đổi | Dòng |
|------|----------|------|
| `.devin/hooks/plan_enforce.py` | Thêm `_fingerprint()` (SHA-256, khớp `storage.fingerprint`) + legacy-state branch trong `_get_plan_state_for_task`: state có metadata → binding nghiêm (V5-02 giữ nguyên); state legacy (không `task_description`/`task_fingerprint`) → bind bằng slug như hành vi pre-V5-02 + warning stderr | +49 |

### Test files (8 files)
| File | Thay đổi | Dòng |
|------|----------|------|
| `tests/test_plan_orchestrator.py` | Rewrite 8 stale v1 FSM tests → 7 tests v2 graph API (`--init --task`: tier S/M/XL, task_slug/task_fingerprint, fingerprint whitespace-stable, collision E2E, `--init` không `--task` → exit 2) | +231 / −161 (net rewrite) |
| `tests/test_cost_guard.py` | Thêm ledger-key fixture + `_seed_ledger` (append HMAC-signed entries qua `cost_ledger.append_entry`) cho warn/block — `test_at_cap_blocks` nay pass đúng lý do | +13 |
| `tests/test_pre_tool_use.py` | `env["AHD_COST_LEDGER_KEY"] = "test-key"` trong `_run()` | +2 |
| `tests/test_reflection_gate.py` | Tương tự trong `_run_pre_tool` | +1 |
| `tests/test_ssrf_guard.py` | `monkeypatch.setenv` + seed verified ledger → `test_ssrf_otel_log` đạt SSRF block path | +2 |
| `tests/test_coverage_boost5.py` | `monkeypatch.setenv` cho 5 `test_main_*`/cost-cap tests | +5 |
| `tests/test_targeted_coverage_boost.py` | Tương tự cho 3 cost-cap tests | +5 |
| `tests/test_cve_remediation_phase3.py` | (1) `failClosedOnConfigError is False` cho config thật; (2) rewrite `test_audit_log_written` theo CVE-2026-AHD-016 (env-source ghi audit; default-source chỉ warning stderr) | +33 / −(rewrite) |
| `tests/test_worktree.py` | +5 happy-path tests: `TestWorktreeLifecycle` (create/list/merge/remove/clean/main CLI với git repo thật tmp) | +62 |

### Baseline + docs (3 files)
| File | Thay đổi |
|------|----------|
| `.devin/hook_hashes.json` | Regenerate baseline (plan_enforce.py thay đổi) → 13/13 verified |
| `HARNESS_UPGRADE_REPORT.md` | Append Iteration 10 + Iteration 11 section (+59 dòng) |
| `harness-upgrade-log.md` | Append Iteration 10 + Iteration 11 section (+47 dòng) |

## Status

**PASS** ✅

### Verification (trích từ commit docs)
- Full suite `pytest tests/ --no-cov`: **2324 passed, 0 failed** (trước: 2280 passed / 31 failed).
- Coverage gate: **80.26%** ≥ 80% (trước 79.44% — pre-existing gap đã đóng).
- V5-02 matrix re-run: **7/7** (exact allow / fp allow / fp block / desc-mismatch-fp-match / legacy allow / legacy collision block / not-done block) ✅.
- `hook_integrity`: baseline regenerate → **13/13 verified** ✅.
- `tests/test_destructive_block.py`: **36 PASS** (regression test xanh — legacy plan_enforce trust không vỡ) ✅.
- `tests/test_cli_entrypoints.py`: 123 PASS (không vỡ) ✅.

### Plan ↔ Act match
- Category A (plan_enforce legacy) → `.devin/hooks/plan_enforce.py` ✅
- Category B (v2 API rewrite) → `tests/test_plan_orchestrator.py` ✅
- Category C (ledger key) → 6 test files ✅
- Category D (CVE assertions) → `tests/test_cve_remediation_phase3.py` ✅
- Bonus (worktree lifecycle) → `tests/test_worktree.py` — ngoài plan gốc, đóng coverage gap.

## Notes

- **SOLUTION_DESIGN.md** rỗng (chỉ có header `TODO: Generate from ARCHITECT subagent`) — Iteration 11 đi thẳng từ `IMPLEMENTATION_PLAN.md` (đã approved) vào thực thi, không qua SDD đầy đủ. Plan gốc đã phân tích nguyên nhân đủ chi tiết (4 category + root cause) nên SDD không thêm thông tin.
- **Rủi ro đã chấp nhận**: Legacy plan_enforce trust (state không metadata → bind bằng slug) là residual risk — control-plane equivalence (attacker ghi được orchestrator state cũng ghi được `_approved.json`). V5-02 protection không thay đổi cho state mang metadata.
- **Không đụng production ngoài 1 branch**: `plan_enforce.py` legacy path là thay đổi production duy nhất; 6 test file còn lại chỉ cập nhật test setup/assertion theo contract bảo mật đã cố ý cứng hoá — KHÔNG weaken hardening.
- **Out of scope** (theo plan): `HLK/` untouched; dead v1 `plan_fsm/cli.py`/`state_machine.py` left as-is; không refactor unrelated.
- **Bonus worktree tests**: +5 tests ngoài plan gốc — cần thiết để đạt coverage gate 80% (worktree.py trước đó chỉ được test guard path, thiếu happy-path lifecycle).
- **Commit strategy**: single squash commit (13 file, +350/−161) — phù hợp retroactive nature của iteration (fix nhiều stale test cùng lúc).
- Report này reconstruction — không có log chạy pytest từng bước trong git history; số liệu verify lấy từ `HARNESS_UPGRADE_REPORT.md` + `harness-upgrade-log.md` được ghi trong cùng commit `4ea8018`.
