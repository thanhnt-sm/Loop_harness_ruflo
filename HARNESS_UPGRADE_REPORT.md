# HARNESS UPGRADE REPORT — Iteration 5: HLK Security Layer

**Date**: 2026-08-15
**Mode**: FULL CHAIN — focus `hlk` (task chính: nâng cấp HLK + fix skill)
**Scope**: `HLK/` security layer + `harness-upgrade` skill
**Guardrail override**: user xác nhận rõ "áp dụng cho hlk" → hợp lệ exception (task chính là HLK)

---

## Baseline → After

| Layer | Baseline | After |
|-------|----------|-------|
| HLK integrity check | (không có check hành vi) | **All PASS** (19 checks, gồm sanitizer smoke + git protection) |
| Token redaction | leak `github_pat_`, `npm_`, `SG.`, `AIzaSy` dài | **redact đầy đủ** — fail-closed gate phủ hết |
| `merge.ours.driver` | inert (`.gitattributes` vô hiệu) | **cấu hình** ở install + upstream-pull |
| `core.hooksPath` | chỉ "nhắc" không set → post-merge verify không chạy | **active** `.githooks` |
| hook-bridge JSON | fail-OPEN (invalid JSON pass-through) | **fail-CLOSED** (exit 2, deny) |
| vault audit | audit cả `source=default` → log-spam | audit file/env + stderr warning default |

---

## Upgrades Applied (11 item, 10 done + 1 cancelled có lý do)

### A. HLK (8): 7 done, 1 cancelled
| ID | Mức | Upgrade | File | Verify |
|----|-----|---------|------|--------|
| U-HLK-1 | HIGH | Thêm token patterns (`github_pat_`, `npm_`, `SG.`, `AIzaSy{33,}`, `AC`, `SK`, `pub`) vào `redact_patterns` + `CRITICAL_SUBSTRINGS` | `config/hlk.config.json`, `security/sanitizer.js` | smoke test 8 cases + `healthCheck().ok` |
| U-HLK-2 | HIGH | Kích hoạt `merge.ours.driver` (trước đây inert) | `setup/install.mjs`, `upstream/hlk-upstream-pull.mjs` | `git config` + integrity check |
| U-HLK-3 | MED | Active `core.hooksPath .githooks` (trước chỉ nhắc) | `upstream/hlk-upstream-pull.mjs` | `git config core.hooksPath` |
| U-HLK-4 | MED | Fix partial redaction Google key (`{35}`→`{22,}`) | `config/hlk.config.json` | smoke `AIzaSy` dài → `[REDACTED]` |
| U-HLK-5 | token | Gộp regex alternation | **CANCELLED** | rủi ro correctness (trộn `gi`/`g`), guardrail #3 |
| U-HLK-6 | gate | Sanitizer smoke test + git protection check | `wrappers/hlk-verify-integrity.js` | integrity PASS |
| U-HLK-7 | fail-open | Invalid JSON → fail-closed (exit 2, deny schema) | `wrappers/hlk-hook-bridge.mjs` | retest exit=2 |
| U-HLK-8 | log-spam | Audit chỉ file/env + stderr warning default | `security/vault-bridge.js` | node --check |

### B. Skill fix (3): all done
| ID | Upgrade | File |
|----|---------|------|
| U-SKILL-1 | Đồng bộ exception HLK lên top rule (hết mâu thuẫn guardrail) | `SKILL.md:53`, `detail/adaptation.md:14` |
| U-SKILL-2 | Thêm guardrail #6 HLK (kèm exception) | `SKILL.md` |
| U-SKILL-3 | Thêm quy trình nâng cấp HLK (snapshot → smallest diff → verify → không force-push) | `detail/upgrade.md` |

---

## Red-Team (v2.0 targeted) — phát hiện + remediation
- **HIGH (bug thật do tôi gây)**: `install.mjs` gọi `execSync` chưa import → `merge.ours.driver` không set bởi installer. **Đã sửa** → dùng `spawnSync` (đã import).
- **MED**: fail-closed JSON output sai schema → **đã sửa** sang `hookSpecificOutput.permissionDecision`.
- **MED**: bỏ audit default mất trace fallback → **đã cân bằng**: vẫn stderr warning khi fallback default (giữ tín hiệu, tránh jsonl spam).
- **LOW/MED (pre-existing, chấp nhận)**: `merge=ours` có thể đóng băng security patch upstream (Issue 2); sanitizer fail-closed có thể thành fail-open nếu hook-bridge passthrough khi module lỗi (Issue 5). → **Không đổi iteration này** (ngoài phạm vi, tránh scope creep), ghi nhận known-risk.

> Ghi chú quy trình: full v5.0 red-team + Runtime Manifest không chạy — môi trường thiếu python (plan_orchestrator.py cần python, không có trong PATH) và không có Runtime Manifest (scope/environment/approver). Đã fallback sang targeted red-team qua subagent `saboteur`. Blocker ghi nhận ở dưới.

---

## Quality Verdict
**PASS** — tất cả deterministic gate:
- `node --check` 6/6 file HLK sửa: ✅
- `node HLK/wrappers/hlk-verify-integrity.js`: **All HLK integrity checks PASSED** (19 checks)
- Sanitizer smoke: `github_pat_`/`ghp_`/`npm_`/`AIzaSy`/`xox`/`sk_live`/`AKIA` → `[REDACTED]`
- hook-bridge invalid JSON → exit 2, deny

---

## Blocker / Note
- `python` không có trong môi trường (chỉ node) → `plan_orchestrator.py`, `context_projection.py`, `plan_quality_check.py` không chạy được. Plan được lập + approval thủ công qua question-gate. **Cần cài python (3.11+) cho chain đầy đủ ở iteration sau.**
- Red-team v5.0 full bỏ qua (thiếu Runtime Manifest) — chỉ chạy targeted.

