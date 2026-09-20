---
name: graph-verify
description: Verify knowledge graph integrity — check node connections, detect orphan nodes, validate edges.
triggers:
  - model
---

# Graph Verify — Knowledge Graph Integrity

## Khi nào dùng
- Khi knowledge_distill.md is updated
- Khi memory graph is modified
- Khi verifying cross-references between concepts

## Cách dùng

1. **Load graph** — read knowledge_distill.md or memory graph
2. **Check nodes** — every node has: id, type, content, connections
3. **Check edges** — every edge connects two valid nodes
4. **Detect orphans** — nodes with no connections
5. **Detect cycles** — circular dependencies
6. **Validate types** — edges match allowed type combinations

## Output format

```text
GRAPH VERIFY: PASS | FAIL

NODES: <count>
EDGES: <count>
ORPHANS: <count> (<list>)
CYCLES: <count> (<list>)
INVALID EDGES: <count> (<list>)

RECOMMENDATIONS
- <fix for each issue>
```
