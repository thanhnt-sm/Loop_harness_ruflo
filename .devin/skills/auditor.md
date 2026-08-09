---
name: auditor
description: Adversarial code review — find security holes, false assumptions, failure modes. Always-on red-team analysis.
triggers:
  - user
  - model
---

# Auditor — Adversarial Code Review

## Khi nào dùng
- Sau khi implement xong, trước khi declare "done"
- Khi cần security review
- Khi cần find failure modes

## Trigger
- Every 5 iterations (mandatory periodic breadth pass — 8 fixed angles).
- After a large output (>5 files or >200 lines changed).
- Before declaring a task complete — **but the done-gate itself is `fable-judge`** (event-driven,
  every done-declaration, focused on claims + frauds + verbatim gate lines per
  `.devin/canon/VERIFICATION_PROTOCOL.md §Verbatim execution gates`). Run fable-judge first;
  Auditor adds the 8-angle breadth sweep. See `.devin/skills/fable-judge.md`.
- Keywords: auditor, adversarial audit, AUDITOR MODE.

1. **Read the diff** — inspect all changed files
2. **Red-team analysis** — find:
   - Security holes (injection, bypass, secrets)
   - False assumptions (unchecked edge cases)
   - Failure modes (what breaks under stress?)
   - Scope creep (unrelated changes)
3. **Report findings** — severity: CRITICAL / HIGH / MEDIUM / LOW
4. **Block "done"** if CRITICAL or HIGH unresolved

## Output format

```text
AUDIT VERDICT: PASS | FAIL | CONDITIONAL

FINDINGS
- [CRITICAL] <file>:<line> — <issue>
- [HIGH] <file>:<line> — <issue>
- [MEDIUM] <file>:<line> — <issue>

RECOMMENDATIONS
- <fix for each finding>
```
