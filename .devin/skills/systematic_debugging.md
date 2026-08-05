---
name: systematic_debugging
description: Systematic debugging methodology — reproduce, isolate, hypothesize, test, fix, verify. Prevent shotgunning.
triggers:
  - user
  - model
---

# Systematic Debugging — Methodical Bug Hunting

## Khi nào dùng
- Khi encountering a bug
- Khi fix attempts fail repeatedly
- Khi need to find root cause (not symptom)

## Cách dùng

1. **Reproduce** — establish reliable reproduction steps
   - If can't reproduce → add logging, try different inputs
2. **Isolate** — narrow down to smallest failing case
   - Binary search: remove half, test, repeat
3. **Hypothesize** — form hypothesis about root cause
   - Write down: "I think X because Y"
4. **Test hypothesis** — verify or falsify
   - If falsified → new hypothesis, don't shotg
5. **Fix root cause** — smallest change that addresses cause
   - NOT symptom — don't mask, fix the actual bug
6. **Verify** — confirm fix works + no regression
   - Run targeted test, then broader suite

## Anti-patterns (DON'T)
- Shotgunning — trying random fixes without understanding
- Symptom masking — catching error without fixing cause
- Scope creep — fixing unrelated bugs found during debug
- Skipping reproduce — fixing without reliable repro

## Output format

```text
DEBUG: COMPLETE

BUG: <description>
REPRO: <steps>
ROOT CAUSE: <explanation>
HYPOTHESIS: <what was tested>
FIX: <file:line> — <change>
VERIFY: <test> — PASS/FAIL
REGRESSION: <suite> — PASS/FAIL
```
