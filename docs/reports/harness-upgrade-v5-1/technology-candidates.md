# Technology Candidates — V5 Iteration 1 Research

**Generated**: 2026-09-04
**Mode**: AUDIT_ONLY — Online research per root cause

---

## RC-001: No Revocation Infrastructure (STRUCTURAL)

### Root Cause
Permission model lacks delegation lifecycle: expiry, revocation_source, revocation_bound enforcement.

### Candidate Solutions

| Candidate | Root Cause | Remedy Class | Source | Access Date | Release/Commit | Maintainer Signal | Tests/Evals | License | Dependencies | SBOM/Provenance | Security History | Compatibility | Cost | Failure Modes | Migration | Recommendation | Confidence | Expiry |
|-----------|------------|--------------|--------|-------------|----------------|-------------------|-------------|---------|--------------|-----------------|------------------|---------------|------|---------------|-----------|----------------|------------|--------|
| **Local Token Registry + Hook Enforcement** | No revocation infra | Infrastructure add | Self-designed | 2026-09-04 | N/A | Internal | Unit tests for hook | MIT | None | N/A | N/A | High (pure Python) | Low (dev time) | Hook bypass if not in chain | Add to pre_tool_use | **RECOMMENDED** — minimal, fits harness | 0.85 | 2026-12-04 |
| **OPA (Open Policy Agent)** | No revocation infra | External policy engine | https://www.openpolicyagent.org/ | 2026-09-04 | v0.68.0 | Active (CNCF graduated) | Extensive | Apache-2.0 | Go binary | Yes | Good | Medium (external dep) | Medium | External service failure | Replace hook auth with OPA | Consider for Phase 2 | 0.70 | 2026-12-04 |
| **SPIFFE/SPIRE** | No revocation infra | Identity framework | https://spiffe.io/ | 2026-09-04 | v1.8.0 | Active (CNCF) | Integration tests | Apache-2.0 | Multiple | Yes | Good | Low (complex) | High | Overkill for local harness | Not recommended now | 0.30 | 2026-12-04 |
| **Custom JWT + Revocation List** | No revocation infra | Token-based | Self-designed | 2026-09-04 | N/A | Internal | Unit tests | MIT | pyjwt | N/A | N/A | High | Low | Token replay | Add to delegation chain | Alternative to local registry | 0.75 | 2026-12-04 |

### Comparison: Eliminates Root Cause?

| Candidate | Eliminates Root Cause? | Notes |
|-----------|----------------------|-------|
| Local Token Registry + Hook | **YES** — adds expiry/revocation_source to permission, hook checks revocation_list per call | Minimal, deterministic, no external deps |
| OPA | **YES** — policy engine evaluates revocation per request | Adds external dependency, overkill |
| SPIFFE/SPIRE | **YES** — full identity framework | Massive overkill |
| Custom JWT | **YES** — token carries expiry, revocation list checked | Similar to local registry, more complex |

**Selected**: **Local Token Registry + Hook Enforcement** — minimal, deterministic, fits "weak model + small context" constraint.

---

## RC-002: Dependency Pins Not Enforced (MECHANICAL)

### Root Cause
`tools/check_deps.py` exists but not in pre-commit hook chain or pre_tool_use for pip/uv.

### Candidate Solutions

| Candidate | Root Cause | Remedy Class | Source | Access Date | Release/Commit | Maintainer Signal | Tests/Evals | License | Dependencies | SBOM/Provenance | Security History | Compatibility | Cost | Failure Modes | Migration | Recommendation | Confidence | Expiry |
|-----------|------------|--------------|--------|-------------|----------------|-------------------|-------------|---------|--------------|-----------------|------------------|---------------|------|---------------|-----------|----------------|------------|--------|
| **Add check_deps.py to pre-commit (Gate 5)** | Not enforced | Hook enforcement | Self-designed | 2026-09-04 | N/A | Internal | Existing tests | MIT | None | N/A | N/A | High | Very Low | False positives on legit deps | Edit `.githooks/pre-commit` | **RECOMMENDED** — immediate fix | 0.95 | 2026-12-04 |
| **Add check_deps.py to pre_tool_use for pip/uv** | Not enforced at runtime | Hook enforcement | Self-designed | 2026-09-04 | N/A | Internal | Existing tests | MIT | None | N/A | N/A | High | Very Low | Blocks legitimate installs | Edit `pre_tool_use.py` | **RECOMMENDED** — defense in depth | 0.90 | 2026-12-04 |
| **uv pip compile --generate-hashes enforcement** | Lockfile drift | CI gate | uv docs | 2026-09-04 | uv 0.5+ | Active | CI tests | MIT | uv | N/A | Good | High | Low | CI failure on drift | Add to CI workflow | Additional safety | 0.85 | 2026-12-04 |

