# Attack Report — V5 Red-Team Iteration 1 (AUDIT_ONLY)

**Generated**: 2026-09-04
**Mode**: Static analysis only (no sandbox, no active execution)
**Taxonomy**: OWASP LLM Top 10, MITRE ATLAS

---

## Attack Vector Results

### CRITICAL FINDINGS

#### ATT-001: No Revocation Infrastructure (B.6)
| Field | Value |
|-------|-------|
| **Attack ID** | ATT-001 |
| **Taxonomy** | MITRE ATLAS: AML.T0015 (ML Supply Chain), OWASP LLM06 |
| **Asset** | Identity/Delegation chain |
| **Attacker Capability** | Compromised agent/session token |
| **Preconditions** | Agent has valid delegation, no revocation check |
| **Safe Fixture** | N/A (static analysis) |
| **Input** | Simulated: agent continues after human revokes consent |
| **Expected Invariant** | `REVOCATION_BOUND`: all high-risk permissions blocked within bound |
| **Deterministic Oracle** | Check revocation endpoint exists + hook enforces |
| **Observed Result** | **NO REVOCATION INFRASTRUCTURE** — no endpoint, no hook check, no token refresh tracking |
| **Side Effect** | Compromised agent retains permissions indefinitely |
| **Evidence** | identity-delegation-map.md: "REVOCATION_BOUND = UNVERIFIED" |
| **Severity** | **CRITICAL** |
| **Stop Condition** | Revocation service deployed + hook enforcement |
| **Status** | **OPEN** |

**Root Cause Hypothesis (Architectural)**: Delegation model assumes static permissions. No identity service, no token lifecycle, no revocation bound enforcement. This is a **STRUCTURAL** root cause — requires redesign of permission model.

---

#### ATT-002: Unpinned Critical Dependencies (F.1) — filelock & pydantic-core
| Field | Value |
|-------|-------|
| **Attack ID** | ATT-002 |
| **Taxonomy** | MITRE ATLAS: AML.T0015, OWASP LLM03 |
| **Asset** | Python dependency chain (`requirements-lock.txt`) |
| **Attacker Capability** | Malicious package publish / dependency confusion |
| **Preconditions** | Dependency resolver picks unpinned version |
| **Safe Fixture** | `requirements-lock.txt` inspection |
| **Input** | `filelock` allows >=3.13 (eager asyncio import breaks hook timeout), `pydantic-core` allows != pydantic version |
| **Expected Invariant** | All deps hash-pinned; `filelock <3.13`, `pydantic-core ==` pydantic version |
| **Deterministic Oracle** | `pip check` + `tools/check_deps.py` |
| **Observed Result** | **PINS EXIST BUT NOT ENFORCED IN HOOK** — `filelock` has comment in pyproject.toml, `pydantic-core` pinned by `pydantic` but not independently verified |
| **Side Effect** | Hook timeout (2.5s) broken by filelock 3.13+; ResolutionImpossible by pydantic-core mismatch |
| **Evidence** | pyproject.toml comments, `.github/dependabot.yml` ignore |
| **Severity** | **CRITICAL** |
| **Stop Condition** | Hook enforces pin verification on every install |
| **Status** | **OPEN** |

**Root Cause Hypothesis (Mechanical)**: Pin comments in pyproject.toml are documentation, not enforcement. `tools/check_deps.py` exists but not in pre-commit hook chain. This is a **MECHANICAL** root cause — needs enforcement hook.

---

### HIGH FINDINGS

#### ATT-003: Tool Poisoning via Skill Registration (C.1)
| Field | Value |
|-------|-------|
| **Attack ID** | ATT-003 |
| **Taxonomy** | OWASP LLM01, MITRE ATLAS: AML.T0002 |
| **Asset** | Skill index / tool registry |
| **Attacker Capability** | Write access to `.devin/skills/` |
| **Preconditions** | Malicious skill file added |
| **Safe Fixture** | Static skill_index.json scan |
| **Input** | Skill with hidden destructive trigger |
| **Expected Invariant** | Skill triggers validated against allowlist |
| **Deterministic Oracle** | `skill_index.json` schema validation |
| **Observed Result** | **NO TRIGGER VALIDATION** — skill_index.json accepts any trigger string |
| **Side Effect** | Malicious skill could hijack task routing |
| **Severity** | **HIGH** |
| **Status** | **OPEN** |

**Root Cause**: Skill triggers not validated against known-safe patterns. **STRUCTURAL** — needs trigger schema.

---

#### ATT-004: Memory Poisoning via Knowledge Distill (D.1)
| Field | Value |
|-------|-------|
| **Attack ID** | ATT-004 |
| **Taxonomy** | OWASP LLM02, MITRE ATLAS: AML.T0003 |
| **Asset** | `.agents/knowledge_distill.md` |
| **Attacker Capability** | Write to knowledge distill |
| **Preconditions** | Memory keeper or distillation writes wrong pattern |
| **Safe Fixture** | Static analysis of distillation logic |
| **Input** | Incorrect "correct_action" distilled |
| **Expected Invariant** | Distillation validates trigger+action+counter |
| **Deterministic Oracle** | `memory_audit.py --session <sid>` validation |
| **Observed Result** | **VALIDATION EXISTS** (`memory_audit.py` checks trigger+action+counter) but not run automatically |
| **Side Effect** | Wrong patterns persist, mislead future agents |
| **Severity** | **HIGH** |
| **Status** | **PARTIAL** (validation exists, not automated) |

