---
name: init_deep
description: Deep initialization for large repos — scan structure, build index, identify conventions, create registry.
triggers:
  - user
---

# Init Deep — Large Repository Initialization

## Khi nào dùng
- Khi starting work on a large/unfamiliar repo
- Khi BOOT_PROTOCOL Tier L/XL requires deep init
- Khi loop_state.md registry is empty or stale

## Cách dùng

1. **Scan structure** — directory tree, file types, key files
2. **Build index** — map: entry points, configs, tests, docs, scripts
3. **Identify conventions** — language, framework, style, patterns
4. **Find build/test commands** — package.json, Makefile, Cargo.toml, etc.
5. **Create registry** — write to loop_state.md:
   - Project type, language, framework
   - Build command, test command, lint command
   - Key directories, entry points
   - Conventions (naming, structure, testing)
6. **Save to memory** — aide_remember key findings

## Output format

```text
INIT DEEP: COMPLETE

PROJECT TYPE: <language/framework>
BUILD: <command>
TEST: <command>
LINT: <command>

KEY FILES
- <path>: <purpose>

CONVENTIONS
- <convention description>

REGISTRY WRITTEN: loop_state.md
MEMORY SAVED: <items>
```
