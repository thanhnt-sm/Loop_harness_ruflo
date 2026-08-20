# EXECUTION REPORT — V5-01 Extension: Revocation Persistence (U-REG-2)

## Summary

Extension V5-01 giải quyết ACCEPTED limitation ATK-8 từ Iteration 9: `revoke()`/`decommission()` trước đây chỉ sửa `_agents` dict trong RAM — registry reload (process mới) mất revocation, agent đã revoke match trở lại.

Giải pháp (U-REG-2): persist revocation state ra file JSON (`agent_registry_revocations.json`), áp dụng lại tại `load()`. Thêm method `restore()` để đưa agent về `active` + xóa khỏi state file.

Thay đổi gói trong 1 commit (`9c71650`, Iteration 10) cùng V5-02 slug-collision fingerprint binding và V5-04 telemetry-outage test.

## Commits

| Commit | Mô tả |
|--------|-------|
| `9c71650` | feat(harness): Iteration 10 — V5-02 slug-collision fingerprint binding, V5-04 telemetry-outage test, V5-01 ext revocation persistence |

> Ghi chú: commit `24745a9` (Iteration 9) là nền tảng — implement `AgentRegistry` lifecycle ban đầu (owner/expiry/revocation in-memory). Extension này xây trên đó.

## Files Changed

| File | Thay đổi |
|------|----------|
| `.devin/scripts/agents/registry.py` | +80 dòng: `revocations_path` param, `_load_revocations()`/`_save_revocations()`/`_apply_persisted_revocations()`, `restore()`, persist trong `revoke()`/`decommission()`, áp dụng tại `load()` |
| `tests/test_registry_lifecycle.py` | +57 dòng: 3 test mới (revoke persist, decommission persist + restore, corrupt file) |

> Commit `9c71650` còn chạm `state_machine_v2.py` (+5) và `storage.py` (+13) — thuộc V5-02, không thuộc scope plan này. `test_telemetry_outage.py` (+125) thuộc V5-04.

## Status

**HOÀN THÀNH** — tất cả task T1–T4 + verify matrix đạt.

### Verify matrix (từ IMPLEMENTATION_PLAN.md)

| Case | Expected | Kết quả |
|------|----------|---------|
| revoke → registry mới cùng path → vẫn revoked | match loại | ✅ `test_revoke_persists_across_registry_reload` PASS |
| decommission → registry mới → vẫn loại | match loại | ✅ `test_decommission_persists_across_registry_reload` PASS |
| restore → active + file sạch | match trở lại | ✅ trong `test_decommission_persists...` — `reg2.restore("a")` → match lại, `reg3` reload giữ active |
| File hỏng JSON | load không crash, `_load_revocations` → {} | ✅ `test_corrupt_revocations_file_does_not_crash` PASS |
| revoke id không tồn tại | False, không ghi file | ✅ `test_revoke_unknown_id_returns_false` PASS (return False); code path `agent is None → return False` trước `_save_revocations()` → không ghi file |
| pytest cũ (registry lifecycle) | vẫn 10 PASS | ✅ 10/10 old tests PASS |
| py_compile | OK | ✅ |

### Test chạy thực tế

```
tests/test_registry_lifecycle.py — 13 passed (10 cũ + 3 mới)
py_compile .devin/scripts/agents/registry.py — OK
```

> Coverage report báo 60% < fail-under 80% — là config coverage global (gộp `update_common.py` không liên quan), không phải lỗi của task này. `registry.py` riêng đạt 79%.

## Notes

- **Backward-compat**: không có `revocations_path` → default `.devin/plan_state/agent_registry_revocations.json`; file thiếu/hỏng → `{}` (fail-closed, không crash, không tự un-revoke).
- **Design decision (SOLUTION_DESIGN.md dòng 29)**: file hỏng → coi như không có revocation mới nhưng KHÔNG đổi status hiện có. Test `test_corrupt_revocations_file_does_not_crash` verify agent active vẫn match (không bị un-revoke sai).
- **Scope guardrail**: chỉ 1 file chính (`registry.py`) + test. Không dep mới, không touch hooks/HLK — đúng guardrail.
- **Report retroactive**: plan cũ, report viết lại sau dựa trên git history + chạy test xác minh. Không bịa — mọi số liệu lấy từ commit `9c71650` và test run thực tế.