### Comparison: Eliminates Root Cause?

| Candidate | Eliminates Root Cause? | Notes |
|-----------|----------------------|-------|
| Pre-commit gate | **YES** — blocks commit with unpinned deps | Immediate, zero runtime cost |
| Pre-tool-use gate | **YES** — blocks `pip install` / `uv add` with bad pins | Defense in depth |
| CI gate | **YES** — catches drift in CI | Catches missed local |

**Selected**: **All three** — defense in depth (pre-commit + pre-tool-use + CI).

---

## RC-003: Skill Trigger Validation (STRUCTURAL)

### Root Cause
Skill triggers free-text, no schema validation, no trusted/untrusted namespace.

### Candidate Solutions

| Candidate | Root Cause | Remedy Class | Source | Access Date | Release/Commit | Maintainer Signal | Tests/Evals | License | Dependencies | SBOM/Provenance | Security History | Compatibility | Cost | Failure Modes | Migration | Recommendation | Confidence | Expiry |
|-----------|------------|--------------|--------|-------------|----------------|-------------------|-------------|---------|--------------|-----------------|------------------|---------------|------|---------------|-----------|----------------|------------|--------|
| **Trigger Schema (regex allowlist) + Core/Dynamic Namespace** | No validation | Schema + Namespace | Self-designed | 2026-09-04 | N/A | Internal | Unit tests | MIT | None | N/A | N/A | High | Low | Blocks valid dynamic triggers | Refactor skill_index.json | **RECOMMENDED** | 0.85 | 2026-12-04 |
| **JSON Schema for skill_index.json** | No validation | Schema validation | JSON Schema | 2026-09-04 | draft-2020-12 | Standard | Validators exist | N/A | jsonschema | N/A | N/A | High | Low | Schema evolution | Add validation script | Alternative | 0.80 | 2026-12-04 |
| **Skill Signing (cosign)** | Untrusted skills | Provenance | cosign | 2026-09-04 | v2.4+ | Active | CLI tests | Apache-2.0 | cosign, fulcio | Yes | Good | Medium | Medium | Key management | Sign core skills | Phase 2 | 0.65 | 2026-12-04 |

### Comparison: Eliminates Root Cause?

| Candidate | Eliminates Root Cause? | Notes |
|-----------|----------------------|-------|
| Trigger Schema + Namespace | **YES** — core skills validated triggers, dynamic skills reviewed | Minimal, deterministic |
| JSON Schema | **PARTIAL** — validates structure, not semantic trigger safety | Needs custom validators |
| Skill Signing | **YES** — proves provenance, but doesn't validate trigger content | Complementary |

**Selected**: **Trigger Schema + Core/Dynamic Namespace** — addresses both validation and trust.

---

## RC-004: Memory Write Gate (MECHANICAL)

### Root Cause
`memory_audit.py` validates but not hooked as mandatory gate.

### Candidate Solutions

