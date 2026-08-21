# HARNESS_UPGRADE_REPORT — HLK Micro-dissection

> Phiên: `harness-upgrade` kết hợp `full-power` (manual, subagent quota đã cạn)  
> Mục tiêu: vi phẫu từng setting/config của HLK, áp dụng upgrade nhỏ nhất, verify sau mỗi bước.

---

## GoalSpec

- **Objective**: Rà soát và tối ưu cấu hình/setting của HLK (`HLK/config/`, `HLK/wrappers/`, `HLK/loop/`, `HLK/security/`, `HLK/package.json`, `HLK/custom-hooks/`) theo quy trình `harness-upgrade` detail/upgrade.md.
- **Acceptance criteria**:
  - `node HLK/wrappers/hlk-verify-integrity.js` PASS
  - `pytest` toàn bộ suite PASS (2360 passed, 3 skipped)
  - Không phá vỡ behavior hiện tại, không tạo false positive mới
  - Mỗi upgrade là 1 diff nhỏ, có verify

## Baseline

- HLK integrity: ✅ PASS (v3.0.0, hlk_enabled=true)
- Full pytest: ✅ 2360 passed, 3 skipped (0 failed) — trước và sau khi áp dụng upgrade

---

## 1. `HLK/config/hlk.config.json`

| Setting | Trạng thái cũ | Phát hiện | Hành động |
|---|---|---|---|
| `failClosedOnConfigError` | `false` | Config lỗi/thiếu pattern → fallback defaults, tiềm ẩn lọt secret | **Bật `true`** — fail-closed mặc định theo CVE-2026-AHD-011 |
| `redact_patterns` | có pattern quá rộng `(?i)(mongodb\+srv\|postgresql\|mysql)://[^\s]+` | Redact cả URL không chứa credential (false positive) | **Xóa** pattern rộng; **thêm** pattern empty-user `://:[^@\s]+@` để bắt `redis://:pass@...` |
| `redact_patterns` | thiếu AWS session token, Datadog key | Thiếu coverage so với `sanitizer.js` defaults | **Thêm** `(?i)aws[_-]?session[_-]?token\s*=\s*['"]?[A-Za-z0-9/+=]{40,}` và `(?i)datadog[_-]?(api\|app)[_-]?key\s*=\s*['"]?[a-f0-9]{32}` |
| `telemetry_overrides` | `OTEL_METRICS_EXPORTER=file`, `OTEL_LOGS_EXPORTER=file` | Vẫn tạo file telemetry cục bộ | **Chuyển thành `none`** — chặn hoàn toàn metric/log exporter |
| `scan_paths` | `src/**, config/**, .env*` | Chưa bao gồm `.devin/scripts/`, `tests/`, `HLK/**` | **Ghi nhận** rủi ro residual — hiện chưa có consumer nào dùng `scan_paths` |
| `secretPrecedence` | `file>env` | `secrets.env` placeholder có thể override env thật nếu chưa điền | **Ghi nhận** rủi ro — cần kiểm tra nội dung file khi onboard |

### Kết quả kiểm thử sanitizer sau chỉnh sửa

```
postgresql://localhost/prod -> postgresql://localhost/prod   (không còn false positive)
postgres://admin:s3cr3t@db.example.com:5432/prod -> [REDACTED]/prod
redis://:pass123@cache.internal:6379/0 -> [REDACTED]/0
mongodb+srv://user:pass@cluster/db -> [REDACTED]/db
```

## 2. `HLK/loop/hlk-loop.config.json`

| Setting | Phát hiện | Hành động |
|---|---|---|
| Step `07` `ruflo_hardening_implementation` | Tham chiếu `HLK/prompts/07_ruflo_hardening_implementation.prompt.md` nhưng file **không tồn tại** | **Tạo prompt 07** để config nhất quán với step/report 07 |
| `runner.command = "npx"`, `args_template` dùng `npx claude-flow swarm run` | Phụ thuộc network + package `claude-flow` public; có thể không khả dụng offline | **Ghi nhận** — cần cân nhắc mode `manual` hoặc local binary |
| `max_iterations = 3` | Hạn chế loop tự học | **Ghi nhận** — có thể tăng khi ổn định |
| `timeout_ms = 1800000` | 30 phút mỗi step | **Ghi nhận** — phù hợp, không đổi |

## 3. `HLK/package.json`

| Setting | Trạng thái cũ | Phát hiện | Hành động |
|---|---|---|---|
| `engines.node` | `>=14.0.0` | Code dùng `node:fs/url` prefix (cần ≥14.18.0) và `fs.cpSync` (≥16.7.0) | **Nâng thành `>=14.18.0`** — chính xác hóa yêu cầu tối thiểu |
| `type: module` | `module` | ESM consistent | Giữ nguyên |
| `bin` entries | 10 binaries | Hợp lệ | Giữ nguyên |

## 4. `HLK/config/secrets.env.example`

