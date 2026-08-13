# Báo cáo An ninh & Củng cố Môi trường Loop Harness

**Ngày:** 2026-08-13
**Phạm vi:** Toàn bộ source code, kiến trúc, giải pháp AHD (`.devin/`, `tools/`, `HLK/`, configs) + môi trường chạy.
**Kết quả test:** `pytest` — **2060 passed, 0 failed, coverage 84.64%** (gate 80%).

---

## 1. Hiện trạng ban đầu (trước khi củng cố)

### 1.1 Môi trường thiếu công cụ (đã cài tự động, không cần root)
| Thiếu | Ảnh hưởng | Đã xử lý |
|---|---|---|
| `python3` hoàn toàn (Debian 12, không sudo) | Không chạy được `.devin/scripts/*.py`, hooks, test | Cài **Python 3.11.15** qua `uv` tại `/workspace/.tools/python` |
| `pytest` + deps (pydantic, pytest-cov, hypothesis, filelock, pyyaml) | Test suite không chạy | Venv `/workspace/.venv` — đã cài đầy đủ |
| `pwsh` (PowerShell) | Toàn bộ `tools/*.ps1` (deploy/package/verify) không chạy | Cài **PowerShell 7.6.4** tại `/workspace/.tools/pwsh` (cần `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` vì thiếu libicu hệ thống) |
| `python` không trên PATH | `tests/test_pytest_config.py` fail | `.venv/bin` prepend PATH (qua `.tools/env.sh` + `.bashrc`) |

Toolchain hiện có: `uv` 0.12.3, `node v22.23.2`, `npm 10.9.8`, `git 2.39.5`. Env tự nạp: `source /workspace/.tools/env.sh`.

### 1.2 Repo hỏng trạng thái (đã khôi phục)
- **18 file `.devin/agents/`** (COMMANDER.md, DISPATCH_TEMPLATES.md, 3 executors, 6 personas, 5 workers) **bị xoá khỏi working tree** (uncommitted) → đã `git restore`. 4 test FSM/agents fail vì thiếu các file này.
- **`hook_hashes.json` stale** (13 hooks) → đã `hook_integrity.py --generate` + `--verify` PASS.

### 1.3 Trước khi vá: 7 test fail / 2037 pass
| Test | Nguyên nhân | Loại |
|---|---|---|
| test_commander_md_has_3_states | thiếu file agents | repo state |
| test_dispatch_templates_has_3_new | thiếu file agents | repo state |
| test_agents_have_required_fields | thiếu thư mục agents | repo state |
| test_agent_names_match_directories | thiếu thư mục agents | repo state |
| test_hook_integrity::test_verify_passes | hash baseline stale | repo state |
| test_pytest_collect_only_passes | `python` không trên PATH | môi trường |
| test_validate_absolute_path_blocks_system_dirs | **lỗ hổng thật** | an ninh |

---

## 2. Lỗ hổng đã phát hiện & vá (red-team findings)

### 2.1 `path_zones.py` — Windows system-dir bypass trên Linux (P1) ✅ ĐÃ VÁ
- **File:** `.devin/scripts/path_zones.py:181-202`
- **Lỗ hổng:** `validate_absolute_path("C:/Windows/System32/my-harness")` **trả True (cho phép)** trên Linux. Vì `Path.resolve()` trên Linux coi `\` là ký tự thường → resolve thành `/workspace/C:/Windows/...` (prefix cwd) → check `DANGEROUS_ROOTS` (`c:/windows`) không khớp → bypass.
- **Khai thác:** deploy tooling (`tools/deploy-template.ps1`) có thể cài harness vào system dir ngay cả khi chạy trên Linux — phá vỡ cam kết chặn `C:/Windows/System32`, `/etc`, `/usr/bin`.
- **Vá:** kiểm tra **cả dạng raw (chưa resolve)** lẫn dạng resolved cho path traversal và `DANGEROUS_ROOTS`.
- **Test:** `tests/test_path_validation.py` (19/19 pass).

### 2.2 `schema_gate.py` — fail-open khi exception (P1) ✅ ĐÃ VÁ
- **File:** `.devin/hooks/schema_gate.py:522-525`
- **Lỗ hổng:** `except Exception` gán `result["code"] = 0` → bất kỳ lỗi không ngờ nào (lỗi code, payload dị dạng ngoài dự kiến) khiến cổng **cho phép** write/edit đi qua → security gate trở thành trang trí.
- **Khai thác:** agent chèn payload làm hỏng gate (JSON array thay vì dict, tool_input sai kiểu) → schema_gate vô hiệu, có thể ghi file ngoài safe zone.
- **Vá:** fail-closed mặc định (exit 1), opt-in fail-open qua `AHD_SCHEMA_GATE_FAIL_OPEN=1` (đồng bộ với nhánh timeout đã fail-closed từ trước).
- **Test:** `tests/test_schema_gate.py` (thêm `test_unexpected_exception_fails_closed`, `test_fail_open_opt_in_env`).

### 2.3 `pre_tool_use.py` — SSRF bypass qua IP encoding (P1) ✅ ĐÃ VÁ
- **File:** `.devin/hooks/pre_tool_use.py` — `check_ssrf()`
- **Lỗ hổng:** check `ipaddress.ip_address(host)` bỏ qua các dạng encoding: `2130706433` (decimal 127.0.0.1), `0x7f000001` (hex), `017700000001` (octal), `0177.0.0.1` (octal dotted), `127.1` (short-form, Python 3.9.5+ strict → ValueError → pass), `0x7f.0.0.1`. Tất cả đều bypass → agent có thể fetch metadata/private endpoint.
- **Khai thác:** `curl http://2130706433:8080/` hoặc `curl http://0x7f000001/` → vượt SSRF guard, đọc `169.254.169.254` metadata / dịch vụ nội bộ.
- **Vá:** thêm `_decode_ip_encoding()` chuẩn hoá hex/octal/decimal/short-form/IPv4-mapped-IPv6 (`::ffff:127.0.0.1`) trước khi check; thêm `is_unspecified` vào điều kiện block.
- **Test:** `tests/test_ssrf_guard.py` (parametrize 9 dạng bypass).

