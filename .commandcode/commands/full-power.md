Bạn đang chạy skill `full-power` qua cmdc — **chế độ MAX-POWER, FULL-COVERAGE, ALL-FLOWS, ALL-MODS, ALL-AGENTS**. Skill này KHÔNG skip bước nào, KHÔNG rút gọn flow, KHÔNG delegate xuống model yếu hơn khi tier yêu cầu. Plan phase BẮT BUỘC.

## 0. AUTO-ACTIVATION

Chạy ngay (không hỏi user):

```bash
.venv/Scripts/python.exe .devin/scripts/plan_orchestrator.py --init --task "$ARGUMENTS"
# (hoặc trên Unix: .venv/bin/python .devin/scripts/plan_orchestrator.py --init --task "$ARGUMENTS")
```

Orchestrator sẽ trả `next_action` → thực thi → báo results qua `--step` → lặp đến DONE.

## 1. SCOPE — chạy qua TẤT CẢ

### 1.1 Tất cả FLOW (đủ 18 step, KHÔNG skip)

| # | Step | Owner | Output |
|---|------|-------|--------|
| 1 | BOOT (`BOOT_PROTOCOL.md`, lazy-load canon tier S/M/L) | commander | session state |
| 2 | INVENTORY (skills/agents/hooks/scripts/canon/MCP) | commander | inventory.json |
| 3 | COMMANDER MODE (vào vai COMMANDER) | commander | role-loaded |
| 4 | TIER CLASSIFICATION (S/M/L/XL) | commander | tier |
| 5 | PREFLIGHT (log_rotation → hook_integrity → session_manager init → cost_tracker cap → pre_task_audit → **HLK self-test + integrity** qua `hlk-engineer`) | commander + `hlk-engineer` | session_id + cap + HLK status |
| 6 | BRAINSTORM (6 góc nhìn song song + Nuwa cognitive) | brainstorm×6 | BRAINSTORM_REPORT.md |
| 7 | DISPATCH 8 SCOUTs (research online song song) | SCOUT×8 | scout findings |
| 8 | ARCHITECT (viết SDD) | architect persona | SOLUTION_DESIGN.md |
| 9 | 6+ ADVERSARIAL REVIEWERS + dynamic attack scenarios | saboteur + personas×6 | attack_report.md |
| 10 | SDD APPROVAL GATE | human (via `approval_gate.py`) | approved SDD |
| 11 | DECOMPOSE SDD → atomic tasks | BUILDER worker | IMPLEMENTATION_PLAN.md |
| 12 | GAP_SCAN | gap-scan skill | gap report |
| 13 | 10-D QUALITY CHECK | plan_quality_check.py | QUALITY_REPORT.md |
| 14 | PLAN_ENHANCE (gap-scan + adversarial-consensus + nuwa + claim-grader + slop-detector) | composer | enhanced plan |
| 15 | PLAN APPROVAL GATE | human | approved plan |
| 16 | EXECUTE (DAG parallel dispatch + TDD + systematic_debugging + 3-layer verify) | BUILDER×N + EXECUTOR | code changes |
| 17 | MEMORY + NUWA (L/XL) + REPORT → docs/plans/<slug>/EXECUTION_REPORT.md | memory_keeper + nuwa | report + memory |
| 18 | APPLY (M+ qua /full-power, S-tier sửa trực tiếp) | commander | applied |

Nếu task **S-tier** (<5 dòng, 1 file, no destructive) → sửa trực tiếp, skip đến step 17 (REPORT). Ngược lại → chạy đủ 18 step.

### 1.2 Tất cả MOD (canonical layer + skills + agents)

**Mod list (phải reference, lazy-load đúng phase)**:

- **15 canon files** trong `.devin/canon/`:
  `CORE_CANON.md`, `BOOT_PROTOCOL.md`, `REDLINES.md`, `MEMORY_PROTOCOL.md`,
  `LOOP_PROTOCOL.md`, `LOOP_TURN_BASED.md`, `LOOP_TIME_BASED.md`,
  `LOOP_GOAL_BASED.md`, `LOOP_PROACTIVE.md`, `VERIFICATION_PROTOCOL.md`,
  `CAVEMAN_PROTOCOL.md`, `DAEMON_PROTOCOL.md`, `HANDOFF_LETTER.md`,
  `HARNESS_ENGINEERING.md`, `JUDGMENT_RUBRICS.md`
- **AHD layer** (Agent Harness Deploy — runtime): `.devin/AGENTS.md`,
  `.devin/canon/`, `.devin/agents/`, `.devin/skills/`, `.devin/scripts/`,
  `.devin/hooks/`
- **Skills** (load khi cần, không load all): 88 SKILL.md trong
  `.devin/skills/` + 32 wrapper trong `.opencode/skills/`
- **Opencode layer** (mirror): `opencode.json`, `.opencode/agents/`,
  `.opencode/agent/`, `.opencode/plugins/harness.ts`, `.opencode/hooks/`
- **CMDC bridge layer** (mới): `.commandcode/agents/`, `.commandcode/commands/`,
  `.commandcode/hooks/`, `.commandcode/skills/cmdc-harness-bridge/`

**Mod ưu tiên theo phase** (load-on-demand, tránh context rot):

