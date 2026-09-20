---
name: slop-detector
description: "Use after generating user-facing prose, docs, commit messages, naming, or code. Detects AI-generated filler, generic abstractions, and meaningless identifiers."
version: "1.2.0"
last_updated: "2026-07-07"
triggers: [user, model]
---

# Skill: slop-detector

> Detect AI Slop before it ships.

## Severity grading (U31)

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Meaning distortion — slop changes what the text says | Must fix before shipping |
| **HIGH** | Hedge words — undermines confidence without reason | Fix unless uncertainty is real |
| **MEDIUM** | Filler — adds words without adding meaning | Fix if time permits |
| **LOW** | Style — cosmetic, doesn't affect meaning | Optional |

## Trigger
- After writing user-facing prose, README, PR description, commit message, or inline documentation.
- After naming a class, function, variable, or module.
- After creating an abstraction (interface, base class, wrapper).
- Final report before user-facing output.

## When to run
Before declaring a task done or before a user-facing response.

## How

1. **Prose check.** [HIGH]
   Flag and rewrite any of these AI Slop phrases:
   - `delve into`, `leverage`, `seamless`, `robust`, `in the ever-evolving landscape`, `it's important to note`, `as a responsible AI`, `we will explore`, `this is a complex topic`
   - Hedging: `might be`, `could be considered`, `arguably`, `to some extent` (unless uncertainty is real)
2. **Naming check.** [MEDIUM]
   Flag generic names with no domain meaning:
   - `data`, `info`, `manager`, `helper`, `utils`, `processor`, `handler`, `service`, `common`, `base` (unless part of a recognized pattern)
   - Replace with the domain concept (e.g., `UserProfile` not `UserData`, `InvoiceParser` not `InvoiceProcessor`).
3. **Abstraction check.** [CRITICAL]
   Flag:
   - Single-call wrapper functions.
   - Interfaces with only one implementation.
   - Premature generic abstractions (`AbstractBaseFoo`, `IManager`).
   - Gold-plating: unrequested features, speculative extension points.
4. **Commit message check.** [HIGH]
   - Reject: `update`, `fix`, `improve`, `changes`.
   - Require: `area: what changed and why`.
5. **Meaning distortion check.** [CRITICAL]
   - Flag: text that changes the meaning of what was actually done
   - Flag: claims that overstate or understate the actual change
   - Flag: false precision (specific numbers without evidence)
6. **Style check.** [LOW]
   - Flag: redundant adjectives, passive voice, wordy constructions
   - Only fix if no CRITICAL/HIGH/MEDIUM issues remain
7. **Output a slop report.**
   For each issue: `[severity] [category] original -> rewrite`.
   Fix CRITICAL and HIGH before shipping. MEDIUM if time permits. LOW optional.

## Output
```
## Slop report
| # | severity | category | original | rewrite |
|---|----------|----------|----------|---------|
| 1 | CRITICAL | abstraction | ... | ... |
| 2 | HIGH | prose | ... | ... |
| 3 | MEDIUM | naming | ... | ... |
| 4 | LOW | style | ... | ... |
```

Caveman compact. One row per issue. Sort by severity (CRITICAL first).
