---
name: using-skills
description: "Use before responding to any user request. Enforces skill-first methodology: check if a skill matches the request, invoke it before acting. Prevents ad-hoc work that bypasses the harness."
triggers: [model]
---

# Skill: using-skills — Meta-Skill

> This is a **meta-skill**. Its job is to enforce that other skills get used.
> Inspired by obra/superpowers `using-superpowers` pattern.

## The rule

**Before responding to any user request, check: does a skill match?**

1. Scan the skill list (descriptions start with "Use when...").
2. If a skill's "Use when..." condition matches the current situation → invoke it first.
3. If no skill matches → proceed without a skill (not everything needs one).
4. If multiple skills match → invoke all of them (parallel if possible).

## Why

Skills encode hard-won lessons. When an agent skips a skill and improvises, it re-derives
the lesson from scratch — usually worse. The skill exists because:
- Someone hit this situation before.
- They distilled the correct response.
- They wrote it down so it wouldn't have to be re-derived.

Skipping skills = paying the lesson's cost again every time.

## Recursion guard (U35)

> Prevents skill invocation deadlock from nested skill calls.

**Max invocation depth: 3**
- Depth 1: meta-skill (using-skills) → invokes skill
- Depth 2: skill → invokes sub-skill
- Depth 3: sub-skill → must NOT invoke further skills

**Enforcement:**
1. Track `skill_invocation_depth` in session_state
2. Before invoking a skill, check current depth
3. If depth >= 3 → stop, log error to stderr: `[U35 Recursion Guard] Max depth (3) exceeded. Skill: <name>`
4. Do NOT invoke the skill — proceed without it
5. Reset depth to 0 when top-level skill invocation completes

**Why depth 3?**
- Depth 1: using-skills decides which skill to use
- Depth 2: that skill may need a sub-skill (e.g., auditor uses comment_checker)
- Depth 3: sub-skill should be terminal (no further nesting)
- Beyond 3 = likely infinite loop or over-engineering

## The skill list (scan this)

> U26: Reduced to core skills (via negativa). Removed skills are archived.

| Skill | Use when... |
|-------|-------------|
| `harness-sensor` | Code or files have been modified |
| `update_from_repos` | Updating workspace from upstream repos in `REPOS.md` |
| `comment_checker` | After code edits that touch comments, or before declaring a code task complete |
| `slop-detector` | After generating user-facing prose, docs, naming, or abstractions |
| `fable-judge` | Before declaring "done" — adversarial done gate |
| `using-skills` | (this skill) Before responding to any request |

## Process vs Implementation skills

| Type | What it does | Examples |
|------|-------------|----------|
| **Process** | Sets the *approach* — how to think about the task | using-skills, comment_checker, slop-detector, fable-judge |
| **Implementation** | Does the *work* — executes a specific capability | harness-sensor, update_from_repos |

Process skills run first. They shape the approach. Implementation skills run when their
trigger condition is met during execution.

## When to NOT invoke a skill

- The request is conversational/informational (no work to do).
- The request is trivial (single command, <5 lines, no verification chain).
- A skill's "Use when..." condition clearly doesn't match.

Don't force-fit a skill to a request that doesn't need it. Skills are tools, not rituals.

## Personal skill shadowing

Users can add personal skills by dropping `.md` files into `.devin/skills/` with the same
frontmatter format. Personal skills **shadow** (override) built-in skills by name. This
lets users customize behavior without forking the canon.

## Output

This meta-skill doesn't produce a report. It produces a *decision*: which skill(s) to
invoke, or "no skill needed." The decision is visible in the next action.
