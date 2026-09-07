# Component Map — V5 Red-Team Audit Iteration 1

**Generated**: 2026-09-04
**Scope**: Harness upgrade workspace (`.devin/`, `AGENTS.md`, `docs/`, `tools/`, `tests/`)

---

## 1. Prompts / Rules / Instructions

| Component | File | Load | Purpose |
|-----------|------|------|---------|
| Entry file | `AGENTS.md` | BOOT | Root entry, routes to canon/skills |
| Entry file | `CLAUDE.md` | BOOT | Universal rules for all agents |
| Canon: CORE | `.devin/canon/CORE_CANON.md` | BOOT | Universal operating principles |
| Canon: REDLINES | `.devin/canon/REDLINES.md` | BOOT (top 5) | Hard stops |
| Canon: BOOT | `.devin/canon/BOOT_PROTOCOL.md` | BOOT | Startup sequence |
| Canon: VERIFICATION | `.devin/canon/VERIFICATION_PROTOCOL.md` | ON-DEMAND | Maker≠checker, anchors |
| Canon: HARNESS_ENG | `.devin/canon/HARNESS_ENGINEERING.md` | ON-DEMAND | Design principles |
| Canon: MEMORY | `.devin/canon/MEMORY_PROTOCOL.md` | ON-DEMAND | 3-layer memory |
| Canon: LOOP | `.devin/canon/LOOP_PROTOCOL.md` | ON-DEMAND | Loop primitives |
| Canon: CAVEMAN | `.devin/canon/CAVEMAN_PROTOCOL.md` | ON-DEMAND | Token compression |
| Skills index | `.devin/skills/skill_index.json` | BOOT | Progressive load metadata |
| Skills (26) | `.devin/skills/*/SKILL.md` | ON-DEMAND | Task-specific protocols |

---

## 2. Model / Router

| Component | Description |
|-----------|-------------|
| Active model | opencode/nemotron-3-ultra-free (planner/reviewer) |
| GLM executor | GLM-5.2 High (free tier, 200K ctx) |
| Kimi executor | Kimi K2.7 (free tier until 2026-07-05) |
| Lightning executor | SWE-1.7 Lightning (1000 tok/s) |
| Router | `auto_model_router.py` — tier-based routing |

---

## 3. Agents / Subagents

| Agent | Role | Config |
|-------|------|--------|
| Commander | Orchestrator, dispatches | `.devin/agents/COMMANDER.md` |
| Workers | SCOUT, BUILDER, AUDITOR, VERIFIER, MEMORY_KEEPER | `.devin/agents/workers/` |
| Personas | architect, code_reviewer, git_workflow_master, saboteur, new_hire, security_auditor | `.devin/agents/personas/` |
| Executors | lightning-executor, glm-executor, kimi-executor | `.devin/agents/*-executor/` |

---

## 4. Flows / Retry / Cancel / Escalation

| Flow | Trigger | Mechanism |
|------|---------|-----------|
| 3-Phase Plan→Approve→Execute | `/full-power`, `/plan` | `plan_orchestrator.py` FSM |
| Zero-Command Max chain | Task without slash skill | Auto-activates 26 skills |
| Loop protocols | Turn/goal/time based | `LOOP_PROTOCOL.md` + `loop_memory_sync.py` |
| Adversarial consensus | `/adversarial-consensus` | 6+ persona review |

---

## 5. Tools / MCP / API

| Tool | Type | Registry |
|------|------|----------|
| 7 tools | Native | `.devin/tool_registry.json` |
| aide-memory | MCP (stdio) | `.devin/mcp_config.json` |
| spark-memory | MCP (remote) | `.devin/mcp_config.json` |
| deepwiki | MCP (HTTP) | `.devin/mcp_config.json` |
| devin | MCP (HTTP) | `.devin/mcp_config.json` |

---

## 6. Schemas

| Schema | File | Purpose |
|--------|------|---------|
| Tool registry | `.devin/tool_registry.json` | 7 tools |
| Skill index | `.devin/skills/skill_index.json` | 26 skills progressive |
| Hook hashes | `.devin/hook_hashes.json` | 51 hooks SHA256 |
| Hook order | `.devin/hook_order.json` | 10 hooks canonical order |
| MCP config | `.devin/mcp_config.json` | 4 MCP servers |

---

## 7. Shell / Code Executor

| Executor | Access | Constraints |
|----------|--------|-------------|
| Bash (PowerShell) | Full workspace | Pre-tool hooks enforce governance |
| Python scripts | `.devin/scripts/` | Deterministic gates, no LLM judgment |
| Hook chain | Pre→Post | 10 hooks in canonical order |

