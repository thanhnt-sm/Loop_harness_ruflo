# Loop Protocol — Turn-Based Loop Detail

> Sub-protocol of `LOOP_PROTOCOL.md`. Load when task is exploratory (each output reshapes next question).
> Turn-based = human prompt triggers, human reviews output. The manual baseline.
>
> **Required context**: This sub-protocol references `§State contract`, `§Mandatory stop conditions`,
> and `§Maker/checker` from `LOOP_PROTOCOL.md`. Load core first if not already loaded.

## Skills upgrade (cheapest improvement)

Turn-based is not loop-engineered, just chat. No kickoff needed. But: write the verification you repeat every turn into a Skill (SKILL.md) — checklist, multi-step flow, support files. The loop stays human-driven, but each turn's quality stops depending on you remembering to remind the agent. This is the cheapest upgrade: no autonomy added, consistency gained.

## Idle-yank

> Source: oh-my-openagent's Todo Enforcer (Sisyphus Labs), reimplemented as prompt-level protocol.

If an agent has not produced output AND not written `.devin/loop_state/<session_id>.md` and `.devin/session_state/<session_id>.json` for **N** consecutive polling intervals (default N=2), the harness yanks it back:

1. **Re-inject the GoalSpec.** Re-read `.devin/loop_state/<session_id>.md`, restate the goal + current subtask.
2. **Force a state write.** Require state update before any other action.
3. **Diagnose the stall.** Blocked? confused? done-but-didn't-declare? Each has a different response.
4. **Re-dispatch or escalate.** Don't let the agent sit idle again.

### Stall diagnosis + response

| Stall type | Signal | Yank response |
|------------|--------|---------------|
| **Blocked** | Hit error/obstacle, stopped | Re-dispatch with obstacle as subtask. 2 rounds → escalate. |
| **Confused** | Output off-topic/contradicts GoalSpec | Re-inject GoalSpec + scope. Reset to last known-good state. |
| **Done-but-silent** | Output complete, no state write | Force verification (maker≠checker). Verified → done. Not → re-dispatch. |
| **Drifted** | Started tangential task | Stop tangent. Log as "deferred". Re-dispatch original goal. |
| **Truly idle** | No output, no state, no error | Re-dispatch from last state. 2 rounds → escalate. |

### Implementation (prompt-level)

Enforced by the **Commander** (or user, if no Commander). Between iterations, check each active worker: if `last_output_age > 2 * polling_interval` AND `state_write_age > 2 * polling_interval` → diagnose stall type → yank.

For user-driven loops: if no per-session state write and no done-declaration → prompt: "You went idle. Read `.devin/loop_state/<session_id>.md`, state current subtask, continue. If blocked, say what. If done, run verification."

### Rules

- **Not a punishment.** Recovery mechanism — re-orienting the agent.
- **Don't yank too early.** N=2 gives agent time for real work. Every interval = micromanagement.
- **Don't yank too late.** N>4 = loop stalled. User waiting.
- **Yank ≠ escalate.** Yank = "wake up". Escalate = "human needed". Yank first; escalate if yank fails 2 rounds.
- **State write is the heartbeat.** Writes state = alive. Doesn't = idle or done — yank distinguishes.

## Edge loop pattern

> Source: Reddit user's workflow design, via Wisely Chen's guide. The *edges* of creative/judgment work — repetitive, verifiable parts before and after the human's creative core — can be looped safely.

### The pattern

`[Loop: Before human] → [Human: Creative core] → [Loop: After human]`. Before: gather candidates, de-duplicate, check sources, verify links → cleaned draft. Human: selection decisions, argument construction, narrative structure, final polish. After: verify output (links, formatting, cross-refs), run lint/test/build → validated final.

### When to use

No auto-metric for core (e.g., "is this a good argument?"). Verifiable edges (e.g., "are all links valid?"). Human's judgment is irreplaceable core.

### Examples

| Task | Before loop | Human core | After loop |
|------|-------------|------------|------------|
| Blog post | Gather research, check sources | Write argument | Check links, formatting |
| Architecture | Survey patterns, list constraints | Make decisions | Verify diagram consistency |
| Code review PR | Run lint/test/coverage | Judge architecture | Verify comments addressed |
| Marketing page | Gather assets, check copy length | Write messaging | Check layout, validate forms |

### Rules

1. **Human core is never looped.** Looping judgment = cognitive surrender.
2. **Before-loop produces draft, not final.** Human decides what to use.
3. **After-loop validates, doesn't create.** Checks output, doesn't generate.
4. **Both edges L1 by default.** Promote to L2 only after human trusts edge loop.

**Loop the edges. Keep the core human.**

## Kickoff template (turn-based)

Turn-based doesn't need a formal kickoff — it's just chat. But if you want consistency:

```
Context: [what the agent needs to know]
Task: [what to do]
Verify: [how to check the output is correct]
```

No max iterations, no budget cap, no convergence check — human reviews each turn.
