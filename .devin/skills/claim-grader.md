---
name: claim-grader
description: Grade claims as [fact], [inference], or [unverified]. Prevent hallucinated assertions.
triggers:
  - user
  - model
---

# Claim Grader — Fact-Check Assertions

## Khi nào dùng
- Khi agent makes claims about codebase behavior
- Khi agent asserts "this works" or "this is safe"
- Trước khi declare "done"

## Cách dùng

1. **Extract claims** — find all assertions in output
2. **Grade each claim**:
   - `[fact]` — verified by reading code or running test
   - `[inference]` — reasonable deduction from evidence
   - `[unverified]` — assertion without evidence
3. **Flag unverified claims** — require verification before "done"
4. **Block "done"** if any `[unverified]` claim is load-bearing

## Output format

```text
CLAIM GRADING: PASS | FAIL

CLAIMS
- [fact] "function X handles null" — verified at file:line
- [inference] "Y is safe because Z" — reasonable from evidence
- [unverified] "this is production-ready" — NO EVIDENCE

BLOCKERS
- <unverified claims that must be verified>
```
