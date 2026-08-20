# EXECUTION REPORT — V5-04 Telemetry-Outage Fail-Closed Deterministic Test

## Summary

Plan **V5-04 [LOW]** bổ sung test deterministic cho invariant V5 §17 "telemetry outage → fail-closed, ghi BLOCKED" — đảm bảo khi OTel (OpenTelemetry) outage thì audit event **không bị mất âm thầm**, mà được ghi vào fallback `events.jsonl` và lỗi được surface qua stderr.

Đây là task **test-only** (U-TEL-1): không sửa production code, chỉ thêm 1 file test `tests/test_telemetry_outage.py` dùng monkeypatch in-process (không subprocess flaky) để khóa các invariant:

1. OTel outage (`_emit_otel_span`→False) → event vẫn ghi fallback `events.jsonl`, field đúng (`tool_name`/`status`/`input.hash`), exit 0.
2. OTel available (`_emit_otel_span`→True) → không ghi fallback (event đi span).
3. Fallback write outage (`events.jsonl` là directory → `open()` fail) → không crash, stderr có warning "error writing telemetry log", passthrough giữ nguyên.
4. Wrapper transparent: `tool_output` dict → stdout in lại JSON; `exit_code` 5 → exit 5.
5. Invalid stdin (garbage JSON) → exit 0, không crash.
6. `_determine_status` matrix (blocked/error/success) + `_hash_input` không leak raw input.

## Commits

| Commit | Ngày | Tác giả | Mô tả |
|--------|------|---------|-------|
| `9c71650` | 2026-08-16 05:49:23 UTC | thanhnt-sm | feat(harness): Iteration 10 — V5-02 slug-collision fingerprint binding, V5-04 telemetry-outage test, V5-01 ext revocation persistence |

> Lưu ý: commit `9c71650` là commit gộp cho 3 plan (V5-02, V5-04, V5-01). Phần V5-04 chỉ tương ứng với file `tests/test_telemetry_outage.py` (125 dòng thêm). Các file khác trong commit thuộc V5-02 (`state_machine_v2.py`, `storage.py`) và V5-01 (`registry.py`, `test_registry_lifecycle.py`).

## Files Changed

| File | Loại | Thay đổi | Thuộc plan |
|------|------|----------|------------|
| `tests/test_telemetry_outage.py` | NEW | +125 dòng | V5-04 (báo cáo này) |

Không sửa production code (`otel_instrument.py` / hooks / HLK) — đúng guardrail "test-only, 1 file mới duy nhất".

## Status

| Mục | Kết quả |
|-----|---------|
| pytest `tests/test_telemetry_outage.py` | **7/7 PASS** (0.91s) |
| Red-team (ATK-1 → ATK-6 + smoke) | **PASS** — không issue chặn merge |
| Sửa production code | Không (test-only) |
| pytest cũ vỡ thêm | Không (không touch file khác) |
| hook_integrity | Không đổi (không touch hook) |

### Chi tiết test cases (7/7 PASS)
- `test_otel_outage_records_fallback_event` — PASS
- `test_otel_available_skips_fallback` — PASS
- `test_fallback_write_failure_is_surfaced_not_swallowed` — PASS
- `test_passthrough_output_and_exit_code_preserved` — PASS
- `test_invalid_stdin_does_not_crash` — PASS
- `test_determine_status_matrix` — PASS
- `test_hash_input_never_leaks_raw` — PASS

## Notes

- **Retroactive report**: plan đã được thực thi từ trước (commit `9c71650` ngày 2026-08-16), báo cáo này được viết lại sau (retroactive) dựa trên git history + artifacts có sẵn (`IMPLEMENTATION_PLAN.md`, `SOLUTION_DESIGN.md`, `redteam-report.md`).
- **Coverage gate**: pytest chạy ra exit code 1 do `fail-under=80` (coverage toàn repo 28.87%) — đây là cấu hình coverage toàn cục của `pytest.ini`, **không phải test failure**. Bản thân 7 test của V5-04 đều PASS.
- **Verify matrix** trong `IMPLEMENTATION_PLAN.md` khớp 100% với test cases thực tế (6 case trong plan + 1 case `_hash_input` tách rời = 7 test).
- **DoD** đạt hết: pytest PASS, không sửa production code, không vỡ test cũ, hook_integrity không đổi.
- **Red-team** (`redteam-report.md`): 6 attack + 1 end-to-end smoke (`__main__` path) đều PASS. Kết luận RED-TEAM PASS — không issue chặn merge.
