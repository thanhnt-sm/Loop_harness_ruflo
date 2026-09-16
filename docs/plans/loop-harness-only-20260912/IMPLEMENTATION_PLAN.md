# Implementation Plan — Loop Harness Ruflo Only

**Status:** Draft; approval required before apply
**Workspace:** `/workspace`
**Repository:** Loop Harness Ruflo
**Branch:** `audit/upgrade-20260912`

## Scope

This plan targets only files that exist in /workspace. Hermes launcher source is excluded and must be handled separately in /Volumes/Data/101.AI/hermes-m1.

- requirements-lock.txt
- docs/reports/HARNESS_UPGRADE_REPORT.md
- .devin/metadata/REPOS_TRACKER.json

## Phase 1 — Read-only audit

| File Path | Function/Area | Command | Acceptance | REQ ID |
|---|---|---|---|---|
| .devin/skills/skill_index.json | skill metadata/loading contract | python3 -c JSON schema inspection | Record actual paths, triggers, and lazy-load flag; no edit | REQ-001 |
| .devin/hooks/pre_tool_use.py | pre-tool dispatch contract | python3 -m py_compile .devin/hooks/pre_tool_use.py and read-only callsite inspection | Identify dispatch/re-export behavior; no edit | REQ-002 |
| .devin/tool_registry.json | tier registry | python3 -c count tiers.tools | Record 5 tiers and 88 entries; no edit | REQ-003 |
| .devin/hooks/schema_gate.py | schema gate contract | python3 -m py_compile .devin/hooks/schema_gate.py and read-only import inspection | Record gate entrypoint and failure semantics; no edit | REQ-004 |
| .devin/hooks/*.py | hook inventory | find .devin/hooks -maxdepth 1 -name *.py | Record deterministic inventory; no edit | REQ-005 |
| .devin/canon/*.md | canon relationships | grep/read-only cross-reference scan | Record concrete overlaps and deprecated files; no edit | REQ-006 |

## Phase 2 — Design review only

| Candidate | Target | Required evidence before any apply | REQ ID |
|---|---|---|---|
| Skill lazy-load | .devin/skills/skill_index.json | Prove runtime loader callsite and regression contract; separate plan required | REQ-010 |
| Tool registry lazy-load | .devin/tool_registry.json | Prove boot injection path and on-demand activation contract; separate plan required | REQ-011 |
| Hook optimization | .devin/hooks/*.py | Per-hook callsite, behavior, and protected-file review; separate plan required | REQ-012 |
| nuwa-skill update | .devin/skills/nuwa-skill/ | Immutable upstream diff and provenance; candidate approval required | REQ-020 |
| caveman canon | .devin/canon/CAVEMAN_PROTOCOL.md | Apply only if reviewed diff proves a new concept; otherwise no-op | REQ-021 |
| loop-engineering canon | .devin/canon/LOOP_PROTOCOL.md | Apply only if reviewed diff proves a new concept; otherwise no-op | REQ-022

## Phase 3 — Apply boundary

No code, hook, schema, canon, skill, or upstream mutation is authorized by this plan. Any apply requires a new plan with exact file paths, symbols, tests, and a new approval hash.

The script harness_upgrade_loop.py does not support --check; do not invoke that unsupported flag. Do not run --infinite.

## Verification

- python3 tools/check_governance.py --layout-only must pass.
- Read-only audit outputs must identify commands and outputs.
- No EXECUTION_REPORT.md is created for this audit-only plan.
- Existing WIP and unrelated mutations remain unchanged.
