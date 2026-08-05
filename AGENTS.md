# Devin CLI — Agent Harness Deploy (AHD)

> **Full reference**: `docs/AGENTS_full_reference.md` (load on-demand only)
> **Usage guide**: `docs/USAGE_GUIDE.md` — tất cả skills/agents/flows
> **Loop guide**: `docs/CONTINUOUS_LOOP_GUIDE.md` — chạy loop liên tục

## Orchestrator skills (3 executors)

| Skill | Executor | Model | Cost | Khi nào |
|-------|----------|-------|------|---------|
| `/lightning` | lightning-executor | SWE-1.7 Lightning | $2.5/$12.5 MTok | Cần tốc độ (1000 tok/s) |
| `/glm` | glm-executor | GLM-5.2 High | **Free** | Free tier, reasoning cao |
| `/kimi` | kimi-executor | Kimi K2.7 | **Free** (đến 2026-07-05) | Free tier, open-source |

Pattern chung: orchestrator (active model) plan/review → executor implement/test/report.

## Cách dùng nhanh

```bash
cd . && devin                          # Mở CLI
devin -p -- "mô tả công việc"          # Non-interactive

/full-power <task>    # 3-Phase đầy đủ (Plan→Approve→Execute) — FORCE Plan bắt buộc
/plan <task>          # Chỉ Phase 1: Plan (SDD + quality check + approval gate)
/lightning <task>     # Executor SWE-1.7 Lightning (sau khi plan approved)
/glm <task>           # Executor GLM-5.2 (free, sau khi plan approved)
/kimi <task>          # Executor Kimi K2.7 (free, sau khi plan approved)
/auditor             # Audit code
/tdd                 # Test-driven development
/gap-scan            # Scan thiếu sót
/adversarial-consensus <artifact>  # 3-persona adversarial review
```

## 3-Phase Architecture (Plan → Approve → Execute) — BẮT BUỘC

**M-tier+ tasks BẮT BUỘC đi qua 3 phase. KHÔNG SKIP. Hook `plan_enforce.py` sẽ block.**

1. **PLAN** (`/plan` hoặc `/full-power`): 5 SCOUTs song song → ARCHITECT + 3 adversarial reviewers → plan + coverage matrix → 10-D quality check
2. **APPROVE**: Human approval gate (R0 auto-approve, R1+ require review)
3. **EXECUTE**: DAG-based parallel dispatch → 3-layer verify (deterministic + adversarial + acceptance) → coverage + audit

S-tier (<5 lines, 1 file, no destructive op) → skip 3-Phase, sửa trực tiếp.

**RED LINE**: Skip Plan phase cho M-tier+ = violation.

## Guardrails

- Smallest coherent diff — không scope creep
- Preserve pre-existing user changes
- No destructive ops (chặn bởi hooks: rm -rf, force-push, drop table)
- No unrelated refactors/dependencies/docs
- Trivial edits sửa thẳng, skip delegation
- Fan-out chỉ khi write sets disjoint + user yêu cầu
- Executor unavailable → stop, report missing profile

## MCP servers

| Server | Mục đích |
|--------|----------|
| aide-memory | Persistent memory (recall/remember) |
| spark-memory | Shared memory cross-agent |
| deepwiki | Query GitHub repo docs |
| devin | Devin V3 API (sessions, playbooks) |

## Canon (on-demand, KHÔNG load all at BOOT)

| File | Load khi nào |
|------|-------------|
| CORE_CANON.md | BOOT (always) |
| BOOT_PROTOCOL.md | BOOT (always) |
| REDLINES.md | BOOT (top 5 only) |
| LOOP_PROTOCOL.md | Chạy loop |
| VERIFICATION_PROTOCOL.md | Verify output |
| MEMORY_PROTOCOL.md | Manage memory |
| CAVEMAN_PROTOCOL.md | Compress context |
| HARNESS_ENGINEERING.md | Design harness |

## AHD components (on-demand)

- **Canon**: `.devin/canon/` — 10 protocol files
- **Skills**: `.devin/skills/` — 23 skills (auditor, tdd, gap-scan, slop-detector, v.v.)
- **Agents**: `.devin/agents/` — 3 executors + COMMANDER + 6 personas + 5 workers
- **Hooks**: `.devin/hooks/` — 7 Python hooks (pre/post tool, session start/end, stop)
- **Scripts**: `.devin/scripts/` — 8 runtime scripts
- **HLK**: `HLK/` — security layer (sanitizer + vault-bridge)
- **Tools**: `tools/` — packaging, deploy, verify, health-check

## Red Team + Upgrades

- **70/70 upgrades complete** (U01-U50 P0-P3 + U51-U70 P4-P7)
- Red team score: 4.0 → **8.0/10**
- Devin compatibility: 44% → **100%**
- Trackers: `.devin/upgrade/UPGRADE_TRACKER.json` + `UPGRADE_TRACKER_V2.json`

## Safe zones cho code changes

- `src/`, `.devin/skills/`, `.devin/agents/`, `scripts/` — OK
- `HLK/`, security policies, `.env` — **KHÔNG đụng**