| Candidate | Root Cause | Remedy Class | Source | Access Date | Release/Commit | Maintainer Signal | Tests/Evals | License | Dependencies | SBOM/Provenance | Security History | Compatibility | Cost | Failure Modes | Migration | Recommendation | Confidence | Expiry |
|-----------|------------|--------------|--------|-------------|----------------|-------------------|-------------|---------|--------------|-----------------|------------------|---------------|------|---------------|-----------|----------------|------------|--------|
| **Post-tool hook for knowledge_distill writes** | Not automated | Hook enforcement | Self-designed | 2026-09-04 | N/A | Internal | Existing tests | MIT | None | N/A | N/A | High | Very Low | False reject valid patterns | Add to post_tool_use.py | **RECOMMENDED** | 0.90 | 2026-12-04 |
| **Fable-judge gate for memory writes** | Maker≠checker | Independent verify | fable-judge skill | 2026-09-04 | skill exists | Internal | Skill tests | MIT | fable-judge | N/A | N/A | Medium | Medium | Slow (LLM call) | Add to memory_audit.py | Defense in depth | 0.75 | 2026-12-04 |
| **Claim-grader for memory claims** | Evidence grading | Evidence grade | claim-grader skill | 2026-09-04 | skill exists | Internal | Skill tests | MIT | claim-grader | N/A | N/A | Medium | Low | Extra LLM call | Add to memory_audit.py | Lightweight alternative | 0.80 | 2026-12-04 |

### Comparison: Eliminates Root Cause?

| Candidate | Eliminates Root Cause? | Notes |
|-----------|----------------------|-------|
| Post-tool hook | **YES** — runs validation on every knowledge_distill write | Deterministic, fast |
| Fable-judge | **YES** — independent adversarial review | Slow, probabilistic |
| Claim-grader | **YES** — grades evidence quality | Fast, deterministic-ish |

**Selected**: **Post-tool hook (deterministic) + Claim-grader (evidence grading)** — layered defense.

---

## RC-005: Supply Chain Provenance (STRUCTURAL)

### Root Cause
Vendoring process lacks cosign/SBOM verification.

### Candidate Solutions

| Candidate | Root Cause | Remedy Class | Source | Access Date | Release/Commit | Maintainer Signal | Tests/Evals | License | Dependencies | SBOM/Provenance | Security History | Compatibility | Cost | Failure Modes | Migration | Recommendation | Confidence | Expiry |
|-----------|------------|--------------|--------|-------------|----------------|-------------------|-------------|---------|--------------|-----------------|------------------|---------------|------|---------------|-----------|----------------|------------|--------|
| **update_from_repos: cosign verify + SBOM check** | No provenance gate | Supply chain gate | update_from_repos skill | 2026-09-04 | skill exists | Internal | Skill tests | MIT | cosign, sbom | Yes | Good | Medium | Low | Blocks unsigned vendors | Edit skill | **RECOMMENDED** | 0.85 | 2026-12-04 |
| **REPOS.md provenance fields** | Tracking only | Metadata | Self-designed | 2026-09-04 | N/A | Internal | N/A | N/A | None | N/A | N/A | High | Very Low | Not enforcement | Edit REPOS.md | Required metadata | 0.90 | 2026-12-04 |
| **SLSA Level 3** | Full supply chain | Framework | slsa.dev | 2026-09-04 | v1.0 | Active | Framework | Apache-2.0 | Multiple | Yes | Excellent | Low | High | Complex adoption | Long-term | Phase 3 | 0.50 | 2026-12-04 |

### Comparison: Eliminates Root Cause?

| Candidate | Eliminates Root Cause? | Notes |
|-----------|----------------------|-------|
| cosign + SBOM in update_from_repos | **YES** — verifies before vendor | Automated gate |
| REPOS.md provenance fields | **PARTIAL** — tracks, doesn't enforce | Required for audit |
| SLSA Level 3 | **YES** — full framework | Overkill for now |

**Selected**: **update_from_repos cosign/SBOM gate + REPOS.md provenance fields** — automated + auditable.

---

## RC-006: Drift Detection Not in Hook Chain (MECHANICAL)

### Root Cause
`drift_detect.py` exists but not in mandatory hook chain.

### Candidate Solutions

