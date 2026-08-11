# Adversarial Review — Rollout Pipeline P1

**Artifact:** `tools/package-template.ps1`, `tools/init-new-project.ps1`, `tools/deploy-template.ps1`, `.devin/scripts/path_zones.py`
**Type:** code
**Date:** 2026-08-11
**Rounds:** 4/4
**Status:** CONSENSUS after revision

## Round 1 summary

### Findings by persona

#### Saboteur
- [DISSENT:BLOCKING] Path validation bypass trong `path_zones.py` cho absolute paths — `validate_absolute_path()` cho phép deploy vào `C:\Windows\System32` vì không chặn dangerous system roots.
- [DISSENT:ADVISORY] Race condition trên staging directory trong `package-template.ps1` — timestamp độ phân giải giây có thể collision khi 2 process cùng chạy.
- [DISSENT:ADVISORY] No timeout cho P1 gate tests — pytest/bench/red-team có thể treo mãi mãi.
- [DISSENT:ADVISORY] Inconsistent error handling trong `package-template.ps1` — `Remove-Item` dùng `SilentlyContinue` nuốt lỗi.

#### Security Auditor
- [DISSENT:ADVISORY] Path Traversal Validation Incomplete in `deploy-template.ps1` — regex `\.\.` yếu, không kiểm tra sau `GetFullPath` normalize.
- [DISSENT:ADVISORY] Placeholder Resolution Potential Injection in `deploy-template.ps1` — `$escaped = $kv.Value -replace '\\', '\\'` chỉ escape backslash, các ký tự regex khác (`$`, `+`, `?`, v.v.) có thể gây regex injection.
- [REVIEW:PASS] Zip Extraction Security — GOOD
- [REVIEW:PASS] Secret Exclusion — GOOD
- [REVIEW:PASS] Blocked Zone Enforcement — GOOD
- [REVIEW:PASS] Source/Target Separation — GOOD

#### Architect
- [DISSENT:ADVISORY] Hardcoded Absolute Paths in Deployed Config — config.json chứa đường dẫn máy cụ thể.
- [DISSENT:ADVISORY] Duplicated Rollout Gate Logic — `package-template.ps1` và `init-new-project.ps1` cùng implement gate.
- [DISSENT:ADVISORY] Tight Coupling Between Scripts — hardcoded required file paths.
- [DISSENT:ADVISORY] Placeholder Resolution Brittleness — hai implementation khác nhau, hardcoded key order.
- [DISSENT:ADVISORY] Path Traversal Check is Naive — string-based `..` detection có thể bypass.

### Promoted issues (2+ reviewers)
- **Path traversal/validation bypass** — found by Saboteur + Security Auditor + Architect → ADVISORY/BLOCKING promoted to **BLOCKING**.
- **Placeholder resolution brittleness/injection** — found by Security Auditor + Architect → promoted to **ADVISORY**.

### Final severity tally
- BLOCKING: 1
- ADVISORY: 7
- INFO: 0

## Revision history

### Round 1
- Thêm `DANGEROUS_ROOTS` trong `.devin/scripts/path_zones.py` để chặn deploy vào `C:/Windows`, `C:/Program Files`, `C:/ProgramData`, `/etc`, `/usr/bin`, v.v.
- Sửa `validate_absolute_path()` dùng `Path.resolve(strict=False)` để resolve `..` và symlinks, sau đó kiểm tra dangerous roots + blocked zones.
- Sửa `package-template.ps1` staging directory dùng GUID thay vì chỉ timestamp giây: `harness-staging-$timestamp-$guid`.
- Sửa `package-template.ps1` cleanup `Remove-Item` dùng `try/catch` + `ErrorAction Stop` thay vì `SilentlyContinue`.
- Sửa `deploy-template.ps1` placeholder resolution dùng string `.Replace($kv.Key, $kv.Value)` thay vì regex `-replace` để tránh regex injection.
- Sửa `package-template.ps1` recursive placeholder resolution dùng string `.Replace` thay vì regex `-replace`.
- Thêm `tests/test_path_validation.py` cases cho `DANGEROUS_ROOTS`, `validate_absolute_path`, path traversal resolve.
- Chạy full test suite: **2042 passed, 2 skipped, 85.45% coverage**.

