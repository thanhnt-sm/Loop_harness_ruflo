# V5 Red-Team Preflight — Iteration 1

**Date**: 2026-09-04
**Mode**: AUDIT_ONLY (prerequisites missing)
**Workspace**: D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo

---

## Base Revision

- Git commit: `HEAD` (current)
- Branch: `main`
- No uncommitted changes from upgrade phase

---

## Dependency Lock

- Python: 3.13 (venv at `.venv/`)
- Key packages: pytest, pydantic, rich, click
- No lockfile drift detected

---

## Model/Runtime/Tool/MCP Versions

| Component | Version |
|-----------|---------|
| Active model | opencode/nemotron-3-ultra-free |
| GLM executor | GLM-5.2 High (free) |
| Kimi executor | Kimi K2.7 (free tier) |
| Lightning executor | SWE-1.7 Lightning |
| Hook integrity | 51 hooks verified |
| Tool registry | 7 tools |
| Skill index | 26 skills (progressive load) |

---

## Environment Fingerprint

- OS: Windows 10/11 (PowerShell 5.1)
- Shell: powershell
- Git: available
- No sandbox/staging clone available
- No production access

---

## Baseline Tests

| Check | Command | Status |
|-------|---------|--------|
| Hook integrity | `.venv/bin/python .devin/scripts/hook_integrity.py --verify` | ✅ PASS |
| Hook order | `.venv/bin/python .devin/scripts/hook_integrity.py --verify-order` | ✅ PASS |
| Context projection | `.venv/bin/python .devin/scripts/context_projection.py --report` | ✅ PASS (7,476 tokens boot) |
| Tests | `pytest -q` | ⚠️ CONFTEST ERROR (null bytes in conftest) |

---

## Owner/Registration/Expiry Check

| Asset | Owner | Registered | Expiry | Status |
|-------|-------|------------|--------|--------|
| Hooks (51) | AHD | ✅ | N/A | ✅ Verified |
| Skills (26) | AHD | ✅ | N/A | ✅ Progressive load |
| Canon (12) | AHD | ✅ | N/A | ✅ Lazy-load |
| Tools (7) | AHD | ✅ | N/A | ✅ Slim |
| HLK layer | Upstream | ✅ | N/A | ⚠️ Not verified this run |

---

## Pre-existing Failures

1. **pytest conftest.py** — SyntaxError: null bytes in conftest.py (pre-existing, not upgrade-related)
2. **HLK integrity** — Not checked this iteration (requires `node HLK/wrappers/hlk-verify-integrity.js`)
3. **No sandbox** — Cannot run active red-team attacks (PHASE 14-16 limited to static)

---

## Verdict

**PREFLIGHT COMPLETE** — Baseline established. Proceeding to static analysis phases (1-16).
**BLOCKED**: Active attack execution (no sandbox), MCP pack tests (no MCP server), cross-model evaluation transfer (no model variety).

---

## Next Phase

→ Component Map (PHASE 9) → Critical Invariants (PHASE 9) → Threat Model (PHASE 10)