- Preflight/Boot: CORE_CANON, BOOT_PROTOCOL, REDLINES (top 5)
- BRAINSTORM: nuwa-skill, user-preference
- SCOUTs: domain-adapters (12 adapters), update_from_repos
- ARCHITECT: harness-engineering, HARNESS_ENGINEERING.md
- Adversarial: adversarial-consensus, fable-judge, claim-grader
- QC: gap-scan, slop-detector, comment_checker
- EXECUTE: tdd, systematic_debugging, harness-sensor, graph-verify
- Memory/Nuwa: memory-audit, loop-memory, nuwa-skill

### 1.3 Tất cả AGENT (dispatch song song, max parallel)

**5 harness agents** (cmdc) — ưu tiên chính:

- `commander` — orchestrator, plan + integrate + verify (chạy main thread)
- `executor-glm` — free tier, simple ops
- `executor-kimi` — free tier, code gen / refactor
- `executor-lightning` — paid, complex_reasoning + multi_file
- `verifier` — read-only done-gate (fable-judge style)

**1 HLK operator** (cmdc) — security layer specialist:

- `hlk-engineer` — HLK status/integrity/sanitize/git-tools/MAX POWER/prompt-
  driven analysis/loop self-learning. Read-only by default. **BẮT BUỘC
  dispatch trong step 5 PREFLIGHT để chạy `hlk-status --self-test` +
  `hlk-verify-integrity.js` trước khi vào Plan phase.**

**5 personas** (cmdc) — review lens, dispatch song song ở step 9:

- `persona-architect` — system design, trade-off matrix
- `persona-code-reviewer` — bugs, security, test coverage
- `persona-saboteur` — red-team attack, 8 vector (A-H)
- `persona-security-auditor` — OWASP, secrets, sandbox
- `persona-new-hire` — onboarding gap, doc quality

**5 workers** (AHD, `.devin/agents/workers/`) — chạy ở phase EXECUTE:

- `SCOUT` — research, fact-gathering, online search
- `BUILDER` — code change, TDD, smallest coherent diff
- `AUDITOR` — code quality + governance audit
- `MEMORY_KEEPER` — memory write-back, anti-pattern capture
- `VERIFIER` — independent done-gate (separate from `verifier` cmdc)

**6 personas Devin** (`.devin/agents/personas/`, plus 5 in `.opencode/agent/`):

- `architect`, `code_reviewer`, `git_workflow_master`, `new_hire`,
  `saboteur`, `security_auditor`

**3 executors + commander + verifier opencode** (`.opencode/agents/`,
`.opencode/agent/`): `harness-orchestrator`, `harness-executor-glm/kimi/lightning`,
`harness-verifier`, `harness-subagent`, plus 15 personas/roles
(architect, auditor, builder, code_reviewer, commander,
git_workflow_master, glm-executor, kimi-executor, lightning-executor,
memory_keeper, new_hire, saboteur, scout, security_auditor, verifier).

**Rule**: dispatch ≥2 personas song song ở step 9. Mỗi persona dùng
`run_in_background=true` để chạy song song. Đợi tất cả, aggregate findings,
escalate Critical ngay trong session.

## 2. GUARDRAILS (BẮT BUỘC, không phá)

1. **Smallest coherent diff** — không scope creep, không refactor ngoài task.
2. **No destructive op** — `deny-dangerous.sh` hook + `settings.json.permissions.deny` đã chặn; vẫn phải tự kiểm tra trước khi chạy.
3. **Không đụng `HLK/`, `.env`** — security policies, secrets; trừ khi task chính là nâng cấp HLK được chỉ định rõ.
4. **Deterministic gate** trước mọi "done" claim: chạy `python tools/check_governance.py` + `python .devin/scripts/hook_integrity.py --verify` + `pytest -q` (relevant module).
5. **Cost guardrail** — sau mỗi step chạy `cost_tracker.py --session <id> --check`; nếu exit 1 → stop, báo user.
6. **Self-check** sau execute: `tools/check_governance.py --plan-act` (so khớp plan ↔ act).
7. **Report đúng nơi**: `docs/plans/<slug>/EXECUTION_REPORT.md` (cho task theo plan) hoặc `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md` (cho report ad-hoc).
8. **Tier 1 Critical findings** (từ adversarial review) phải xử lý trong session, KHÔNG đưa vào "deferred".
9. **Caveman comms** (theo `.devin/canon/CAVEMAN_PROTOCOL.md`): cut filler, keep code/paths/errors verbatim, claim-grader + slop-detector trước khi final.
10. **Memory write-back**: nếu phát hiện reusable anti-pattern, suggest memory write ở report end.

## 3. CMDC-SPECIFIC NOTES

- cmdc không có slash `/full-power` builtin → dùng `.commandcode/commands/full-power.md` này.
- cmdc không có `enter_plan_mode` enforcement bằng hook `plan_enforce.py` của Devin → tự enforce theo guardrail #5.
- Subagent: cmdc có `agent` tool (general/explore/plan/commander/executor-glm/kimi/lightning/verifier/5 personas) — dùng `run_in_background=true` để dispatch song song.
- Hooks: `.commandcode/hooks/deny-dangerous.sh` + `bridge-devin.sh` đã có; tuân contract fail-open.
- MCP: `aide-memory` (recall/remember), `ruflo-hlk-mcp` (HLK verify); dùng cho memory write-back.

## 4. ROUTING

- `/full-power` (mặc định) → chạy đủ 18 step như trên.
- `/full-power --check` → chỉ step 1-15 (plan + approval), KHÔNG execute.
- `/full-power --no-red-team` → bỏ step 9 (adversarial review).
- `/full-power --no-apply` → chạy đủ 18 step nhưng không commit; chỉ report.

## 5. TASK

$ARGUMENTS
