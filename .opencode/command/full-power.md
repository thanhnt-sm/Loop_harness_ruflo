---
description: Full Power Mode — 3-Phase đầy đủ (Plan→Approve→Execute) với max parallel, adversarial review, QC gates, enforcement. FORCE Plan phase bắt buộc. Chạy qua tất cả flow / tất cả mod / tất cả agent. Gọi: /full-power <task>
agent: build
---

Bạn đang chạy skill `full-power`. Thực thi theo đúng launcher — **MAX-POWER, FULL-COVERAGE, ALL-FLOWS, ALL-MODS, ALL-AGENTS** (KHÔNG skip bước nào, KHÔNG rút gọn flow):

1. Đọc `/workspace/.devin/skills/full-power/SKILL.md` (source of truth, chứa full chain 3-Phase, 18 step).
2. Phân tích task `$ARGUMENTS`:
   - **S-tier** (<5 dòng, 1 file, không destructive) → sửa trực tiếp, báo kết quả.
   - **M/L/XL** → mở Plan phase: `python .devin/scripts/plan_orchestrator.py --init --task "$ARGUMENTS"`.
3. **Chạy đủ 18 step** (xem `.commandcode/commands/full-power.md` để biết chi tiết từng step):
   BOOT → INVENTORY → COMMANDER_MODE → TIER → PREFLIGHT → BRAINSTORM (6 góc) → 8 SCOUTs song song → ARCHITECT (SDD) → 6+ adversarial reviewers song song → SDD approval gate → DECOMPOSE → GAP_SCAN → 10-D QC → PLAN_ENHANCE → plan approval gate → EXECUTE (DAG parallel + TDD + 3-layer verify) → MEMORY + NUWA + REPORT → APPLY.
4. **Quét TẤT CẢ mod** (load-on-demand theo phase, không load all):
   - 15 canon files trong `.devin/canon/` (CORE_CANON, BOOT_PROTOCOL, REDLINES, MEMORY_PROTOCOL, LOOP_*, VERIFICATION, CAVEMAN, DAEMON, HANDOFF, HARNESS_ENGINEERING, JUDGMENT_RUBRICS).
   - AHD layer: `.devin/AGENTS.md`, `.devin/agents/`, `.devin/skills/`, `.devin/scripts/`, `.devin/hooks/`.
   - Opencode layer: `opencode.json`, `.opencode/agents/`, `.opencode/agent/`, `.opencode/plugins/harness.ts`, `.opencode/hooks/`.
   - 88 skill files trong `.devin/skills/` + 32 wrapper trong `.opencode/skills/` (load theo phase).
5. **Dispatch TẤT CẢ agent** (max parallel, `run_in_background: true`):
   - 5 harness (cmdc): `commander` (main), `executor-glm/kimi/lightning`, `verifier`.
   - 5 personas (cmdc): `persona-architect`, `persona-code-reviewer`, `persona-saboteur`, `persona-security-auditor`, `persona-new-hire`.
   - 1 HLK operator (cmdc): `hlk-engineer` — BẮT BUỘC chạy ở step 5 PREFLIGHT để verify HLK.
   - 5 workers (AHD): `SCOUT`, `BUILDER`, `AUDITOR`, `MEMORY_KEEPER`, `VERIFIER`.
   - 6 personas Devin (`architect`, `code_reviewer`, `git_workflow_master`, `new_hire`, `saboteur`, `security_auditor`) + 15 personas/roles opencode (architect, auditor, builder, code_reviewer, commander, git_workflow_master, 3 executors, memory_keeper, new_hire, saboteur, scout, security_auditor, verifier).
   - ≥2 personas song song ở step 9; aggregate findings; Tier 1 Critical fix ngay trong session.
6. Tuân theo orchestrator (Plan → Approve → Execute), báo results qua `--step`, lặp đến DONE.
7. Không đụng `HLK/`, `.env`, security policies. Không destructive op.
8. Sau execute: self-check `python tools/check_governance.py` + `python tools/check_governance.py --plan-act` + viết execution report đúng nơi (`docs/plans/<slug>/EXECUTION_REPORT.md` hoặc `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md`).

Routing:

- `/full-power` (mặc định) → đủ 18 step + apply.
- `/full-power --check` → step 1-15, không execute.
- `/full-power --no-red-team` → bỏ step 9.
- `/full-power --no-apply` → đủ 18 step nhưng không commit.

$ARGUMENTS
