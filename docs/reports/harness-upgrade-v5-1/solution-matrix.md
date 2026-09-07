# Solution Matrix — V5 Iteration 1

**Generated**: 2026-09-04
**Mode**: AUDIT_ONLY — Maps root causes to selected solutions

---

## Solution Mapping

| Root Cause | Type | Selected Solution | Eliminates Root Cause? | Evidence |
|------------|------|-------------------|----------------------|----------|
| **RC-001: No revocation infrastructure** | STRUCTURAL | Local Token Registry + Hook Enforcement | **YES** — adds expiry, revocation_source, revocation_list check in hook | Hook checks revocation_list per tool call; token carries expiry |
| **RC-002: Dependency pins not enforced** | MECHANICAL | check_deps.py in pre-commit (Gate 5) + pre_tool_use for pip/uv + CI gate | **YES** — blocks commit/install with unpinned deps | Pre-commit runs check_deps.py; pre_tool_use intercepts pip/uv |
| **RC-003: Skill trigger validation** | STRUCTURAL | Trigger Schema (regex allowlist) + Core/Dynamic Namespace | **YES** — core skills validated triggers, dynamic skills reviewed | skill_index.json validates trigger against schema; namespace separates trust |
| **RC-004: Memory write gate** | MECHANICAL | Post-tool hook for knowledge_distill + Claim-grader evidence grading | **YES** — validates trigger+action+counter on every write | post_tool_use calls memory_audit.py; claim-grader grades evidence |
| **RC-005: Supply chain provenance** | STRUCTURAL | update_from_repos: cosign verify + SBOM check + REPOS.md provenance fields | **YES** — verifies signature/provenance before vendor | update_from_repos runs cosign/sbom; REPOS.md tracks provenance |
| **RC-006: Drift detection hook** | MECHANICAL | drift_detect.py in post_tool_use chain + alert → context_flags | **YES** — continuous monitoring + actionable alerts | post_tool_use runs drift_detect; writes context_flags |
| **RC-007: Task-scoped permissions** | STRUCTURAL | Task spec `required_tools: []` + plan_enforce validation | **YES** — task declares needs, plan validates least-privilege | plan schema adds required_tools; plan_enforce checks subset |

---

## Does Solution Eliminate Root Cause Completely?

| Root Cause | Solution | Eliminates Completely? | Residual Risk | Mitigation |
|------------|----------|----------------------|---------------|------------|
| RC-001 | Local Token Registry + Hook | **YES** | Hook bypass if not in chain | Hook in canonical chain (verified) |
| RC-002 | check_deps.py gates (3 layers) | **YES** | False positive on new deps | Allowlist for known-safe patterns |
| RC-003 | Trigger Schema + Namespace | **YES** | Dynamic skill trigger evolution | Regex allowlist updated per review |
| RC-004 | Post-tool hook + Claim-grader | **YES** | Claim-grader probabilistic | Deterministic hook primary, claim-grader secondary |
| RC-005 | cosign/SBOM gate + REPOS.md | **YES** | Upstream key compromise | Key rotation policy in REPOS.md |
| RC-006 | Hook + alert routing | **YES** | Alert fatigue | Context_flags deduplication |
| RC-007 | Task required_tools + plan_enforce | **YES** | Plan approve grants excess | Plan review checks least-privilege |

---

## Implementation Effort Estimate

| Solution | Files to Change | Est. Effort | Risk | Dependencies |
|----------|-----------------|-------------|------|--------------|
| Local Token Registry + Hook | `pre_tool_use.py`, new `token_registry.py`, `hook_integrity.py` baseline | Medium (2-3 days) | Medium | None |
| check_deps.py gates (3) | `.githooks/pre-commit`, `pre_tool_use.py`, CI workflow | Low (1 day) | Low | None |
| Trigger Schema + Namespace | `skill_index.json` schema, `skill_index.json` generator, skill loader | Medium (2 days) | Medium | Nuwa skill compatibility |
| Memory write gate | `post_tool_use.py`, `memory_audit.py`, claim-grader integration | Low (1 day) | Low | claim-grader skill |
| update_from_repos cosign/SBOM | `update_from_repos/SKILL.md`, `update_from_repos/*.py`, `REPOS.md` | Medium (2 days) | Medium | cosign, syft/sbom |
| drift_detect.py hook + alert | `post_tool_use.py`, `drift_detect.py`, `context_flags` writer | Low (1 day) | Low | None |
| Task required_tools + plan_enforce | `plan_orchestrator.py` schema, `plan_enforce.py`, plan templates | Medium (2-3 days) | Medium | Plan FSM compatibility |

---

## Priority Order (Tier 1 = Must Fix This Iteration)

| Priority | Root Cause | Solution | Tier |
|----------|------------|----------|------|
| 1 | RC-001: No revocation | Local Token Registry + Hook | **TIER 1** |
| 2 | RC-002: Dep pins not enforced | check_deps.py gates (3) | **TIER 1** |
| 3 | RC-003: Skill trigger validation | Trigger Schema + Namespace | **TIER 1** |
| 4 | RC-004: Memory write gate | Post-tool hook + Claim-grader | **TIER 2** |
| 5 | RC-005: Supply chain provenance | update_from_repos cosign/SBOM | **TIER 2** |
| 6 | RC-006: Drift detection hook | Hook + alert routing | **TIER 2** |
| 7 | RC-007: Task-scoped permissions | Task required_tools + plan_enforce | **TIER 2** |

**TIER 1 Criteria**: Critical severity, structural/mechanical, blocks safe operation if unfixed.
**TIER 2 Criteria**: High severity, can be deferred to next iteration with mitigation.

---

## Cross-Cutting Concerns

| Concern | Impact | Resolution |
|---------|--------|------------|
| Hook chain modifications | All solutions modify hook chain | Single PR updating `post_tool_use.py` + `pre_tool_use.py` |
| Skill system changes | RC-003, RC-004 affect skills | Coordinate with Nuwa skill for dynamic skill compatibility |
| Plan system changes | RC-007 affects plan FSM | Ensure plan_orchestrator.py schema backward compatible |
| Token registry | RC-001 new component | Keep minimal: in-memory dict + persistence, no external deps |

---

## Verification Strategy Per Solution

| Solution | Verification Method | Oracle |
|----------|---------------------|--------|
| Local Token Registry + Hook | Re-attack ATT-001: revoke → agent blocked | Deterministic: hook returns DENY |
| check_deps.py gates | Try commit/install bad pins → blocked | Deterministic: exit code 1 |
| Trigger Schema + Namespace | Load malicious skill trigger → rejected | Deterministic: schema validation fail |
| Memory write gate | Write invalid pattern to knowledge_distill → rejected | Deterministic: validation fail |
| update_from_repos cosign/SBOM | Vendor unsigned skill → blocked | Deterministic: cosign verify fail |
| drift_detect.py hook | Simulate model drift → context_flags set | Deterministic: flag written |
| Task required_tools + plan_enforce | Task requests write, only read approved → blocked | Deterministic: plan_enforce DENY |

---

## Next Phase

→ Change Manifest (implementation plan) → Implementation