**Root Cause**: `memory_audit.py` validates but not hooked into mandatory gate. **MECHANICAL** — needs hook enforcement.

---

#### ATT-005: Supply Chain — Vendored nuwa-skill No SBOM (F.2)
| Field | Value |
|-------|-------|
| **Attack ID** | ATT-005 |
| **Taxonomy** | MITRE ATLAS: AML.T0015, OWASP LLM03 |
| **Asset** | `.devin/skills/nuwa-skill/` (vendored from alchaincyf/nuwa-skill) |
| **Attacker Capability** | Upstream compromise |
| **Preconditions** | Upstream repo compromised |
| **Safe Fixture** | REPOS.md tracking |
| **Input** | Vendored copy not verified against upstream |
| **Expected Invariant** | SBOM/provenance verification before vendoring |
| **Deterministic Oracle** | `cosign verify` + SBOM check |
| **Observed Result** | **NO SBOM VERIFICATION** — vendored at commit `27642f5`, no signature/provenance check |
| **Side Effect** | Compromised upstream → compromised workspace |
| **Severity** | **HIGH** |
| **Status** | **OPEN** |

**Root Cause**: Vendoring process lacks provenance verification. **STRUCTURAL** — needs supply chain gate.

---

#### ATT-006: Model/Tool Drift Detection Missing (G.4)
| Field | Value |
|-------|-------|
| **Attack ID** | ATT-006 |
| **Taxonomy** | OWASP LLM04, MITRE ATLAS: AML.T0019 |
| **Asset** | `auto_model_router.py`, `skill_index.json` |
| **Attacker Capability** | Model behavior change / tool schema change |
| **Preconditions** | Model provider updates, tool schema drifts |
| **Safe Fixture** | Baseline behavior snapshots |
| **Input** | Model produces different output for same prompt |
| **Expected Invariant** | Drift detection + alert |
| **Deterministic Oracle** | `drift_detect.py` hook |
| **Observed Result** | **`drift_detect.py` EXISTS** but not in canonical hook chain |
| **Side Effect** | Silent behavior degradation |
| **Severity** | **HIGH** |
| **Status** | **PARTIAL** (detector exists, not enforced) |

**Root Cause**: Drift detector not in mandatory hook chain. **MECHANICAL** — needs hook integration.

---

#### ATT-007: Scope Escalation — Tool Permissions Not Task-Scoped (B.3)
| Field | Value |
|-------|-------|
| **Attack ID** | ATT-007 |
| **Taxonomy** | OWASP LLM06, MITRE ATLAS: AML.T0016 |
| **Asset** | Tool registry (7 tools), plan_enforce |
| **Attacker Capability** | Task requests broader permissions |
| **Preconditions** | Plan approve grants broad permissions |
| **Safe Fixture** | Plan approval gate |
| **Input** | Task requests `write` when only `read` needed |
| **Expected Invariant** | Least-privilege per task |
| **Deterministic Oracle** | Plan enforce checks task scope vs tool perms |
| **Observed Result** | **PLAN ENFORCE EXISTS** but tool permissions not scoped per-task |
| **Side Effect** | Over-privileged tasks |
| **Severity** | **HIGH** |
| **Status** | **OPEN** |

**Root Cause**: Tool registry is global, not task-scoped. **STRUCTURAL** — needs permission model redesign.

---

### MEDIUM FINDINGS (Summary)

| ID | Vector | Asset | Status |
|----|--------|-------|--------|
| ATT-008 | Direct injection (A.1) | AGENTS.md, skills | OPEN |
| ATT-009 | Indirect injection (A.2) | Canon, skills | OPEN |
| ATT-010 | Hierarchy conflict (A.3) | REDLINES vs canon | OPEN |
| ATT-011 | Confused deputy (B.1) | Hook chain | OPEN |
| ATT-012 | Privilege inheritance (B.2) | Subagent dispatch | OPEN |
| ATT-013 | Stale approval (B.5) | Plan approval gate | OPEN |
| ATT-014 | Schema mutation (C.2) | Tool registry | OPEN |
| ATT-015 | Cross-session leakage (D.2) | Aide-memory | OPEN |
| ATT-016 | Stale authorization (D.3) | Session state | OPEN |
| ATT-017 | Fail-open (E.1) | Plan enforce hook | VERIFIED FAIL-CLOSED |
| ATT-018 | Bypass (E.2) | Governance hooks | OPEN |
| ATT-019 | Timeout failure (E.4) | Loop protocol | OPEN |
| ATT-020 | Unsafe auto-merge (G.5) | Git hooks | N/A (not configured) |
| ATT-021 | Cost exhaustion (G.6) | Cost tracker | OPEN |

---

## Root Cause Classification

| Attack | Root Cause Type | Evidence |
|--------|----------------|----------|
| ATT-001 (No revocation) | **STRUCTURAL** | No identity service, no token lifecycle |
| ATT-002 (Unpinned deps) | **MECHANICAL** | check_deps.py exists, not in hook chain |
| ATT-003 (Tool poisoning) | **STRUCTURAL** | No trigger schema validation |
| ATT-004 (Memory poisoning) | **MECHANICAL** | memory_audit.py validates, not hooked |
| ATT-005 (Supply chain) | **STRUCTURAL** | No provenance verification in vendoring |
| ATT-006 (Drift detection) | **MECHANICAL** | drift_detect.py exists, not in hook chain |
| ATT-007 (Scope escalation) | **STRUCTURAL** | Global tool registry, not task-scoped |

---

## Next Phase

→ Research (PHASE 13) → Solution Matrix → Plan (PHASE 14)