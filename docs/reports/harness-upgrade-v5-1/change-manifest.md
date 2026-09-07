# Change Manifest — V5 Iteration 1 Implementation Plan

**Generated**: 2026-09-04
**Mode**: AUDIT_ONLY → Implementation plan for next iteration

---

## Changes Required

### TIER 1 (Must Fix)

#### CHG-001: Local Token Registry + Hook Enforcement (RC-001)
- **Files**: 
  - `.devin/scripts/token_registry.py` (new)
  - `.devin/hooks/pre_tool_use.py` (add revocation check)
  - `.devin/hook_hashes.json` (regenerate baseline)
- **Description**: In-memory token registry with expiry, revocation_source, revocation_list. Hook checks revocation_list per tool call.
- **Effort**: 2-3 days
- **Dependencies**: None
- **Tests**: Unit tests for token_registry; integration test re-attack ATT-001
- **Rollback**: Remove hook check, delete token_registry.py

#### CHG-002: check_deps.py Gates (RC-002)
- **Files**:
  - `.githooks/pre-commit` (add Gate 5: `python tools/check_deps.py`)
  - `.devin/hooks/pre_tool_use.py` (intercept pip/uv commands)
  - `.github/workflows/ci.yml` (add check_deps step)
- **Description**: Three-layer enforcement: pre-commit, pre-tool-use, CI
- **Effort**: 1 day
- **Dependencies**: None
- **Tests**: Try commit/install filelock 3.13+ → blocked; valid install → passes
- **Rollback**: Remove gates from hook/pre-commit/CI

#### CHG-003: Skill Trigger Schema + Core/Dynamic Namespace (RC-003)
- **Files**:
  - `.devin/skills/skill_index.json` (add trigger_schema field)
  - `.devin/scripts/skill_loader.py` (new: validate triggers on load)
  - `.devin/skills/core/` (directory for validated core skills)
  - `.devin/skills/dynamic/` (directory for reviewed dynamic skills)
- **Description**: Regex allowlist for triggers (e.g., `^[a-z-]+$`). Core skills pre-validated. Dynamic skills require review.
- **Effort**: 2 days
- **Dependencies**: Nuwa skill compatibility (dynamic skills from Nuwa)
- **Tests**: Load skill with invalid trigger → rejected; valid trigger → loads
- **Rollback**: Remove validation, merge directories

### TIER 2 (Next Iteration)

#### CHG-004: Memory Write Gate (RC-004)
- **Files**:
  - `.devin/hooks/post_tool_use.py` (add knowledge_distill write detection)
  - `.devin/scripts/memory_audit.py` (ensure validate_trigger_action_counter exported)
  - `.devin/skills/claim-grader/SKILL.md` (integrate for evidence grading)
- **Description**: Post-tool hook detects writes to knowledge_distill.md, runs validation, claim-grader grades evidence.
- **Effort**: 1 day
- **Dependencies**: claim-grader skill
- **Tests**: Write invalid pattern → rejected; valid → accepted with grade
- **Rollback**: Remove hook detection

#### CHG-005: update_from_repos Supply Chain Gate (RC-005)
- **Files**:
  - `.devin/skills/update_from_repos/*.py` (add cosign verify + SBOM generation)
  - `REPOS.md` (add provenance fields: cosign_signature, sbom_hash, commit_hash)
- **Description**: Before vendoring, verify cosign signature, generate SBOM, record provenance.
- **Effort**: 2 days
- **Dependencies**: cosign, syft (SBOM)
- **Tests**: Vendor unsigned skill → blocked; signed + SBOM → accepted
- **Rollback**: Disable verification flag

#### CHG-006: Drift Detection Hook + Alert Routing (RC-006)
- **Files**:
  - `.devin/hooks/post_tool_use.py` (add drift_detect.py call)
  - `.devin/scripts/drift_detect.py` (ensure writes context_flags)
  - `.devin/context_flags/<sid>.json` (drift_alert field)
- **Description**: Post-tool hook runs drift detection on model outputs, writes alert to context_flags.
- **Effort**: 1 day
- **Dependencies**: None
- **Tests**: Simulate drift → context_flags.drift_alert = true
- **Rollback**: Remove hook call

#### CHG-007: Task-Scoped Permissions (RC-007)
- **Files**:
  - `.devin/scripts/plan_orchestrator.py` (add required_tools to plan schema)
  - `.devin/hooks/plan_enforce.py` (validate task tools ⊆ approved tools)
  - Plan templates (add required_tools field)
- **Description**: Task declares required_tools; plan_enforce validates least-privilege.
- **Effort**: 2-3 days
- **Dependencies**: Plan FSM compatibility
- **Tests**: Task requests write, only read approved → DENY; valid subset → ALLOW
- **Rollback**: Remove validation, revert schema

---

## Implementation Order

1. **CHG-002** (check_deps.py gates) — Lowest risk, immediate value
2. **CHG-006** (drift_detect hook) — Low risk, monitoring value
3. **CHG-004** (memory write gate) — Medium risk, uses existing validation
4. **CHG-001** (token registry) — Medium risk, new component
5. **CHG-003** (skill trigger schema) — Medium risk, affects Nuwa
6. **CHG-005** (supply chain gate) — Medium risk, external deps
7. **CHG-007** (task-scoped permissions) — Highest risk, plan FSM changes

---

## Change Budget (V5 §16)

| Change | Files | Lines | Permission Edges | Dependencies | Side-effect Tools | Boundaries | Network Egress | Data Classes |
|--------|-------|-------|------------------|--------------|-------------------|------------|----------------|--------------|
| CHG-001 | 3 | ~200 | +1 (revocation check) | 0 | 0 | +1 (token registry) | 0 | +1 (token) |
| CHG-002 | 3 | ~50 | 0 | 0 | +2 (pip/uv intercept) | 0 | 0 | 0 |
| CHG-003 | 4 | ~150 | 0 | 0 | 0 | +2 (core/dynamic dirs) | 0 | 0 |
| CHG-004 | 3 | ~80 | 0 | +1 (claim-grader) | 0 | 0 | 0 | 0 |
| CHG-005 | 2+1 | ~200 | 0 | +2 (cosign, syft) | 0 | 0 | +1 (cosign API) | 0 |
| CHG-006 | 3 | ~60 | 0 | 0 | 0 | 0 | 0 | +1 (drift_alert) |
| CHG-007 | 3+templates | ~300 | +1 (tool scope check) | 0 | 0 | 0 | 0 | 0 |

**Total Budget**: ~24 files, ~1040 lines, +2 permission edges, +3 dependencies, +2 side-effect tools, +3 boundaries, +1 network egress, +2 data classes.

**High-Risk Changes** (per V5): CHG-001 (permission boundary), CHG-005 (network egress), CHG-007 (permission edge). All require human approval.

---

## Approval Requirements

| Change | Risk Level | Approval Required |
|--------|------------|-------------------|
| CHG-001 | High (permission boundary) | Human (APPROVER) |
| CHG-002 | Low | Auto (pre-commit) |
| CHG-003 | Medium (skill system) | Human (APPROVER) |
| CHG-004 | Low | Auto |
| CHG-005 | High (network egress) | Human (APPROVER) |
| CHG-006 | Low | Auto |
| CHG-007 | High (permission edge) | Human (APPROVER) |

**APPROVER**: NONE (current) → All High-risk changes will HOLD until human approver assigned.

---

## Next Phase

→ Implementation (when CHANGE_MODE = APPLY_WITH_APPROVAL)