---
name: tdd
description: Test-Driven Development — write failing test first, implement to pass, refactor. Red-Green-Refactor cycle.
triggers:
  - user
  - model
---

# TDD — Test-Driven Development

## Khi nào dùng
- Khi implementing new feature
- Khi fixing a bug (write test that reproduces first)
- Khi refactoring (tests must pass before and after)

## Cách dùng

### Red-Green-Refactor cycle

1. **RED** — write a failing test
   - Test describes desired behavior
   - Test must fail (not error) before implementation
   - One test at a time, smallest possible

2. **GREEN** — make it pass
   - Write minimal code to pass the test
   - NOT production quality yet — just make it work
   - Don't add extra functionality

3. **REFACTOR** — improve code quality
   - Tests must still pass
   - Remove duplication, improve naming, extract methods
   - Small steps, test after each

### Rules
- Never write production code without a failing test
- Never write more test than needed to fail
- Never write more production code than needed to pass
- Run tests after every change

## Output format

```text
TDD: COMPLETE

TESTS WRITTEN: <count>
- <test name>: <what it verifies>

IMPLEMENTATION: <files changed>

REFACTOR: <what was improved>

VERIFY: all tests PASS
```
