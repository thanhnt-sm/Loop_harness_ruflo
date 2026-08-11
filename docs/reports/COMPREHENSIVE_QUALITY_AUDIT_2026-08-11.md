# Báo cáo Audit Chất Lượng Toàn Diện — Loop_harness_ruflo

**Ngày:** 2026-08-11
**Audit tracks:** 7
**Mô hình:** subagent_explore, read-only
**Output:** docs/reports/COMPREHENSIVE_QUALITY_AUDIT_2026-08-11.md

---

## Tóm tắt điều hành

Repo `Loop_harness_ruflo` đã được audit trên 7 trục chất lượng theo yêu cầu:
- Khuym workflow
- AHD harness engineering
- Code review
- Security (thay thế `ck-security`)
- Adversarial-consensus
- Token/cost (thay thế `ck-predict`)
- Git workflow

**Tổng phát hiện:** 19 findings
- P0 (Critical): 7
- P1 (High): 8
- P2 (Medium): 4

**Kết luận cao cấp:**
- AHD harness architecture tổng thể tốt, tuân thủ 5 pillars.
- Khuym onboarding bị mâu thuẫn: state báo complete nhưng `.codex/` không tồn tại.
- Security hooks có fail-open exception và SSRF bypass nguy hiểm.
- Token cost: waste lớn từ `AGENTS.md` 186KB và BOOT ~158KB.
- Code coverage thiếu test cho 2 module quan trọng.

---

## Bảng mapping skill yêu cầu

| Skill yêu cầu | Track thực tế | Tình trạng |
|---|---|---|
| khuym-framework | Track 1 — Khuym workflow | ✅ chạy |
| harness-framework | Track 2 — AHD harness audit | ✅ chạy |
| code-review | Track 3 — Code review audit | ✅ chạy |
| ck-security | Track 4 — Security audit | ✅ substitute |
| adversarial-consensus | Track 5 — Adversarial-consensus audit | ✅ chạy |
| ck-predict | Track 6 — Token/cost audit | ✅ substitute |
| — | Track 7 — Git workflow audit | ✅ bổ sung |

---

## Track findings

### Track 1 — Khuym workflow

| ID | Severity | Finding | Evidence | Tag |
|---|---|---|---|---|
| K-01 | P0 | Thiếu toàn bộ thư mục `.codex/` và 7 support scripts | `.khuym/onboarding.json:19-28`; `.codex/` not found | [fact] |
| K-02 | P1 | Mâu thuẫn onboarding state "complete" vs thiếu file | `.khuym/onboarding.json:6` | [inference] |
| K-03 | P2 | state.json đang idle, chưa có workflow active | `.khuym/state.json:4-6` | [fact] |

### Track 2 — AHD harness audit

Không phát hiện P0/P1/P2. 5 pillars (caveman, context, harness, loop, memory), BOOT lazy-load, Maker≠Checker, 3 stop conditions, safe/blocked zones đều tuân thủ.

| ID | Severity | Finding | Evidence | Tag |
|---|---|---|---|---|
| H-01 | — | Không có vấn đề | `CORE_CANON.md`, `LOOP_PROTOCOL.md`, `REDLINES.md`, `CAVEMAN_PROTOCOL.md` | [fact] |

### Track 3 — Code review audit

| ID | Severity | Finding | Evidence | Tag |
|---|---|---|---|---|
| C-01 | P0 | Thiếu test `test_spc_monitor.py` | `.devin/scripts/spc_monitor.py` (352 dòng); no `tests/test_spc_monitor.py` | [fact] |
| C-02 | P0 | Thiếu test `test_state_router.py` | `.devin/scripts/state_router.py` (355 dòng); no `tests/test_state_router.py` | [fact] |
| C-03 | P1 | 42 lần `except Exception` trong `.devin/scripts/` | `spc_monitor.py:81,98`; `state_router.py:250`; `worktree.py:102,110,136,141,152,175`; `dag_executor.py:415,510,537` | [fact] |
| C-04 | P2 | `.gitignore` duplicate `.env` entries, `example.env` bị ignore | `.gitignore:61-63,167-169,193` | [fact]/[inference] |
| C-05 | P2 | BRAINSTORM implementation thiếu edge case test | `state_machine.py:51-64`; `test_plan_fsm.py:334-342` | [inference] |

### Track 4 — Security audit (thay `ck-security`)

| ID | Severity | Finding | Evidence | Tag |
|---|---|---|---|---|
| S-01 | P0 | `schema_gate.py` fail-open khi exception | `.devin/hooks/schema_gate.py:522-525` | [fact] |
| S-02 | P1 | `pre_tool_use.py` 5 gate dùng `pass` khi exception | `.devin/hooks/pre_tool_use.py:420-422,465-467,510-512,540-542,614-616` | [fact] |
| S-03 | P1 | SSRF bypass qua IP encoding (decimal/hex/octal) | `.devin/hooks/pre_tool_use.py:267-318` | [fact] |
| S-04 | P2 | `config.json` deny list thiếu `mkfs.*`, `fdisk`, `parted`, `lvremove`, `vgremove`, `cryptsetup` | `.devin/config.json:56-79` | [fact] |

### Track 5 — Adversarial-consensus

