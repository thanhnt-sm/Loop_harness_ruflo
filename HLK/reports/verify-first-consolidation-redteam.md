# Adversarial Review — Verify-First Consolidation to HLK

> **Target**: Plan `consolidate-to-hlk.md` (HLK as single source of truth)
> **Reviewer**: 6 personas
> **Date**: 2026-08-27
> **Post-implementation**: Yes (Phase 0-6 done)

---

## 1. Persona-Saboteur — Attack path

### Findings

**P0 [BLOCKING — must fix]**: `.devin/scripts/X.py` shim files dùng `from HLK.chain.X import *` (wildcard). Nếu attacker control được `HLK/chain/X.py` content → tất cả callers qua `.devin/` execute arbitrary code. → **Recommend**: dùng explicit imports (`from HLK.chain.X import function_a, class_b`) thay vì wildcard. HOẶC: thêm `__all__` validation trong mỗi HLK module.

**P1 [HIGH]**: `HLK/scripts/sync_to_mirrors.py` chạy với quyền user. Nếu repo bị attacker control (vd `.git/HEAD` compromised) → sync có thể ghi file malicious vào `.devin/scripts/` rồi được load bởi `.devin/` callers. → **Recommend**: thêm hash check trước sync (verify HLK files integrity).

**P1**: `HLK/chain/_platform_utils.py` `get_python_cmd()` đọc từ env `AHD_PYTHON_CMD`. Nếu set `AHD_PYTHON_CMD=/path/to/malicious` → arbitrary code execution. → **Recommend**: validate path giống `cc_cli_path` (P0 fix từ plan trước).

**P2**: `HLK/chain/loaders/verify-first-loader.js` patch `child_process.spawn` + `execFile`. Nếu Node app khác load loader này → tất cả subprocess calls đều bị intercept → có thể break functionality khác. → **Recommend**: scope loader chỉ vào `verify_first_cli.py` invocation (đã làm), nhưng cần check load order.

**P3**: `HLK/chain/config.py` fallback đọc `.devin/config/*.yaml` nếu HLK config thiếu. Nếu `.devin/config/` bị attacker write → inject malicious config. → **Recommend**: validate YAML schema trước khi load.

### Recommendations

1. **CRITICAL**: Replace wildcard imports trong shim files (`from HLK.chain.X import *` → `from HLK.chain.X import specific_items`)
2. Add hash check trong sync_to_mirrors
3. Validate `AHD_PYTHON_CMD` path (mirror P0 fix)
4. Validate YAML schema in config loader

### Verdict

🚨 **BLOCKED by P0** — wildcard imports là security hole. Phải fix trước khi ship.

---

## 2. Persona-New-Hire — Onboarding

### Findings

**P1 [GOOD]**: `HLK/docs/verify-first-deployment.md` rất comprehensive — có architecture, provider matrix, CLI examples, Python API, Node integration, migration guide, security, tests. New hire có thể onboard trong 30 phút.

**P2 [POLISH]**: `HLK/docs/migration-diff.md` là auto-generated output của `diff_compare.py`. New hire có thể run `py HLK/scripts/diff_compare.py` để xem real-time diff. ✓

**P2 [POLISH]**: `AGENTS.md` (root) có section "HLK is Source of Truth" rõ ràng. ✓

**P3**: `HLK/chain/loaders/verify-first-loader.js` không có README riêng → new hire phải đọc code để hiểu cách load. → **Recommend**: thêm `HLK/chain/loaders/README.md` ngắn.

### Recommendations

1. Add `HLK/chain/loaders/README.md` (5-10 dòng giải thích cách load)

### Verdict

✅ **GOOD** — Documentation đủ cho new hire. Polish thêm nhỏ.

---

## 3. Persona-Security-Auditor

### Findings

