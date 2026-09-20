---
name: verify-first
description: "Run verify-first chain (BRD -> scenario -> rubric -> test -> gate). POINTER to HLK canonical. Use when user provides BRD.md and wants full verify-first pipeline."
tools: read_file, run_command, todo_write
model: sonnet
maxTurns: 30
permissionMode: default
background: false
showOutput: true
---

# verify-first (POINTER — Command Code Agent)

**Canonical source**: `HLK/skills/verify-first/SKILL.md` + `HLK/chain/`

This is a thin pointer. Do NOT add logic here.

## Cách dùng (delegate to HLK)

```bash
# Cross-platform CLI
py HLK/chain/verify_first_cli.py <BRD.md> --out-dir ./out

# Node wrapper
node HLK/chain/hlk_wrappers/verify-first-wrapper.mjs <BRD.md>
```

Xem `HLK/skills/verify-first/SKILL.md` để biết chi tiết về chain, gate, audit.
