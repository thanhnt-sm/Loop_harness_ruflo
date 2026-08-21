# Caveman Protocol — Token Compression (Caveman Compressed)

> Source: JuliusBrussee/caveman + cheeseonamonkey/Lean-Caveman. Goal: ~65% token reduction without losing precision.

---

## Problem
Agent transcripts burn tokens on filler carrying no decision-relevant info. 40 words → 8 words. Filler eats context window for evidence (file contents, errors, prior state). Context fills with filler → model loses track of actual problem.

## Deeper Point
Token efficiency = **attention**. 200K context × 65% filler = 70K usable. 100K × 90% signal = more *usable* attention. Caveman = context-window multiplier.

## Why ~65%
Filler (hedging, restating, transitions, pleasantries) ≈ 65% tokens in verbose mode. Cutting leaves signal. Exact varies by task; direction consistent.

---

## Rule: Strip Filler. Keep Signal.
- **Cut**: adverbs, hedging, pleasantries, restating question, motivational filler, transitions.
- **Keep verbatim**: code, paths, line numbers, errors, identifiers, commands, URLs, exact values.

---

## Examples
| Verbose (Bad) | Caveman (Good) |
|---------------|----------------|
| "So I looked into the issue and it looks like the problem is probably in the config file at line 42 where the path seems to be wrong." | `config.json:42` — path wrong. Fix: `/correct/value`. |
| "I'm happy to report that I've successfully completed the deployment and everything appears to be working!" | Deploy done. `verify.py` PASS. 3 tools synced. |

---

## What Caveman is NOT
- NOT broken grammar. Sentences parseable.
- NOT dropping evidence. Paths/lines/errors always verbatim.
- NOT for user-facing prose needing warmth (apologies, bad news, teaching).
- NOT for code comments or docs for humans.

## When to Relax
- User asks explanation/teaching.
- Writing Docs/README (full prose).
- Bad news or clarifying questions (clarity > brevity).

---

## Dynamic Context Compaction
Context fill = leading indicator of token waste. Window fills → model falls back to slop. React before happens.

### Triggers
- `context_fill_pct > 70%` → `compact` mode
- `context_fill_pct > 80%` → `ultra` mode
- Single tool output > 20 lines or > 3KB → dispatch `context-compactor`
- Single `read` > 50 lines → use `offset`/`limit` or `grep`

### Automatic Load + Enforcement
- `post_tool_use.py` writes `context_oversized: true` + `oversized_tool_calls_since_flag: 0` to `.devin/context_flags/<sid>.json` when tool response oversized. Prints stderr directive → run `context-compactor`.
- Flag still set next tool call → increments `oversized_tool_calls_since_flag` — tracks un-compacted calls.
- `pre_tool_use.py` **graduated gate** by counter:
  - **0-1 (note)**: non-compaction tools allowed + stderr "compact soon"
  - **2-3 (warning)**: non-compaction tools allowed + stderr "compact NOW, block incoming"
  - **≥4 (block)**: non-compaction tools **blocked** (exit 2). Agent must run `context-compactor` + clear flag.
  - Compaction-safe tools (read, grep, glob, write, edit, notebook_*, todo_write, skill) **always allowed** — agent needs them to compact.
- Compaction **enforced, not suggested**. Agent can't ignore flag indefinitely — at 4+ un-compacted calls, forced to act.
- `loop-memory` reads flags at iter end, updates `session_state.json` + `loop_state.md`.

### Registry Front Matter
```yaml
context_fill_pct: <0-100 estimate>
caveman_level: <light|compact|full|ultra|wenyan>
active_session: s-...
```
Session file must include:
```yaml
context_fill_pct: <0-100>
caveman_level: <light|compact|full|ultra|wenyan>
```

### Compaction Rules
- Use `context-compactor` skill for large payloads.
- Never compress verbatim: code, paths, lines, errors, exact values.
- When in doubt, offload full payload + keep one-line summary + path.

---

## Compression Levels
| Level | Cuts | Example |
|-------|------|---------|
| **light** | Filler, hedging, pleasantries | `Sync done. 2 issues: src/sync.py:42 path, :88 backup.` |
| **full** | light + articles, aux verbs, restating Q | `sync.py:42` hardcoded path (P1). `:88` missing backup (P0). |
| **ultra** | full + abbreviate, drop pronouns, telegraphic | `sync.py:42 hardcode P1. :88 no backup P0. fix: registry + shutil.copy2.` |
| **wenyan** | Classical Chinese | `sync.py:42 路徑硬編 P1。:88 無備份 P0。修：registry + shutil.copy2。` |

### When Each
| Channel | Default | Escalate |
|---------|---------|----------|
| Worker → Commander | full | compact (>70%) / ultra (>80%) |
| Commander → user | light | full (user asks) |
| Memory writes | full | ultra (near 3KB cap) |
| Large tool output | compact | ultra (context high) |
| Docs / README | full prose | — |
| Bad news / questions | full prose | — |

---

## Ultra Mode
- Abbreviate: `configuration`→`config`, `verification`→`verify`, `implementation`→`impl`
- Drop pronouns: "I found the bug" → `found bug`
- Telegraphic: SVO only, no connectives
- **Keep verbatim**: code, paths, lines, errors, commands, URLs, values
- **Never ultra for**: bad news, apologies, teaching, user summaries

---

## Wenyan Mode
Classical Chinese (文言文) for Chinese sessions max compression. Same keep-verbatim rules. Only when session language Chinese AND context constrained.