**P0 [FIXED trước]**: `cc_cli_path` allowlist (Phase 7 của plan trước) ✓
**P0 [FIXED]**: `live_auto_merge` có secret scan + human confirm ✓
**P0 [FIXED]**: `audit_path` validation ✓
**P0 [NEW — raised by Saboteur]**: Wildcard imports trong shim files (P0 #1 ở trên)

**P1 [OPEN]**: `HLK/scripts/sync_to_mirrors.py` — nếu sync bị trigger từ CI/CD với quyền root, có thể overwrite `.devin/` files → potential RCE. → **Recommend**: scope sync chỉ vào specific files (allowlist).

**P1 [OPEN]**: `HLK/chain/loaders/verify-first-loader.js` patch global `child_process.spawn`. Nếu Node app khác load loader → bị ảnh hưởng. → **Recommend**: dùng `Module._patch` scoped hoặc isolated loader.

**P2**: Audit log `.devin/state/verify_first_audit.jsonl` không có rotation → grow không giới hạn. → **Recommend**: dùng `auto_pr_runner.rotate_audit_log` (đã có) cho audit log này.

**P2 [OPEN]**: Config fallback đọc `.devin/config/*.yaml` — nếu attacker write YAML với secret injection → có thể leak qua CC client. → **Recommend**: validate schema YAML strict.

**P3**: Pointer files ở `.commandcode/`, `.opencode/` không có signature. Nếu attacker replace → user bị redirect đến malicious code. → **Recommend**: thêm checksum verification (SHA256 của HLK files).

### Recommendations

1. **CRITICAL**: Fix wildcard imports
2. Scope sync với file allowlist
3. Add audit log rotation
4. Validate YAML schema strict
5. Add signature cho pointer files

### Verdict

🚨 **BLOCKED by 1 P0** (wildcard imports). 3 P1 open, 3 P2 open, 1 P3 open.

---

## 4. Persona-Architect — Scalability

### Findings

**P1 [GOOD]**: `HLK/chain/` với 17 modules được split rõ ràng theo concern (BRD, scenario, rubric, test, etc.). Dễ maintain.

**P1 [GOOD]**: `sync_to_mirrors.py` idempotent + audit log → có thể chạy batch trong CI/CD.

**P2 [OPEN]**: Khi HLK lớn lên (50+ scripts), `sync_to_mirrors.py` sẽ write nhiều files → chậm nếu 100+ files. → **Recommend**: incremental sync (chỉ file thay đổi).

**P2 [OPEN]**: `HLK/chain/__init__.py` re-export 17 modules. Khi import 1 module → tất cả được load. → **Recommend**: lazy import (chỉ load khi cần).

**P2 [OPEN]**: Cross-platform testing chưa có CI matrix (chỉ test trên Windows local). → **Recommend**: GitHub Actions matrix `windows-latest` + `macos-latest` + `ubuntu-latest`.

**P3**: `HLK/chain/config.py` load file mỗi call → I/O overhead. → **Recommend**: cache config với TTL.

### Recommendations

1. Incremental sync (chỉ file thay đổi)
2. Lazy import trong `__init__.py`
3. CI matrix cho cross-platform
4. Cache config với TTL

### Verdict

✅ **ACCEPTABLE** — MVP scale được ~50 modules. Production scale cần optimization.

---

## 5. Persona-Code-Reviewer

### Findings

**P1 [GOOD]**: 6 test files mới (`test_migration_diff.py`, `test_hlk_config.py`, `test_hlk_skill_pointer.py`, `test_provider_config.py`, `test_sync_to_mirrors.py`, Node test) — total ~25 tests, all pass.

**P1 [GOOD]**: 38+ tests cũ (verify-first chain) vẫn pass với shim re-export → backward compat guarantee.

**P2 [POLISH]**: `HLK/chain/__init__.py` re-export dài 200 dòng → khó review. → **Recommend**: generate từ script (auto-build `__all__`).

**P2 [POLISH]**: `HLK/scripts/sync_to_mirrors.py` có 4 separate functions (sync_to_devin/cmdc/opencode/audit). Có thể consolidate thành 1 config-driven function.

**P3 [OK]**: Code style consistent với existing convention. ✓

**P3 [OPEN]**: Cross-platform tests (`test_platform_utils.py`) chỉ pass trên Windows (1 skip trên POSIX). Cần test trên macOS/Linux thật. → **Recommend**: CI matrix.

### Recommendations

1. Generate `__init__.py` từ script (auto)
2. Consolidate sync functions
3. CI matrix cho cross-platform

### Verdict

✅ **GOOD** — Test coverage tốt, code style nhất quán.

---

## 6. Persona-Claim-Grader

### Findings (graded)

**Claim 1**: "HLK là source of truth duy nhất"
- Grade: **[inference]** — architecture design nhưng chưa prove bằng enforcement. Có thể dev tạo file ngoài HLK mà không ai check.
- Action: cần CI lint rule: fail nếu có file .py mới ở .devin/scripts/ mà không có mirror ở HLK/chain/.

**Claim 2**: ".devin không bị xóa"
- Grade: **[fact]** — `git status` confirm, `ls .devin/scripts/` shows 18 files (17 original + config.py mới từ sync).
- Evidence: `sync_to_mirrors.py` chỉ add/update, không delete.

**Claim 3**: "Mirror 1 chiều HLK → providers"
- Grade: **[fact]** — `sync_to_mirrors.py` chỉ ghi, không đọc từ mirror.
- Evidence: code review.

**Claim 4**: "Cross-platform guarantee"
- Grade: **[inference]** — 12 unit tests pass trên Windows. Chưa test trên macOS/Linux.
- Action: cần CI matrix.

**Claim 5**: "Provider registration"
- Grade: **[fact]** — `opencode.json` có `references.hlk` + `references.verify-first`. AGENTS.md có section. Pointer files ở `.commandcode/`, `.opencode/`.
- Evidence: `tests/test_provider_config.py` pass.

**Claim 6**: "All 7 phases completed"
- Grade: **[inference]** — Phase 0-6 done, tests pass. Final verify + report (Phase 8) chưa done.

### Recommendations

1. Add CI lint: fail nếu file .py mới ở .devin/scripts/ không có mirror HLK
2. Setup CI matrix
3. Complete Phase 8 final verify

### Verdict

✅ **MIXED** — 3 claim [fact], 3 claim [inference]. Cần final verify + CI.

---

## 7. Tổng hợp

| Persona | Verdict | Blocking | Open Advisory |
|---|---|---|---|
| Saboteur | 🚨 BLOCKED | 1 (P0 wildcard) | 4 (P1-P3) |
| New-Hire | ✅ GOOD | 0 | 1 (P3 polish) |
| Security-Auditor | 🚨 BLOCKED | 1 (P0 wildcard) | 7 (P1-P3) |
| Architect | ✅ ACCEPTABLE | 0 | 4 (P2-P3) |
| Code-Reviewer | ✅ GOOD | 0 | 3 (P2-P3) |
| Claim-Grader | ✅ MIXED | 0 | 3 (verify) |

### Overall Verdict

🚨 **BLOCKED BY 1 P0** (wildcard imports trong shim files).

### What's been verified

✅ 7/8 phases done (Phase 0-6 complete):
- HLK cover 17 modules
- Pointer files ở 3 providers
- 38+ tests pass
- Sync mechanism work
- 7 security fixes applied (from previous plans)

### What's still open

**P0** (must fix before production):
- Wildcard imports trong shim files

**P1** (recommended before scale):
- Incremental sync
- Lazy imports
- Audit log rotation
- CI matrix
- Scope sync với allowlist

**P2-P3** (polish):
- README cho loaders
- Auto-generate `__init__.py`
- Various

### Risk assessment

- **Current risk**: MEDIUM (P0 wildcard chưa exploit được nhưng là attack surface)
- **Production risk**: LOW nếu fix P0 + setup CI matrix

---

**Reviewer**: combined 6 personas
**Confidence**: high (post-implementation)
**Recommend re-review**: sau khi fix P0 wildcard imports