| Candidate | Root Cause | Remedy Class | Source | Access Date | Release/Commit | Maintainer Signal | Tests/Evals | License | Dependencies | SBOM/Provenance | Security History | Compatibility | Cost | Failure Modes | Migration | Recommendation | Confidence | Expiry |
|-----------|------------|--------------|--------|-------------|----------------|-------------------|-------------|---------|--------------|-----------------|------------------|---------------|------|---------------|-----------|----------------|------------|--------|
| **Add drift_detect.py to post_tool_use chain** | Not in hook chain | Hook enforcement | Self-designed | 2026-09-04 | N/A | Internal | Existing tests | MIT | None | N/A | N/A | High | Very Low | False positive drift alerts | Edit post_tool_use.py | **RECOMMENDED** | 0.90 | 2026-12-04 |
| **Drift alert → context_flags + session_state** | Alert only | Alert routing | Self-designed | 2026-09-04 | N/A | Internal | N/A | MIT | None | N/A | N/A | High | Very Low | Alert fatigue | Add to drift_detect.py | Required for action | 0.85 | 2026-12-04 |

### Comparison: Eliminates Root Cause?

| Candidate | Eliminates Root Cause? | Notes |
|-----------|----------------------|-------|
| Hook chain integration | **YES** — runs on every tool call | Continuous monitoring |
| Alert routing | **REQUIRED** — makes detection actionable | Without this, detection = noise |

**Selected**: **Both** — hook integration + alert routing to context_flags.

---

## RC-007: Task-Scoped Permissions (STRUCTURAL)

### Root Cause
Global tool registry, no least-privilege per task.

### Candidate Solutions

| Candidate | Root Cause | Remedy Class | Source | Access Date | Release/Commit | Maintainer Signal | Tests/Evals | License | Dependencies | SBOM/Provenance | Security History | Compatibility | Cost | Failure Modes | Migration | Recommendation | Confidence | Expiry |
|-----------|------------|--------------|--------|-------------|----------------|-------------------|-------------|---------|--------------|-----------------|------------------|---------------|------|---------------|-----------|----------------|------------|--------|
| **Task spec `required_tools: []` + plan_enforce validation** | No task scope | Permission model redesign | Self-designed | 2026-09-04 | N/A | Internal | New tests needed | MIT | plan_enforce.py | N/A | N/A | Medium | Medium | Breaks existing plans | Refactor plan schema + plan_enforce | **RECOMMENDED** | 0.80 | 2026-12-04 |
| **Tool registry per-task subset** | No task scope | Registry redesign | Self-designed | 2026-09-04 | N/A | Internal | New tests needed | MIT | tool_registry.json | N/A | N/A | Low | High | Major refactor | New registry format | Phase 2 | 0.60 | 2026-12-04 |
| **Capability-based permissions (OAuth2-like)** | No task scope | Capability model | OAuth2 spec | 2026-09-04 | RFC 6749 | Standard | Libraries exist | N/A | oauthlib | N/A | Good | Low | High | Over-engineering | Not recommended | 0.40 | 2026-12-04 |

### Comparison: Eliminates Root Cause?

| Candidate | Eliminates Root Cause? | Notes |
|-----------|----------------------|-------|
| Task spec required_tools + plan_enforce | **YES** — task declares needs, plan validates | Minimal change, leverages existing plan gate |
| Per-task tool registry | **YES** — true least-privilege | Major refactor |
| Capability-based | **YES** — fine-grained | Overkill |

**Selected**: **Task spec `required_tools` + plan_enforce validation** — minimal change, uses existing plan approval gate.

---

## Adoption State Machine (per candidate)

| Candidate | State |
|-----------|-------|
| Local Token Registry + Hook | DISCOVER → SOURCE_VERIFY (internal) |
| check_deps.py pre-commit + pre-tool | DISCOVER → SOURCE_VERIFY → SECURITY_REVIEW (trivial) |
| Trigger Schema + Namespace | DISCOVER → SOURCE_VERIFY |
| Memory write gate (hook + claim-grader) | DISCOVER → SOURCE_VERIFY |
| update_from_repos cosign/SBOM | DISCOVER → SOURCE_VERIFY |
| drift_detect.py hook + alert routing | DISCOVER → SOURCE_VERIFY |
| Task required_tools + plan_enforce | DISCOVER → SOURCE_VERIFY |

---

## Next Phase

→ Solution Matrix (per root cause) → Change Plan → Implementation