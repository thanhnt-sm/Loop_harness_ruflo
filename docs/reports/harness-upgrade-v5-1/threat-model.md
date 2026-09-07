# Threat Model — V5 Red-Team Iteration 1

**Generated**: 2026-09-04
**Mode**: AUDIT_ONLY (static analysis)
**Taxonomy**: OWASP LLM Top 10 (2025), MITRE ATLAS, NIST AI 100-2

---

## Asset Inventory (from component-map.md)

| Asset | Type | Sensitivity | Criticality |
|-------|------|-------------|-------------|
| AGENTS.md / CLAUDE.md | Config/Rule | High | Critical |
| Canon files | Rule/Protocol | High | Critical |
| Hook chain (51) | Enforcement | High | Critical |
| Skill index (26) | Capability | Medium | High |
| Tool registry (7) | Action | Medium | High |
| Session state | Runtime state | Medium | Medium |
| Knowledge distill | Learned patterns | Low | Medium |
| MCP configs | Integration | Medium | High |

---

## Attack Families (OWASP Agentic AI / MITRE ATLAS)

### A. Goal/Instruction Hijacking

| Vector | Asset | Likelihood | Impact | Notes |
|--------|-------|------------|--------|-------|
| Direct injection | AGENTS.md, skills | Medium | High | User prompt could override rules |
| Indirect injection | Canon files, skills | Medium | High | Retrieved docs could contain injection |
| Hierarchy conflict | REDLINES vs canon | Low | High | Conflicting rules at different layers |
| Context smuggling | Skill bodies | Low | Medium | Large skill bodies could hide instructions |
| Multi-turn drift | Loop protocol | Medium | Medium | Long loops accumulate drift |

### B. Identity/Delegation

| Vector | Asset | Likelihood | Impact | Notes |
|--------|-------|------------|--------|-------|
| Confused deputy | Hook chain | Low | High | Hooks run with agent perms |
| Privilege inheritance | Subagent dispatch | Medium | High | Subagents inherit parent perms |
| Scope escalation | Tool registry | Low | High | Tool permissions not scoped per-task |
| Audience confusion | MCP servers | Low | Medium | MCP config not validated per-call |
| Stale approval | Plan approval gate | Medium | Medium | Approved plan may not match execution |
| Revocation lag | No identity service | High | High | **No revocation infrastructure** |

### C. Tool/MCP

| Vector | Asset | Likelihood | Impact | Notes |
|--------|-------|------------|--------|-------|
| Tool poisoning | Skill triggers | Medium | High | Malicious skill could register |
| Schema mutation | Tool registry | Low | High | Registry not immutable |
| Token passthrough | MCP servers | N/A | N/A | No MCP tokens in workspace |
| Consent bypass | Hook chain | Low | High | Pre-tool hooks mandatory |
| SSRF/egress | Network access | N/A | N/A | No network by default |

### D. Memory/RAG/State

| Vector | Asset | Likelihood | Impact | Notes |
|--------|-------|------------|--------|-------|
| Poisoning | Knowledge distill | Medium | Medium | Distilled patterns could be wrong |
| Cross-session leakage | Aide-memory | Low | Medium | Scope per-file, but MCP shared |
| Stale authorization | Session state | Medium | Medium | State not auto-expired |
| Replay | Loop archive | Low | Low | Archive is append-only |
| Retrieval trust confusion | Memory search | Low | Medium | No trust grading in search |
| Cache bleed | Context flags | Low | Low | Per-session isolation |
| Deletion failure | Candidate memory | Low | Low | Auto-cleared on distillation |
| Unbounded retention | Loop archive | Medium | Low | Archive grows forever |

### E. Flow/Control

| Vector | Asset | Likelihood | Impact | Notes |
|--------|-------|------------|--------|-------|
| Fail-open | Plan enforce hook | Low | High | Hook blocks on error (fail-closed) |
| Bypass | Governance hooks | Medium | High | Model could edit hook files |
| Race condition | Parallel dispatch | Low | Medium | Worktree isolation mitigates |
| Timeout/cancel failure | Loop protocol | Medium | Medium | No hard timeout enforcement |
| Infinite loop | Loop protocol | Low | Medium | Stop conditions + idle-yank |
| Non-deterministic approval | Approval gate | Low | High | Human approval required for M+ |
| Policy service outage | Hook chain | Low | High | Hooks local, no external deps |

