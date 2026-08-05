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

## Cách dùng

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
