---
name: memory-audit
description: Audit memory quality — check for stale entries, duplicates, contradictions, low-confidence memories.
triggers:
  - model
---

# Memory Audit — Quality Check Persistent Memory

## Khi nào dùng
- Khi session ends (before archive)
- Khi memory recall returns suspicious results
- Khi knowledge_distill.md grows large (>8KB)

## Cách dùng

1. **Load all memories** — aide_recall + knowledge_distill.md
2. **Check for issues**:
   - Stale entries — older than expiration trigger
   - Duplicates — same fact stored multiple times
   - Contradictions — conflicting facts
   - Low confidence — memories with confidence < 70%
   - Orphaned — memories not referenced by any loop
3. **Clean up** — remove stale, merge duplicates, flag contradictions
4. **Update knowledge_distill.md** — write cleaned version
5. **Report** — what was removed, merged, flagged

## Output format

```text
MEMORY AUDIT: COMPLETE

TOTAL MEMORIES: <count>
STALE: <count> removed
DUPLICATES: <count> merged
CONTRADICTIONS: <count> flagged
LOW CONFIDENCE: <count> flagged

CLEANED SIZE: <bytes> (was <bytes>)
```