### Round 2
- Tách logic rollout gates vào `tools/RolloutGates.ps1` dùng chung cho `package-template.ps1` và `init-new-project.ps1` — fix duplicated logic.
- Bỏ regex `\.\.` naive trong `deploy-template.ps1`, dựa hoàn toàn vào `path_zones.py` (single source of truth) cho path traversal validation.
- Thêm `tools/RolloutGates.ps1` vào danh sách `requiredFiles` trong `init-new-project.ps1`.
- Chạy `package-template -RolloutStage P1 -DryRun` và `init-new-project -RolloutStage P1 -DryRun`: P1 gate PASSED.
- Chạy full test suite lại: **2042 passed, 2 skipped, 85.45% coverage**.

### Round 3
- Thêm `Invoke-ExternalCommand` trong `tools/RolloutGates.ps1` dùng `Start-Process` + redirect output sang temp files + `Wait-Process -Timeout` — fix no timeout cho gate tests (pytest 600s, bench 180s, red-team 180s, e2e 180s).
- Trong `package-template.ps1`: thay thế hardcoded nvm/aide-memory prefix `${USER_HOME}\AppData\Roaming\nvm\v18.20.0\node_modules\aide-memory` trong `.devin/config.json` bằng `{{AIDE_MEMORY_GLOBAL}}`.
- Trong `deploy-template.ps1`: escape backslash trong replacement value khi ghi vào JSON raw text; thêm `Set-BashCommandSlashes` để chuyển backslash → forward slash và bọc đường dẫn trong dấu nháy kép nếu chứa dấu cách.
- Chạy `package-template -RolloutStage P1 -DryRun`: P1 PASSED, Placeholders 2.
- Triển khai `init-new-project -RolloutStage P1` sang `Loop_harness_pilot_v3`: P1 PASSED, HLK install OK, verify 62/62, HLK integrity PASS, smoke 62/0, bash commands resolved với forward slashes và quoted.

### Round 4
- Chạy C3 review 3 persona (Saboteur, Security Auditor, Architect) trên P2 pipeline sau khi triển khai `Loop_harness_pilot_v4`.
- **Findings:**
  - Saboteur: Wait-Process -Timeout không hoạt động trên PowerShell 5.1; init-new-project thiếu timeout HLK; ErrorActionPreference Continue trong deploy-template; placeholder ${USER_HOME}; python availability; git uncommitted changes warning.
  - Security Auditor: command injection qua `& python` trong deploy-template; Start-Process ArgumentList không quote ở init-new-project; ErrorActionPreference Continue; hardcoded bot email; temp file cleanup silent.
  - Architect: inconsistent ErrorActionPreference; duplicate placeholder resolution; missing timeout in init-new-project.
- **Fix Round 4:**
  - RolloutGates.ps1: thêm fallback loop timeout cho PowerShell < 7.4; log warning khi cleanup temp file fail.
  - deploy-template.ps1: dot-source RolloutGates.ps1; dùng Invoke-ExternalCommand cho path_zones với check python availability; đổi ErrorActionPreference = 'Stop'; xóa hardcoded bot email; thêm `${USER_HOME}` placeholder resolution.
  - init-new-project.ps1: dùng Invoke-ExternalCommand cho HLK install (300s) và verify (180s).
  - Full test suite: 2042 passed, 2 skipped, 85.45%.
  - Triển khai `Loop_harness_pilot_v5` bằng `init-new-project -RolloutStage P2`: P2 PASSED, verify 62/62, HLK PASS, smoke 62/0.

## Consensus decision

[CONSENSUS] Sau Round 4, tất cả BLOCKING và hầu hết ADVISORY từ C3 review đã được sửa. P2 Pilot (`Loop_harness_pilot_v5`) triển khai thành công với E2E pass, verify 62/62, HLK PASS, smoke 62/0. Các vấn đề còn lại (duplicate placeholder resolution, tight coupling nhẹ) được ghi nợ kỹ thuật cho P3 GA.
