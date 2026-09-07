# Identity / Delegation Map — V5 Iteration 1

**Generated**: 2026-09-04
**Mode**: AUDIT_ONLY (no active identity service)

---

## Identity Chain (Human → Agent → Tool)

```
human_principal (user)
  → client (opencode CLI)
    → agent_identity (active model: nemotron-3-ultra-free)
      → proxy/delegator (orchestrator: plan_orchestrator.py)
        → tool/MCP_server (hooks, scripts, skills)
          → downstream_resource (workspace files, git, MCP servers)
```

---

## Hop-by-Hop Delegation

| Hop | Subject | Issuer | Audience/Resource | Scope | Delegation | Expiry | Revocation Source | Consent | Purpose | Policy Decision |
|-----|---------|--------|-------------------|-------|------------|--------|-------------------|---------|---------|-----------------|
| 1 | user | — | opencode CLI | workspace | full | session | user | explicit | harness upgrade | ALLOW |
| 2 | opencode | user | nemotron-3-ultra-free | planning/review | planning | session | user | explicit | orchestrate upgrade | ALLOW |
| 3 | nemotron | opencode | plan_orchestrator.py | plan FSM | execution | task | opencode | implicit | run upgrade phases | ALLOW |
| 4 | plan_orchestrator | nemotron | hooks/scripts/skills | deterministic gates | execution | task | nemotron | implicit | verify, measure, compress | ALLOW |
| 5 | hooks | plan_orchestrator | workspace files | governance | enforcement | hook call | plan_orchestrator | implicit | block violations | ALLOW |
| 6 | scripts | plan_orchestrator | canon/skills | measurement | execution | script call | plan_orchestrator | implicit | project context, report | ALLOW |
| 7 | skills | plan_orchestrator | task protocols | guidance | invocation | skill call | plan_orchestrator | implicit | adversarial, tdd, etc. | ALLOW |

---

## Asset Registry (from registry.json)

| Asset ID | Owner | Identity | Permissions | Expiry | Revocation | Status |
|----------|-------|----------|-------------|--------|------------|--------|
| hook:pre_tool_use | AHD | hook | read,write,bash | none | hook_integrity.py | active |
| hook:plan_enforce | AHD | hook | read,write,bash | none | hook_integrity.py | active |
| skill:harness-upgrade | AHD | skill | read,write,bash,glob,grep | none | skill_index.json | active |
| canon:CORE_CANON | AHD | canon | read | none | context_projection | active |
| tool:context_projection | AHD | script | read,bash | none | hook_integrity.py | active |
| mcp:aide-memory | Devin | mcp_server | read,write | none | MCP config | active |

---

## Revocation Bound Analysis

**No identity service present** — revocation bound cannot be verified.
- No token refresh mechanism visible
- No credential revocation endpoint configured
- No queued job / in-flight request tracking for revocation

**Finding**: `REVOCATION_BOUND` = **UNVERIFIED** — infrastructure missing.

---

## Agent Sprawl Check

| Asset | Owner | Registered | Expiry | Permission Review | Status |
|-------|-------|------------|--------|-------------------|--------|
| 51 hooks | AHD | ✅ | none | ✅ (baseline) | ✅ |
| 26 skills | AHD | ✅ | none | ✅ (skill_index) | ✅ |
| 12 canon | AHD | ✅ | none | ✅ (boot/ondemand) | ✅ |
| 7 tools | AHD | ✅ | none | ✅ (registry) | ✅ |
| 4 MCP | Devin | ✅ | none | ⚠️ config only | active |

**No sprawl detected** — all assets have owner, registration, no expiry.

---

## Control Plane vs Data Plane

| Plane | Components | Separation Enforced? |
|-------|------------|---------------------|
| CONTROL_PLANE | Hooks, plan_enforce, schema_gate, coverage_enforce, approval_gate, skill_index, hook_order, tool_registry | ✅ Hooks enforce |
| DATA_PLANE | AGENTS.md, canon files, skill bodies, session_state, loop_state, knowledge_distill | ✅ Read-only at BOOT |

**Data plane → Control plane write?** No — session_state written by hooks (control plane), not by data plane content.

---

## Next Phase

→ Threat Model (PHASE 10) → Attack Matrix (PHASE 10)