### F. Supply Chain

| Vector | Asset | Likelihood | Impact | Notes |
|--------|-------|------------|--------|-------|
| Unpinned dependency | requirements-lock.txt | **High** | **High** | **filelock <3.13 pin, pydantic-core == pin** |
| Malicious skill/plugin | Vendored skills | Medium | High | nuwa-skill vendored, no SBOM |
| Transitive dependency | Python deps | Medium | High | Lockfile hash-pinned but not verified |
| Unsigned artifact | Skills/canon | Medium | Medium | No signature verification |
| Missing SBOM | SBOM | Medium | Medium | `sbom/python.sbom.json` exists |
| Install script execution | None | N/A | N/A | No install scripts |

### G. Governance/Ops

| Vector | Asset | Likelihood | Impact | Notes |
|--------|-------|------------|--------|-------|
| Sprawl | All assets | Low | Medium | All assets registered |
| Missing owner/expiry | All assets | Low | Medium | All have owner, no expiry |
| Audit gap | Hook integrity | Low | High | Baseline verified, but no continuous audit |
| Model/tool drift | Auto router | Medium | Medium | No drift detection for model behavior |
| Unsafe auto-merge | Git hooks | N/A | N/A | No auto-merge configured |
| Cost/resource exhaustion | Cost tracker | Low | Medium | Budget caps in loop protocol |
| Rollback failure | Worktree/snapshot | Low | Medium | Snapshot exists, not tested |

---

## Critical Invariants (from V5 protocol §9)

| Invariant ID | Statement | Asset | Threat | PDP | PEP | Test ID | Status |
|--------------|-----------|-------|--------|-----|-----|---------|--------|
| INV-01 | Data plane cannot become authoritative instruction | All canon/skills | D, E | Hook chain | Pre-tool hooks | hook_integrity | ✅ Verified |
| INV-02 | Agent cannot self-grant permissions | Tool registry | B | Plan enforce | Plan enforce hook | plan_enforce test | ✅ Verified |
| INV-03 | Model output never goes straight to shell/executor | Bash tool | C, E | Hook chain | Pre-tool hooks | pre_tool_use test | ✅ Verified |
| INV-04 | Tool auth binds actor, delegation, action, resource, audience, scope, data class, env, time, approval | Tool registry | B, C | Plan enforce | Plan enforce hook | plan_enforce test | ⚠️ Partial |
| INV-05 | Memory bound tenant/session/principal, provenance/TTL, auth-at-read, deletion test | Memory layers | D | Memory protocol | Memory audit hook | memory_audit test | ⚠️ Partial |
| INV-06 | Side effect has actor, purpose, exact target/params, policy decision, trace ID, receipt | All writes | E | Hook chain | Post-tool hooks | post_tool_use test | ✅ Verified |
| INV-07 | Unknown/policy/validator/telemetry failure → fail-closed for high-risk | All hooks | E | Hook chain | Hook chain | hook_integrity test | ✅ Verified |
| INV-08 | Model/tool/schema/dependency/MCP/agent registry drift → evidence stale | All registries | G | Skill index | Skill index | skill_index test | ⚠️ Not implemented |

---

## Risk Summary

| Severity | Count | Examples |
|----------|-------|----------|
| **Critical** | 2 | No revocation infrastructure (B.6), Unpinned filelock/pydantic-core (F.1) |
| **High** | 5 | Tool poisoning (C.1), Memory poisoning (D.1), Supply chain (F.1), Model drift (G.4), Scope escalation (B.3) |
| **Medium** | 12 | Injection vectors (A), Delegation (B), Memory (D), Flow (E), Supply (F.2-4), Governance (G.2-6) |
| **Low** | 8 | SSRF (C.4), Replay (D.4), Archive growth (D.8), etc. |

---

## Next Phase

→ Attack Matrix (concrete PoC for Critical/High) → Root Cause Analysis