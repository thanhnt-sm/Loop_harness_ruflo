# IMPLEMENTATION PLAN — Harness Audit & Upgrade

**Slug:** harness-audit-20260912
**Generated:** 2026-09-12
**Branch:** audit/upgrade-20260912
**Baseline Commit:** 4f8fbcd (main)

---

## 1. Audit Summary

### Baseline Measurements (read-only)
| Metric | Value |
|--------|-------|
| **Always-on BOOT tokens** | ~8,163 tokens |
| **On-demand total tokens** | ~28,916 tokens |
| **Grand total** | ~37,079 tokens |
| **Skills (top-level)** | 15 |
| **Canon files** | 15 |
| **Scripts (.py)** | 151 |
| **Hooks (.py)** | 51 |
| **Agent MD files** | 18 |
| **Tool registry tiers** | 5 |
| **Tool entries** | 88 |
| **Slop hits** | 0 |
| **Governance check** | PASS (exit 0) |
| **REPOS_TRACKER.json mutation** | YES (from check_updates.py --force) |

### Upstream Status (from check_updates.py --force)
| Repo | Current | Upstream | Strategy | Priority |
|------|---------|----------|----------|----------|
| nuwa-skill | 27642f5 | fe03746 | direct-copy-vendored | P0 |
| caveman | 2f49f0e | 15581d1 | manual-canon-update | P3 |
| loop-engineering | 804a4e9 | 712117a | manual-canon-update | P3 |

### 9-Chân Diagnosis Scores
| Dimension | Finding | Score (0-5) |
|-----------|---------|-------------|
| **Context** | BOOT ~8K tokens; on-demand ~29K tokens; always-on includes 4 files | 2 |
| **Tool Registry** | 5 tiers, 88 tools, all unique; no idle tools detected | 3 |
| **Canon** | 15 files; CORE_CANON no overlap hits for git/subagent/deployment | 2 |
| **Skills** | 15 skills; some rarely used (hlk-*, aide-memory, claim-grader); no lazy-load metadata | 2 |
| **Scripts** | 151 py scripts; many pre_tool_*/post_tool_*; auto-run on every call adds overhead | 2 |
| **Hooks** | 53 hooks; pre_tool_* gates on every call — token/friction cost | 2 |
| **Instruction Density** | 28 verify refs across AGENTS/CLAUDE/.devin/AGENTS; REDLINES present | 3 |
| **Compensation** | C1-C7 coverage: C3 (adversarial-review) via adversarial-consensus; C5 (deterministic gates) via schema_gate/plan_enforce; gaps in C2 (lazy-load) | 3 |
| **Repos** | 3 behind (nuwa-skill, caveman, loop-engineering); AHD up-to-date | 3 |

---

## 2. Priority Scoring (v2 formula)

Formula: Priority = (quality_gain × token_saved × determinism_gain) / (risk × effort)

| Candidate | Quality Gain | Token Saved | Determinism | Risk | Effort | Priority | Action |
|-----------|--------------|-------------|-------------|------|--------|----------|--------|
| Lazy-load skills | 4 | 5 | 5 | 1 | 2 | 50.0 | Review only |
| Remove idle hooks | 4 | 4 | 4 | 2 | 3 | 10.7 | Review only |
| Consolidate canon | 3 | 3 | 4 | 2 | 3 | 6.0 | Review only |
| Update nuwa-skill | 3 | 2 | 3 | 2 | 2 | 4.5 | Review only |
| Update caveman | 2 | 2 | 3 | 2 | 3 | 2.0 | No-op unless new concept |
| Update loop-engineering | 2 | 2 | 3 | 2 | 3 | 2.0 | No-op unless new concept |
| Tool registry lazy-load | 3 | 2 | 3 | 3 | 3 | 2.0 | Review only |
| Slop removal | 1 | 1 | 3 | 1 | 2 | 1.5 | Monitor only |

---

## 3. Audit-Only Scope (No Code or Upstream Apply)

This plan authorizes evidence collection and design review only. It does not authorize edits to hooks, schema, canon, skills, upstream copies, or repository configuration beyond the already task-owned .gitignore allowlist.

