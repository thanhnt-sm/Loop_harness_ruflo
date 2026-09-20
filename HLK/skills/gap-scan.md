---
name: gap-scan
description: Scan for gaps between current state and goal. Find missing pieces, untested paths, incomplete coverage.
triggers:
  - user
  - model
---

# Gap Scan — Find Missing Pieces

## Khi nào dùng
- Khi planning a task (find what's missing)
- Khi reviewing completeness before "done"
- Khi exploring a new codebase

## Cách dùng

1. **Define goal** — what should be true when complete?
2. **Scan current state** — what exists now?
3. **Identify gaps**:
   - Missing files (referenced but not created)
   - Missing tests (code without test coverage)
   - Missing docs (public API without docs)
   - Missing error handling (paths without try/catch)
   - Missing edge cases (happy path only)
4. **Prioritize gaps** — CRITICAL (blocks done) / HIGH / MEDIUM / LOW
5. **Report** — list all gaps with severity

## Output format

```text
GAP SCAN: <count> gaps found

CRITICAL GAPS
- <gap description> — <why it blocks done>

HIGH GAPS
- <gap description>

MEDIUM/LOW GAPS
- <gap description>

COVERAGE
- Files: <x>/<y> covered
- Tests: <x>/<y> paths tested
- Edge cases: <x>/<y> handled
```