| Setting | Trạng thái cũ | Phát hiện | Hành động |
|---|---|---|---|
| Keys list | 4 keys (AIDE/SPARK/DEEPWIKI/DEVIN) | Thiếu provider keys, MCP token, Mongo password so với best-practice doc | **Bổ sung** `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `MCP_AUTH_TOKEN`, `MONGO_INITDB_ROOT_PASSWORD` với placeholder `example-change-me` |

## 5. `HLK/wrappers/hlk-hook-launcher.mjs`

| Setting | Phát hiện | Hành động |
|---|---|---|
| `resolveHlkDir` fail path | Khi không tìm thấy `hlk-hook-bridge.mjs`, `process.stdin.pipe(process.stdout)` + `exit(0)` — **fail-open** | **Ghi nhận rủi ro residual**: nếu HLK bị xóa/lỗi path, secret có thể đi qua hook. Cần quyết định chuyển sang fail-closed (`exit(2)`) |

## 6. `HLK/wrappers/hlk-hook-bridge.mjs`

| Setting | Phát hiện | Hành động |
|---|---|---|
| `BLOCK_TOOLS = ['Bash', 'ApplyPatch']` + `sanitizerFailed` | Fail-closed khi sanitizer lỗi | Hợp lệ — giữ |
| `tool_input` sanitizer | Đệ quy redact mọi string trong `tool_input` | Hợp lệ — giữ |
| `agent-tool` hooks | Load từ `HLK/custom-hooks/agent-tool/` | Hợp lệ — giữ |

## 7. `HLK/wrappers/hlk-loader.js`

| Setting | Phát hiện | Hành động |
|---|---|---|
| `hlk_enabled = false` no-op | Tuyệt đối no-op khi tắt | Hợp lệ — giữ |
| `process.argv` sanitizer | Chỉ redact flag `-v, --value, --data, --content` | Hợp lệ — giữ; ghi nhận có thể mở rộng flag nếu cần |
| Custom hooks `pre-argv`, `post-sanitize` | Load từ `HLK/custom-hooks/<phase>/` | Hợp lệ — giữ |

## 8. `HLK/security/sanitizer.js` & `vault-bridge.js`

| Setting | Phát hiện | Hành động |
|---|---|---|
| `DEFAULT_PATTERNS` | Đầy đủ, dùng làm critical baseline | Giữ; `failClosedOnConfigError=true` đảm bảo config không thể thiếu critical |
| `vault-bridge` `file>env` | Ưu tiên `secrets.env` > `process.env` | Hợp lệ về lý thuyết, nhưng cần cảnh báo placeholder (xem residual risk) |

## 9. `HLK/setup/install.mjs`

| Setting | Phát hiện | Hành động |
|---|---|---|
| `--yes` flag | Parse nhưng chưa dùng | **Ghi nhận** — cần implement hoặc xóa |
| `SKIP_CLONE` | Hỗ trợ source local | Giữ |
| `HLK_REPO`, `HLK_BRANCH` hardcoded | `thanhnt-sm/Loop_harness_ruflo` | Hợp lệ với upstream của repo |
| `fs.cpSync` fallback | Hỗ trợ Node 14 | Hợp lệ với engine ≥14.18.0 |

---

## Applied upgrades (theo thứ tự)

1. `HLK/config/hlk.config.json`
   - `failClosedOnConfigError: false → true`
   - Dọn dẹp/redact_patterns: xóa pattern URL quá rộng, thêm empty-user DB URL, AWS session token, Datadog key
   - `OTEL_METRICS_EXPORTER: file → none`, `OTEL_LOGS_EXPORTER: file → none`
2. `tests/test_cve_remediation_phase3.py`
   - Cập nhật assert `failClosedOnConfigError` từ `False → True` cho phù hợp config thật
3. `HLK/prompts/07_ruflo_hardening_implementation.prompt.md`
   - Tạo prompt bị thiếu, đồng bộ với `hlk-loop.config.json` step 07
4. `HLK/package.json`
   - `engines.node: >=14.0.0 → >=14.18.0`
5. `HLK/config/secrets.env.example`
   - Bổ sung 6 key template phổ biến

---

## Verification

| Gate | Kết quả |
|---|---|
| `node HLK/wrappers/hlk-verify-integrity.js` | ✅ PASS |
| `python -m pytest tests/test_cve_remediation_phase3.py -q` | ✅ 39 passed |
| `python -m pytest tests/test_cve_remediation_phase1.py tests/test_cve_remediation_phase2.py -q` | ✅ 66 passed, 1 skipped |
| `python -m pytest tests/test_cve_remediation_*.py -q` | ✅ 130 passed, 1 skipped |
| `python -m pytest -q --no-cov` (full suite) | ✅ **2360 passed, 3 skipped** |
| Manual sanitizer smoke test | ✅ false positive DB URL fixed; `redis://:pass@` now redacted |

---

## Residual risks

1. **`hlk-hook-launcher.mjs` fail-open**: khi `hlk-hook-bridge.mjs` không tìm thấy, secret có thể đi qua. Khuyến nghị chuyển sang `exit(2)` hoặc `deny` JSON.
2. **`hlk-loop.config.json` runner phụ thuộc `npx claude-flow swarm run`**: cần kiểm tra khả năng offline hoặc chuyển mode `manual`.
3. **`scan_paths` chưa được consumer nào sử dụng**: nếu tương lai dùng, cần mở rộng sang `.devin/scripts/`, `tests/`, `HLK/**`.
4. **`docs/03-cau-hinh-best-practice.md` lệch với `hlk.config.json` thực tế**: snippet trong doc vẫn còn `OTEL_*=file`, thiếu `failClosedOnConfigError`, thiếu các pattern mới. Cần sync.
5. **`secrets.env` placeholder override env**: `file>env` an toàn khi file được điền đúng, nhưng nếu user quên thay placeholder, env thật bị override. Khuyến nghị thêm warning trong `vault-bridge.js` khi giá trị chứa `example-`.

---

## Next steps (optional)

1. Quyết định fail-closed cho `hlk-hook-launcher.mjs` và áp dụng.
2. Sync `docs/03-cau-hinh-best-practice.md` với `hlk.config.json` hiện tại.
3. Chạy red-team/adversarial-consensus trên `HLK/config/hlk.config.json` khi subagent quota khả dụng.
4. Đánh giá `hlk-loop.config.json` runner mode cho môi trường offline.

---

*Report generated by `harness-upgrade` manual execution — full-power mode, subagent quota exhausted, all verify deterministic passed.*