### 2.4 Deny list thiếu destructive disk/partition ops (P2) ✅ ĐÃ VÁ
- **File:** `.devin/hooks/pre_tool_use.py` DANGEROUS_PATTERNS + `.devin/config.json` deny
- **Lỗ hổng:** chỉ có `mkfs`, `dd`, `format`, `shred` — thiếu `fdisk`, `sfdisk`, `parted`, `mkpart`, `lvremove`, `vgremove`, `pvremove`, `cryptsetup luksFormat/erase/remove`, `swapoff`, `shutdown`, `reboot`, `halt`, `poweroff`.
- **Vá:** bổ sung cả 2 tầng (Python guard + config deny) + block host power control.
- **Test:** full suite pass (không false positive trên test hiện hữu).

### 2.5 `check_updates.py` — URL fetch thiếu scheme/host guard (B310) ✅ ĐÃ VÁ
- **File:** `.devin/scripts/check_updates.py:46-65`
- **Lỗ hổng:** `urllib.urlopen` trên URL nội suy từ config nguồn (branch/owner/repo) — nếu config bị độc (supply chain qua skill `update_from_repos`), có thể mở `file://` / scheme tuỳ biến / SSRF.
- **Vá:** chỉ cho phép `https://` tới `api.github.com`/`github.com`; các URL khác bị từ chối.
- **Test:** `tests/test_check_updates.py` (4 tests mới).

### 2.6 Bảo mật môi trường ✅ ĐÃ XỬ LÝ
- **Quyền file:** config nhạy cảm từ 777 → **640** (`.devin/config*.json`, `mcp_config.json`, `hook_hashes.json`, `risk_contract.json`, `memory_config.json`, `HLK/config/*.json`).
- **Secret scan git history:** 35 hits đều là **test fixture giả** (`AKIAIOSFODNN7EXAMPLE`, `ghp_abcdef...`) — không có secret thật. Không có `.env` nào được track; `.gitignore` đã chặn toàn bộ `.env*`.
- **bandit:** 0 High / 0 Medium thật / 43 Low (phần lớn là subprocess `shell=False` an toàn + regex redaction chứa chuỗi "password="). 2 Medium còn lại là **false positive**: `0.0.0.0` là chuỗi block SSRF (B104) và `urlopen` đã được guard ở 2.5 (B310).

---

## 3. Findings còn lại (chưa vá — đề xuất cho implementation plan)