## Next Candidates
1. ✅ **DONE (Iteration 5b)**: merge=ours log-aware driver (`HLK/git-tools/hlk-merge-ours.mjs`) — không còn silent, merge-context guard chống clobber.
2. ✅ **DONE (Iteration 5b)**: sanitizer fail-closed end-to-end — hook-bridge block (không passthrough) khi sanitizer lỗi.
3. ✅ **DONE (Iteration 5b)**: `.env` parser dotenv-convention (export prefix + inline comment + escape).
4. Install python runtime + wiring plan_orchestrator (unblock full chain).
5. `.gitignore` chặn `HLK/logs/merge-ours.log` + tài liệu review flow khi log cảnh báo security patch.

---

# ITERATION 5b — Known-risk remediation + .env parser

## Upgrades (3)
| ID | Mức | Upgrade | Verify |
|----|-----|---------|--------|
| U-HLK-9 | HIGH | **Issue 2**: merge=ours → driver log-aware `hlk-merge-ours.mjs` (giữ ours + log `HLK/logs/merge-ours.log`, merge-context guard chống clobber) | driver ngoài merge không clobber ✅; log ghi ✅ |
| U-HLK-10 | MED | **Issue 5**: sanitizer fail → block (exit 2) thay passthrough; bỏ `(text)=>text` fallback | Bash chứa secret → exit 2 ✅ |
| U-HLK-11 | MED | **.env parser**: `export ` prefix + inline comment strip + escape quote | 6 case parse PASS ✅ |

## Verification (Iteration 5b)
- node --check 5/5 file ✅
- `hlk-verify-integrity.js`: **All PASS** ✅
- hook-bridge: normal Read → exit 0; Bash chứa secret → exit 2; invalid JSON → exit 2 ✅
- .env parser: PLAIN/EXPORTED/QUOTED/SINGLE/WITH_COMMENT/ESCAPE → đúng giá trị ✅
- merge-ours driver: ngoài merge không ghi đè working tree ✅

## Incident note
Trong quá trình test driver, `git checkout --ours` đã revert các edit config hlk.config.json (footgun "silent ours"). Đã: (a) re-apply config edits, (b) thêm merge-context guard vào driver để không bao giờ chạm working tree ngoài merge thật.

## Known-risk còn lại
- merge=ours vẫn giữ bản địa khi upstream sửa security (giờ có log để review thủ công, nhưng vẫn cần operator chủ động merge patch). → candidate tiếp: quy trình tự nhắc review khi log mới xuất hiện.

---

# ITERATION 6 — Runtime Unblock + REVIEW phase

**Date**: 2026-08-15 | **Mode**: REVIEW → APPROVE → EXECUTE | **Scope**: toàn bộ harness
**Trả lời blocker Iteration 5**: `python` KHÔNG có trên PATH nhưng có tại `.venv/bin/python` (3.11.15) → unblock full chain.

## Upgrades Applied (3)
| ID | Mức | Upgrade | Verify |
|----|-----|---------|--------|
| U-RT-1 | **HIGH** | Fix `plan_orchestrator.py` hoàn toàn hỏng: relative import khi chạy script; pydantic v2 `PrivateAttr` (can't-pickle mappingproxy); `DirectEdge`/`ConditionalEdge` sai kwarg; `GraphRunner.run` context None; infinite loop QC→PLAN→GAP_SCAN; thiếu `import json`; `asyncio.run` bọc sync main → ValueError | pytest CLI 123 PASS ✅; `--init --task` chạy hết flow + in JSON + exit 0 ✅ |
| U-SKILL-PY | HIGH | `python`/`python3` không có trên PATH nhưng 9 skill files (~92 dòng) bảo chạy `python .devin/scripts/...` → mọi lệnh fail. Thay `python ` → `.venv/bin/python ` | grep không còn `python` bare trong skills ✅ |
| U-HOOK-BASELINE | MED | `hook_integrity --verify` báo 2 TAMPERED (pre_tool_use.py, schema_gate.py) — thay đổi hợp lệ từ upgrade trước chưa regenerate baseline | `--generate` + `--verify`: All 13 hooks PASSED ✅ |

## REVIEW phase scan
- Background scouts (skills/hooks) **fail** do model provider lỗi (`kimi-for-coding/k3`, `openai/gpt-5.4-nano`, v.v. prefix sai) → **self-scan** bằng grep/bash thay thế.
- Phát hiện: python-PATH issue (HIGH), hook baseline stale (MED). Hooks syntax + wiring OK; HLK integrity OK.
- Cả 2 candidates → user approve → apply → verify toàn bộ PASS.

## Quality Verdict (Iteration 6)
**PASS** — deterministic gates:
- `hook_integrity --verify`: All 13 hooks verified, no tampering ✅
- `hlk-verify-integrity.js`: All PASS ✅ | node --check 3 files HLK ✅
- Skills grep: không còn lệnh `python` bare ✅
- pytest `tests/test_cli_entrypoints.py`: 123 PASS ✅
- `plan_orchestrator.py --init --task`: chạy hết flow (SDD approve → QC → plan approve) + JSON + exit 0 ✅

## Blockers còn lại
- Subagent background tasks không chạy được (model provider config sai prefix trong môi trường).
- Full v5.0 red-team + Runtime Manifest vẫn không khả dụng (pre-existing, ngoài scope iteration này).

## Next Candidates
1. Fix model provider prefix cho subagents (kimi-for-coding/k3, openai/gpt-5.x, ...) để background scouts chạy lại.
2. Chạy full chain v5.0 red-team khi Runtime Manifest khả dụng.
3. Xem xét auto-review flow cho merge-ours.log (security patch freeze).