---

## 8. Filesystem / Network

| Resource | Access | Policy |
|----------|--------|--------|
| Workspace files | Read/Write | Governance: safe zones only (src/, .devin/scripts/, .devin/agents/, tests/, tools/, docs/plans/) |
| Root markdown | Blocked | Pre-tool hook blocks new .md at root |
| Network | None by default | MCP servers only via config |
| HLK/ | Read-only | Canonical verify-first chain |
| .env | Blocked | No secrets in logs/state |

---

## 9. Secrets / AuthN / AuthZ

| Secret Type | Storage | Protection |
|-------------|---------|------------|
| API keys | Not in workspace | `.env` gitignored, pre_tool_secrets.py blocks |
| MCP tokens | MCP config | Not in repo |
| Git credentials | OS keychain | Not in workspace |

---

## 10. Memory / RAG / Cache / Persistence

| Layer | Location | Cap | BOOT |
|-------|----------|-----|------|
| Hot Registry | `.devin/loop_state.md` | <3KB | Required |
| Hot Session (human) | `.devin/loop_state/<sid>.md` | <8KB | Current only |
| Hot Session (machine) | `.devin/session_state/<sid>.json` | <8KB | Audit only |
| Knowledge | `.agents/knowledge_distill.md` | <8KB | Required |
| Cold Archive | `.devin/loop_state_archive/` | ∞ | Grep only |
| Aide-memory | MCP (local) | Persistent | On-demand |
| Spark-memory | MCP (remote) | Shared | On-demand |

---

## 11. Tenant / Session

| Concept | Implementation |
|---------|----------------|
| Session ID | `loop_memory_sync.py` generates |
| Context flags | `.devin/context_flags/<sid>.json` |
| Caveman levels | light|compact|full|ultra|wenyan |

---

## 12. CI / CD

| Pipeline | Trigger | Gates |
|----------|---------|-------|
| Pre-commit | Git commit | Redaction, Junk scan, .gitignore audit, Governance |
| CI (GitHub Actions) | Push/PR | Junk scan, .gitignore audit, Governance check |

---

## 13. Dependency / Model / Plugin Supply Chain

| Source | Pinned | Verification |
|--------|--------|--------------|
| Python deps | `requirements-lock.txt` (hash-pinned) | `uv pip compile --generate-hashes` |
| filelock | Pinned `<3.13` | Dependabot ignore |
| pydantic-core | Pinned `==` by pydantic | Bump together |
| Skills | Vendored (git submodule or copy) | REPOS.md tracks upstream |
| HLK | Submodule | `hlk-integrity-check` skill |

---

## 14. Telemetry

| Metric | Collector |
|--------|-----------|
| Hook integrity | `hook_integrity.py --verify` |
| Context projection | `context_projection.py --report` |
| Cost tracking | `cost_tracker.py` / `cost_ledger.py` |
| Plan quality | `plan_quality_check.py` |

---

## 15. Test / Eval / Scorer

| Test Type | Location | Status |
|-----------|----------|--------|
| Unit/Integration | `tests/` | ⚠️ Conftest error (pre-existing) |
| Hook tests | `tests/test_hook_integrity.py` | Importable |
| Plan tests | `tests/test_plan_*.py` | Importable |

---

## 16. Deployment / Rollback

| Mechanism | Description |
|-----------|-------------|
| Git | Source of truth |
| Worktree | `.devin/scripts/worktree.py` for isolation |
| Snapshot | `loop_state_archive` for rollback |
| Hook baseline | `hook_hashes.json` for integrity |

---

## UNVERIFIED-ASPIRATIONAL Items

| Component | Claim | Evidence? |
|-----------|-------|-----------|
| `auto_model_router.py` | Routes to optimal model | No benchmark evidence |
| `nuwa_roi.py` | Measures Nuwa ROI | No runs recorded |
| `adversarial-consensus` skill | 6+ persona review | No execution trace this session |
| `fable-judge` skill | Adversarial done-gate | No run this session |

## PARITY-GAP Items

| Human Knowledge | Agent Accessible? | Gap |
|-----------------|-------------------|-----|
| "pytest conftest has null bytes" | ❌ Not in any file | Info-parity gap |
| "HLK integrity check needed" | ❌ Not in canon | Info-parity gap |
| "No sandbox for red-team" | ❌ Not documented | Info-parity gap |

---

## Next Phase

→ Identity/Delegation Map → Threat Model → Attack Matrix