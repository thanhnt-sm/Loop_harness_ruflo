# Adversarial Review — Rollout Pipeline P1

**Artifact:** `tools/package-template.ps1`, `tools/init-new-project.ps1`, `tools/deploy-template.ps1`, `.devin/scripts/path_zones.py`
**Type:** code
**Date:** 2026-08-10
**Rounds:** 1/3
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

## Consensus decision

[CONSENSUS] Tất cả BLOCKING issues đã được sửa trong Round 1. Còn lại một số ADVISORY về duplicated logic, tight coupling, hardcoded absolute paths trong deployed config — được ghi nhận là technical debt cho P2/P3. Artifacts đã đạt P1 Canary.
