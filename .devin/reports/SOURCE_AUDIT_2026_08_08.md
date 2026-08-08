# Báo cáo rà soát toàn bộ source — AHD Loop Harness

> Ngày rà soát: 2026-08-08
> Mô hình: Agent Harness Deploy (AHD) — khai thác, giám sát và điều phối agent.
> Người thực hiện: Devin CLI audit

---

## 1. Tóm tắt để ra quyết định

Project này là **Agent Harness Deploy (AHD)** — một lớp điều phối và bảo vệ cho Devin CLI, gồm hooks (cổng bảo mật), scripts (công cụ runtime), canon (quy tắc), skills và tests.

**Kết quả test suite:**
- Tổng số test: 2029
- **Pass: 2011**
- **Fail: 15**
- **Skip: 3**
- **Coverage: 90.17%** (vượt ngưỡng 80%)

**Nhận xét nhanh:**
- Hệ thống bảo mật cơ bản khá vững: chặn `rm -rf`, force-push, SSRF, encoding bypass, secret leak.
- Phần lớn source code có comment tiếng Việt, cấu trúc rõ ràng.
- **15 test fail tập trung ở module `plan_fsm`** do thiết kế trạng thái `BRAINSTORM` mới không khớp với test cũ.
- Có một số vấn đề về `.gitignore`, runtime artifacts, và lỗi `except Exception` quá rộng.

**Quyết định cần làm:**
1. Có muốn tôi sửa 15 test `plan_fsm` failed không? (cần chọn giữa cập nhật test theo code mới hoặc sửa code theo test cũ)
2. Có muốn dọn dẹp `.gitignore` để bỏ qua `__pycache__`, `.worktrees/`, `.devin/telemetry/` không?
3. Có muốn tôi refactor dần các khối `except Exception` rộng thành exception cụ thể hơn không?

---

## 2. Phạm vi rà soát

| Thành phần | Mô tả |
|------------|-------|
| `.devin/hooks/` | 14 hook bảo mật/giám sát: pre_tool_use, post_tool_use, schema_gate, coverage_enforce, plan_enforce, drift_detect, v.v. |
| `.devin/scripts/` | ~50 script runtime: plan_orchestrator, plan_fsm, approval_gate, blackboard, checkpoint, event_bus, worktree, v.v. |
| `.devin/canon/` | 17 protocol/canonical rule files |
| `.devin/skills/` | 26 skill definitions và templates |
| `tests/` | 2029 test cases |
| `tools/` | 15 PowerShell/Python utility tools |
| `pyproject.toml`, `pytest.ini`, `.coveragerc`, `.gitignore` | Cấu hình build/test/coverage |

---

## 3. Kết quả chạy thử nghiệm

```text
2029 tests collected
15 failed, 2011 passed, 3 skipped in 104.24s
Coverage: 90.17% (required 80%)
```

Các test fail đều thuộc về `plan_fsm`:
- `tests/test_plan_fsm.py`: 8 fail
- `tests/test_plan_orchestrator.py`: 7 fail

**Nguyên nhân chung:**
- Test kỳ vọng sau `cmd_init` với M-tier, state là `ANALYZE` và action là `dispatch_scouts`.
- Code hiện tại trong `state_machine.py` set state thành `BRAINSTORM` và trả về action `brainstorm`.
- Đây là xung đột giữa thiết kế mới (thêm bước BRAINSTORM đa góc nhìn theo AGENTS.md) với test cũ chưa được cập nhật.

Ví dụ lỗi:
```text
AssertionError: assert 'BRAINSTORM' == 'ANALYZE'
AssertionError: assert 'brainstorm' == 'dispatch_scouts'
```

---

## 4. Phát hiện rủi ro và vấn đề

### 4.1. Bảo mật (Security)

| # | Vấn đề | Mức độ | Vị trí | Ghi chú |
|---|--------|--------|--------|---------|
| S1 | `except Exception` bắt quá rộng | Medium | Toàn bộ source (~205 lần) | Có thể che giấu lỗi nghiêm trọng, khó debug |
| S2 | `json.loads` từ stdin/file không validate schema | Medium | Hầu hết hook/script | Input độc hại có thể gây crash hoặc behavior bất ngờ |
| S3 | `subprocess.run(["git", ...])` dùng list nên an toàn | Low | `ahd_session.py`, `worktree.py`, `cross_platform.py` | Không dùng `shell=True`, hạn chế injection |
| S4 | `shutil.rmtree` trong `worktree.py` | Low | `cmd_merge`, `cmd_remove` | Chỉ xóa worktree do script tạo, có kiểm tra state |
| S5 | `mcp_config.json` chứa đường dẫn tuyệt đối Windows | Low | `.devin/mcp_config.json` | Không portable giữa máy, có thể cần env var |
| S6 | `__pycache__` không bị `.gitignore` trong `.devin/scripts/` | Medium | `.gitignore` dòng 239-240 | Pattern `!.devin/scripts/**` ghi đè `__pycache__/` |

**Đánh giá bảo mật tổng thể:** Tốt. Các hook `pre_tool_use.py`, `schema_gate.py` có nhiều lớp phòng thủ (dangerous command, SSRF, encoding bypass, secret redaction, path traversal, blocked zones). Tuy nhiên cần giảm thiểu `except Exception` rộng.

### 4.2. Chất lượng code (Code Quality)

