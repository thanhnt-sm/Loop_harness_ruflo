---
name: context-compactor
description: Compress context when oversized. Caveman protocol — 65% reduction, 4 compression levels.
triggers:
  - "context_oversized"
  - "compact context"
  - "reduce tokens"
  - "context full"
---

# Context Compactor — Compress Oversized Context

## Khi nào dùng
- Khi `context_flags.context_oversized = true` (ghi bởi post_tool_use)
- Khi session approaching context window limit
- Khi post_tool_use detects oversize warning
- Khi agent bị chặn bởi pre_tool_use do `oversized_tool_calls_since_flag >= 4`

## Cách dùng
Agent chạy skill này khi nhận directive từ hook stderr:
```
[Agent Harness Deploy] context_oversized detected (response > 3000 chars).
Run context-compactor skill before continuing: offload full output to .devin/tmp/, keep head+tail+path in context.
```

Agent thực hiện:
1. **Identify compressible content** — long file reads, verbose outputs, repeated patterns
2. **Select compression level** based on `context_fill_pct`:
   - `< 50%`: L1 (light) — remove filler, 20% reduction
   - `50-70%`: L2 (full) — summarize paragraphs, 40% reduction
   - `70-80%`: L3 (ultra) — extract key facts only, 65% reduction
   - `> 80%`: L4 (wenyan) — telegraphic, 75% reduction
3. **Preserve critical info** — error messages, file paths, code signatures, line numbers, URLs, exact values
4. **Offload full payload** to `.devin/session_state/<session_id>/compaction/full_context_<timestamp>.json`
5. **Write compacted context** to session_state/loop_state with compaction header
6. **Clear context_oversized flag**

## Compression Levels (Caveman Protocol)

| Level | Trigger | Cuts | Target Reduction |
|-------|---------|------|------------------|
| **light** | fill 30-50% | Filler, hedging, pleasantries, transitions | 20% |
| **full** | fill 50-70% | light + articles, aux verbs, restating question | 40% |
| **ultra** | fill 70-80% | full + abbreviate, drop pronouns, telegraphic | 65% |
| **wenyan** | fill >80% | Classical Chinese register (Chinese sessions) | 75% |

## Verbatim Preservation (NEVER compress)
- File paths (`.py`, `.js`, `.json`, `.md`, etc.)
- Line numbers
- Error/status keywords (ERROR, FATAL, CRITICAL, WARNING, FAILED, PASS)
- URLs
- API keys (partial patterns)
- Function calls (`func()`)
- Inline code (`code`)

## Output Format
```
COMPACTION: L<level>
ORIGINAL: <tokens>
COMPACTED: <tokens>
SAVED: <pct>%
PRESERVED: <count> verbatim items
OFFLOADED: <path>
```

## Integration Hooks
- `post_tool_use.py`: Detects oversized responses → sets `context_oversized` flag + prints stderr directive
- `pre_tool_use.py`: Graduated gate based on `oversized_tool_calls_since_flag`:
  - 0-1: note "compact soon"
  - 2-3: warning "compact NOW, block incoming"
  - 4+: BLOCK non-compaction tools (exit 2)
- `context_compaction.py`: Standalone script for manual/automated compaction
  - Usage: `python .devin/hooks/context_compaction.py <session_id> [level]`
  - Compacts session_state + loop_state
  - Offloads full payload to filesystem
  - Clears context_oversized flag

## Deterministic Verification
- Hook integrity: `.devin/scripts/hook_integrity.py --verify`
- Compression ratio measured per level
- Verbatim items preserved (grep for preserved patterns in output)
- Offload file created and readable