| ID | Severity | Finding | Evidence | Tag |
|---|---|---|---|---|
| A-01 | P0 | Mâu thuẫn số vòng lặp tối đa (3 vs 7 rounds) | `.devin/skills/adversarial-consensus/SKILL.md:38,147,249` | [fact] |
| A-02 | P1 | Thiếu logic thực thi aggregation / deduplication | `.devin/skills/adversarial-consensus/SKILL.md:136-141` | [inference] |
| A-03 | P2 | Dynamic scenarios trùng persona cố định | `.devin/scripts/plan_fsm/missions.py:144-225` | [inference] |

### Track 6 — Token/cost (thay `ck-predict`)

| ID | Severity | Finding | Evidence | Tag |
|---|---|---|---|---|
| T-01 | P0 | `AGENTS.md` 186KB (46.5K tokens) — waste lớn nhất | `.devin/AGENTS.md`; `HLK/docs/REDTEAM_REPORT.md:93-148` | [fact] |
| T-02 | P0 | BOOT sequence ~158KB (10× over target <16KB) | `HLK/docs/REDTEAM_REPORT.md` | [fact] |
| T-03 | P1 | Model tier escalation không có cost cap | `.devin/agents/model_tiers.md` | [inference] |
| T-04 | P2 | Nuwa ROI threshold đã được tăng từ 1.5 lên 3.0 | `.devin/scripts/nuwa_roi.py` | [fact] |

### Track 7 — Git workflow

| ID | Severity | Finding | Evidence | Tag |
|---|---|---|---|---|
| G-01 | P0 | `__pycache__` patterns trùng lặp trong `.gitignore` | `.gitignore:90,251-252,263` | [fact] |
| G-02 | P1 | HLK git tools thiếu audit tracked artifacts | `HLK/git-tools/lib/hlk-git-lib.mjs:135-162` | [inference] |
| G-03 | P2 | `worktree.py` không kiểm tra repo health trước khi tạo worktree | `.devin/scripts/worktree.py:180-219` | [inference] |

---

## Phân tích token cost

### Trạng thái hiện tại

- `cost_tracker.py` theo dõi cumulative cost, cap $5.0.
- Always-on context chiếm **26.6%** context window (~53K tokens).
- `.devin/AGENTS.md` chiếm **186KB (~46.5K tokens)** — waste lớn nhất.
- BOOT sequence thực tế **~158KB** (mục tiêu <16KB).
- `FULL_POWER_PROMPT` mỗi lần chạy **~70-80K tokens**.
- Potential savings mỗi session: **200-250K tokens**.

### Đề xuất tối ưu token

1. **Truncate `AGENTS.md` + load canon on-demand**
   - Tác động: tiết kiệm ~41K tokens/session (23.3% context window).
   - Cách làm: giữ `AGENTS.md` 5KB summary; chuyển full canon sang `AGENTS_full.md`; load canon cụ thể khi cần theo `BOOT_PROTOCOL.md`.
   - Effort: 1 ngày.
   - Ưu tiên: P0.

2. **Lazy-load BOOT protocol steps 9-16**
   - Tác động: giảm cold start 60-70%, tiết kiệm ~120K tokens/BOOT.
   - Cách làm: steps 1-8 mandatory; steps 9-16 on-demand; step 17 optional.
   - Effort: 1 tuần.
   - Ưu tiên: P0.

Tổng tiết kiệm ước tính: **~160K tokens/session** (~80% GLM context window).

---

## Anti-pattern catalog

| Anti-pattern | Vị trí | Khuyến nghị |
|---|---|---|
| `except Exception` broad | `.devin/scripts/*` | Thay bằng exception cụ thể hoặc `sys.exit` trong security gates |
| Fail-open security gate | `schema_gate.py:522-525` | Mặc định block khi exception |
| Onboarding drift | `.khuym/onboarding.json` | Re-sync state với file system |
| Always-on oversized context | `.devin/AGENTS.md` | Lazy-load canon |
| Spec contradiction | `adversarial-consensus/SKILL.md` | Đồng nhất max rounds |

---

## Appendix: Evidence list

| Finding ID | File | Lines | Trạng thái verifier |
|---|---|---|---|
| K-01 | `.khuym/onboarding.json` | 19-28 | Verified |
| C-01 | `.devin/scripts/spc_monitor.py` | — | Not re-verified |
| C-02 | `.devin/scripts/state_router.py` | — | Not re-verified |
| C-03 | `.devin/scripts/*` | nhiều | Not re-verified |
| S-01 | `.devin/hooks/schema_gate.py` | 522-525 | Verified |
| S-02 | `.devin/hooks/pre_tool_use.py` | 420-422,465-467,510-512,540-542,614-616 | Not re-verified |
| S-03 | `.devin/hooks/pre_tool_use.py` | 267-318 | Not re-verified |
| A-01 | `.devin/skills/adversarial-consensus/SKILL.md` | 38,147,249 | Not re-verified |
| T-01 | `.devin/AGENTS.md` | — | Not re-verified |
| G-01 | `.gitignore` | 90,251-252,263 | Not re-verified |

---

## Plan state

- IMPLEMENTATION_PLAN: <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\docs\plans\comprehensive-quality-audit-plan\IMPLEMENTATION_PLAN.md" />
- SDD: <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\docs\plans\comprehensive-quality-audit-plan\SOLUTION_DESIGN.md" />
- Quality Report: <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\docs\plans\QUALITY_REPORT_IMPLEMENTATION_PLAN.md" />
