---
name: context-compactor
description: Compress context when oversized. Caveman protocol — 65% reduction, 4 compression levels.
triggers:
  - model
---

# Context Compactor — Compress Oversized Context

## Khi nào dùng
- Khi context_flags.context_oversized = true
- Khi session approaching context window limit
- Khi post_tool_use detects oversize warning

## Cách dùng

1. **Identify compressible content** — long file reads, verbose outputs, repeated patterns
2. **Apply compression levels**:
   - L1: Remove whitespace + comments (20% reduction)
   - L2: Summarize paragraphs (40% reduction)
   - L3: Extract key facts only (60% reduction)
   - L4: Caveman protocol — ultra-compact (65% reduction)
3. **Preserve critical info** — error messages, file paths, code signatures
4. **Write compacted context** to session_state

## Output format

```text
COMPACTION: L<level>
ORIGINAL: <tokens>
COMPACTED: <tokens>
SAVED: <pct>%
PRESERVED: <list of critical items>
```