### Phase 1 — Discovery and Contract Evidence
| Task | File Path | Function | Acceptance Criteria | REQ ID |
|------|-----------|----------|---------------------|--------|
| Inventory skill loading behavior | .devin/skills/skill_index.json; .devin/hooks/pre_tool_use.py | Read-only callsite/contract inspection | Identify actual loader, callers, and regression surface; no edits | REQ-001 |
| Inventory tool registry injection | .devin/tool_registry.json; .devin/hooks/schema_gate.py | Read-only contract inspection | Identify boot injection and activation semantics; no edits | REQ-002 |
| Inventory hook behavior | .devin/hooks/*.py | Read-only behavior map | Prove usage/redundancy per hook with callsite evidence; no edits | REQ-003 |
| Inventory canon overlap | .devin/canon/*.md | Read-only semantic comparison | Identify concrete duplicate/stale sections; no edits | REQ-004 |

### Phase 2 — Candidate Design Reviews
| Candidate | File Path | Required Gate Before Any Future Apply | REQ ID |
|-----------|-----------|---------------------------------------|--------|
| Skill lazy-loading | .devin/skills/skill_index.json; .devin/hooks/pre_tool_use.py | Separate approved implementation plan plus contract/regression test design | REQ-010 |
| Tool registry lazy-loading | .devin/tool_registry.json; .devin/hooks/schema_gate.py | Separate approved implementation plan plus boot/invocation evidence | REQ-011 |
| Hook optimization | .devin/hooks/*.py | Protected-hook review, per-hook evidence, separate approval | REQ-012 |
| nuwa-skill update | .devin/skills/nuwa-skill/ | Immutable upstream diff, provenance, and verification review | REQ-020 |
| caveman canon | .devin/canon/CAVEMAN_PROTOCOL.md | No-op unless review proves a new concept; canon remains untouched | REQ-021 |
| loop-engineering canon | .devin/canon/LOOP_PROTOCOL.md | No-op unless review proves a new concept; canon remains untouched | REQ-022 |

### Phase 3 — Deferred Apply

- No implementation changes in this plan.
- No upstream copy or cherry-pick.
- No canon consolidation.
- No full-power Execute, harness-upgrade --apply, or infinite loop.
- Any future apply requires a new plan with explicit File Path, symbol/contract evidence, acceptance tests, and human approval.

---

## 4. Verification Gates (deterministic)

| Gate | Command | Exit Code Must Be |
|------|---------|-------------------|
| Governance layout | python3 tools/check_governance.py --layout-only | 0 |
| Governance plan-act | python3 tools/check_governance.py --plan-act | 0 after execution report exists |
| Workspace verify | pwsh tools/verify-workspace.ps1 | 0 for future apply |
| HLK integrity | node HLK/wrappers/hlk-verify-integrity.js | 0 for future apply |
| Token footprint | python3 .devin/scripts/context_projection.py --report | BOOT tokens ≤ baseline |
| Skill import smoke | python3 tools/import_smoke_test.py | 0 for future apply |
| Tracker mutation | git diff --stat .devin/metadata/REPOS_TRACKER.json | Pre-existing mutation unchanged |

---

## 5. Rollback Plan

If verification fails:
1. Stop and record the failing gate and affected files.
2. Preserve unrelated user changes; do not use destructive reset or checkout.
3. Revert only task-owned files listed in this plan after reviewing the diff.
4. Keep .devin/metadata/REPOS_TRACKER.json unchanged unless a dedicated approved task authorizes rollback.
5. Record results in EXECUTION_REPORT.md only after approved execution.
6. If selective rollback is unsafe, stop and request review.

---

## 6. Risk & Dependencies

| Risk | Mitigation |
|------|------------|
| Lazy-load breaks skill_view | Phase 1 gate: skill_view smoke test |
| Hook changes cause friction | Phase 4 gate: governance check + verify-workspace |
| Upstream update breaks HLK | Phase 3 gate: hlk-verify-integrity.js PASS required |
| REPOS_TRACKER.json mutation | Preserve pre-existing mutation; do not revert without a dedicated approved task |

## 7. Plan Artifact Tracking

- File Path: .gitignore
- Function: allowlist this plan directory so governance can track the artifact
- Acceptance Criteria: git status lists the plan directory and check_governance.py --layout-only remains clean
- REQ ID: REQ-000
- This scope change is task-owned plan metadata only; it does not authorize upgrade execution.

## 8. Current Unrelated Mutation

- .devin/metadata/REPOS_TRACKER.json remains a pre-existing mutation from the earlier check_updates.py --force run.
- It is preserved as workspace state and is not reverted by this plan.
- No reset, force checkout, or destructive rollback is authorized.

---

## 9. Acceptance Criteria (Plan Level)

- [ ] Governance layout check PASS.
- [ ] Audit outputs remain read-only and reproducible.
- [ ] No core hook/schema/canon/skill file is modified under this plan.
- [ ] Always-on BOOT tokens do not regress from baseline (32,653 chars) if a future approved plan changes context.
- [ ] Slop hits remain 0.
- [ ] Upstream candidates are review-gated individually; `caveman` and `loop-engineering` remain no-op absent proven new concepts.
- [ ] `EXECUTION_REPORT.md` is written only after separately approved execution, with commits, files changed, test results, and residual risks.