| ID | Mức | Khu vực | Finding | Trạng thái |
|---|---|---|---|---|
| R-01 | P1 | hooks | Các gate trong `pre_tool_use.py` vẫn `except Exception: pass` (fail-open cục bộ) tại `_check_context_oversized_gate`, `_check_cost_cap_gate`, `_check_encoding_bypass_gate`, `_check_reflection_gate` — nên đổi thành log severity cao + quyết định fail-closed rõ ràng | ✅ ĐÃ VÁ (T1.1) — tất cả gate giờ `_gate_error()` fail-closed, opt-in `AHD_FAIL_OPEN=1` |
| R-02 | P1 | config | `.devin/config.json` còn 15 vị trí hardcode path Windows nvm (`${USER_HOME}\AppData\Roaming\nvm\v18.20.0\...`) — chưa được placeholder hoá (C3 Round 3 nói đã sửa nhưng file gốc vẫn còn) | ✅ ĐÃ VÁ (T2.1) — thay bằng `{{AIDE_MEMORY_GLOBAL}}`; detector chặn hardcode mới trong `qa_doc_audit.py` (T2.2) |
| R-03 | P2 | HLK/git-tools | `hlk-git-lib.mjs` thiếu `auditTrackedArtifacts()` (chặn commit .env/secret) — theo G-02 audit cũ | ✅ ĐÃ VÁ (T3.1) — `auditTrackedArtifacts()` + tích hợp commit (mới→block, pre-existing→warn) + doctor (`checkTrackedSecrets`) |
| R-04 | P2 | supply chain | `package.json` (root + HLK) không có lockfile (`npm audit` không chạy được) — tạo `package-lock.json` để audit được | ✅ ĐÃ VÁ (T3.2) — 2 lockfile tạo, `npm audit` = 0 vulnerabilities |
| R-05 | P2 | code | `coverage_enforce.py` B104 false positive + coverage `update_common.py` chỉ 30% — cần test bổ sung | ✅ ĐÃ VÁ (T4.2) — `test_update_common.py` (20 tests, 30%→92%), `test_coverage_enforce.py` (18 tests) |
| R-06 | P2 | ops | Hook chain `PreToolUse` có prompt-based deny (LLM quyết định) — phụ thuộc LLM; nên thay bằng deterministic gate hoặc keep + deterministic double-check | ✅ ĐÃ VÁ (T1.2) — prompt deny list mở rộng khớp `DANGEROUS_PATTERNS` (fdisk/parted/lvremove/cryptsetup/swapoff/power); deterministic layer giữ làm lớp chính |
| R-07 | P2 | AGENTS.md | `AGENTS_full.md` 186KB — BOOT nạp toàn bộ gây tốn token (T-01) — cần lazy-load chuẩn | ✅ ĐÃ VÁ (T5.1) — `tests/test_boot_lazy_load.py` (6 tests) enforce entry <8KB, canon on-demand, không nhúng nội dung |
| R-08 | P3 | khuym | `.codex/` scripts (onboarding báo complete) không có trong git — plugin-managed; xác nhận lại onboarding state | ⚠️ GHI NHẬN — `.codex/` KHÔNG tồn tại trên disk dù `onboarding.json`=complete (state stale). Không có hook nào trong repo ref `.codex/`. File plugin giữ nguyên |
| R-09 | P3 | code | duplicate pattern `.gitignore` (.env, `__pycache__`) — cleanup thuần cosmetics | ✅ ĐÃ VÁ (T5.2) — xoá 25 dòng duplicate, `.env`/`__pycache__` vẫn ignore |
| R-10 | P3 | hardening | Không có SAST trong CI — thêm bandit + `npm audit` vào `.github/workflows/ci.yml` | ✅ ĐÃ VÁ (T4.1) — bandit step (fail on High) trong job `ahd-python` |

## 4. Đề xuất (recommendations)

1. **Fail-closed là mặc định cho mọi security gate** — triệt để xoá pattern `except: pass` trong hooks; chỉ opt-in fail-open qua env rõ ràng.
2. **Placeholder hoá toàn bộ path cứng** — biến mọi `${USER_HOME}`, `nvm/vX`, `aide-memory` thành `{{...}}` placeholder, resolve lúc deploy (thống nhất với `PlaceholderUtils.ps1`).
3. **Đưa SAST vào CI** — bandit (0 High gate), `npm audit`, `hook_integrity --verify` mỗi lần merge.
4. **Secret guard ở tầng git** — implement `auditTrackedArtifacts()` trong HLK git-lib để chặn commit `.env`/token; kèm `git log` scanner.
5. **Giảm bề mặt LLM-trust** — prompt-hook deny giữ làm lớp 2; lớp 1 phải deterministic (regex + config deny).
6. **Cải thiện token** — lazy-load canon theo `BOOT_PROTOCOL.md`, không load `AGENTS_full.md` nguyên cục.
7. **Lockfile** — tạo `package-lock.json` cho root + HLK để bật `npm audit` + supply-chain visibility.

---

## 5. Trạng thái cuối

- **Test:** 2108 passed / 0 failed, coverage **85.97%** (trước: 2062 pass / 84.90%). Mới thêm 54 tests (fail-closed gate, qa_doc_audit, update_common, coverage_enforce, boot lazy-load).
- **Hooks:** `hook_integrity --verify` PASS (13 hooks, hash đã regenerate sau khi sửa pre_tool_use + coverage_enforce).
- **bandit:** 0 High / 2 Medium (false positive: `0.0.0.0` SSRF-block string B104 + urlopen đã guard B310) / 43 Low.
- **npm audit:** 0 vulnerabilities (root + HLK, lockfile đã có).
- **HLK doctor:** `hlk-git-doctor.mjs` chạy được, báo 9 tracked artifacts chứa chuỗi secret (toàn bộ là test fixture giả).
- **Git:** các thay đổi chưa commit (working tree); `agents`/`plan`/`.devin/{agents,plan}_state` là runtime symlink của harness (trỏ `state/` gitignored).
- **Lệnh dùng lại:** `source /workspace/.tools/env.sh && pytest` / `bandit -r .devin/scripts .devin/hooks tools` / `node HLK/git-tools/hlk-git-doctor.mjs`.
