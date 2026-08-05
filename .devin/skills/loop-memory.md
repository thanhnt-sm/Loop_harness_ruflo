---
name: loop-memory
description: Sync loop state across sessions — regenerate registry, archive completed loops, restore in-progress loops.
triggers:
  - model
---

# Loop Memory — Cross-Session Loop Sync

## Khi nào dùng
- Khi session starts (restore in-progress loops)
- Khi session ends (archive completed loops)
- Khi loop_state.md is stale or corrupted

## Cách dùng

1. **Read loop_state.md** — current registry
2. **Check session archive** — completed loops from previous sessions
3. **Restore in-progress** — if session was interrupted, restore state
4. **Archive completed** — move done loops to archive
5. **Regenerate registry** — if corrupted, rebuild from session_state files
6. **Sync with aide-memory** — aide_remember key loop outcomes

## Output format

```text
LOOP MEMORY SYNC: COMPLETE

RESTORED: <count> in-progress loops
ARCHIVED: <count> completed loops
REGENERATED: <yes/no> registry

CURRENT LOOPS
- <loop_id>: <status> — <objective>

ARCHIVE
- <loop_id>: <completed_at> — <outcome>
```