| # | Vấn đề | Mức độ | Ví trí | Ghi chú |
|---|--------|--------|--------|---------|
| Q1 | 15 test fail tập trung `plan_fsm` | High | `tests/test_plan_fsm.py`, `tests/test_plan_orchestrator.py` | Cần sửa test hoặc code |
| Q2 | `sys.path.insert` nhiều nơi | Medium | Hầu hết scripts/hooks | Dẫn đến import phức tạp, khó maintain |
| Q3 | `print()` thay vì logging | Low | CLI scripts | Chấp nhận vì đây là CLI tool |
| Q4 | `ruff` chưa được cài đặt | Low | `pyproject.toml` cấu hình ruff nhưng không có package | CI có thể bị lỗi nếu chạy ruff |
| Q5 | `mypy` chưa chạy | Low | `pyproject.toml` cấu hình mypy | Chưa verify type coverage |

### 4.3. Cấu hình và Git

| # | Vấn đề | Mức độ | Vị trí | Ghi chú |
|---|--------|--------|--------|---------|
| G1 | `.gitignore` cho phép `__pycache__` trong `.devin/scripts/` | High | `.gitignore` dòng 239-240 | Cần thêm `!.devin/scripts/**/__pycache__/` hoặc bỏ negate |
| G2 | `.worktrees/` không có trong `.gitignore` | Medium | `.gitignore` | Thư mục untracked do tests tạo |
| G3 | `.devin/telemetry/` đã ignore nhưng file vẫn tracked | Medium | `baseline.json`, `drift_state.json` | File được commit trước khi ignore, cần `git rm --cached` |
| G4 | `.devin/hook_hashes.json` thay đổi timestamp mỗi lần chạy | Medium | `.devin/hook_hashes.json` | Nên ignore hoặc tách timestamp riêng |
| G5 | `drift_state.json` chứa dữ liệu test lạ | Low | `.devin/telemetry/drift_state.json` | `recent_files` có chuỗi "A" rất dài, có thể do test artifact |

### 4.4. Kiến trúc

- **Hooks pipeline:** `pre_tool_use` -> tool execute -> `post_tool_use` -> `schema_gate`/`coverage_enforce` -> `drift_detect`/`self_heal`/`otel_instrument`. Pipeline rõ ràng, có timeout và fail-closed.
- **Plan FSM:** Thêm state `BRAINSTORM` giữa `CLASSIFY` và `ANALYZE`, nhưng chưa đồng bộ với tests.
- **Safe/Blocked zones:** Định nghĩa tập trung trong `path_zones.py`, được dùng bởi `schema_gate.py` và `coverage_enforce.py`. Tốt.

---

## 5. Đề xuất cải thiện

### Ưu tiên cao (P0)

1. **Quyết định về `plan_fsm`:**
   - Nếu giữ thiết kế `BRAINSTORM`: cập nhật `tests/test_plan_fsm.py` và `tests/test_plan_orchestrator.py` để phản ánh flow mới.
   - Nếu quay lại flow cũ: sửa `state_machine.py` để `CLASSIFY` -> `ANALYZE`.

2. **Sửa `.gitignore`:**
   - Thêm `!.devin/scripts/**/__pycache__/` để tránh ghi đè `__pycache__/`.
   - Thêm `.worktrees/` vào ignore.
   - Chạy `git rm --cached` cho `.devin/telemetry/baseline.json` và `drift_state.json` nếu muốn bỏ tracking.

### Ưu tiên trung bình (P1)

3. **Giảm `except Exception` rộng:** refactor thành exception cụ thể (`json.JSONDecodeError`, `OSError`, `FileNotFoundError`, v.v.) để tránh che lỗi.

4. **Cài đặt `ruff` và `mypy`:**
   - `pip install ruff mypy` hoặc thêm vào `pyproject.toml` `[project.optional-dependencies].dev`.
   - Chạy `ruff check .` và `mypy .devin/scripts .devin/hooks`.

5. **Xem xét `mcp_config.json`:** thay đường dẫn tuyệt đối bằng env var hoặc relative path để portable.

### Ưu tiên thấp (P2)

6. **Dọn `drift_state.json`:** xóa dữ liệu test artifact hoặc thêm logic sanitize.
7. **Xem xét `hook_hashes.json`:** tách `_generated` timestamp ra file riêng hoặc ignore file này.

---

## 6. Các file/thư mục cần chú ý

| File | Lý do |
|------|-------|
| `.devin/scripts/plan_fsm/state_machine.py` | Xung đột state `BRAINSTORM` vs tests |
| `.devin/hooks/pre_tool_use.py` | Gate bảo mật chính, cần giữ vững |
| `.devin/hooks/schema_gate.py` | Kiểm tra path/secret/encoding sau mỗi tool call |
| `.devin/scripts/path_zones.py` | Source of truth cho safe/blocked zones |
| `.gitignore` | Cần sửa để ignore pycache và worktrees |
| `.devin/telemetry/drift_state.json` | Chứa dữ liệu lạ, có thể cần dọn |

---

## 7. Kết luận

Source base của AHD khá vững về bảo mật và kiến trúc, coverage test cao (90.17%). Điểm yếu chính là **mismatch giữa `plan_fsm` và tests**, cộng thêm **`.gitignore` chưa chuẩn** dẫn đến `__pycache__` và runtime artifacts rò rỉ vào git.

Nếu muốn tiếp tục, tôi có thể:
- Sửa 15 test fail `plan_fsm`.
- Sửa `.gitignore` và dọn runtime artifacts.
- Refactor `except Exception` rộng.
