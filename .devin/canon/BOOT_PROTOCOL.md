# BOOT Protocol — Startup Sequence (Caveman Compressed)

> Order mandatory. No skip/reorder.
> **Full ref**: `docs/BOOT_PROTOCOL_full.md` (on-demand)
> **U63**: Only these load at BOOT:
> - `.devin/AGENTS.md` (~3KB)
> - `.devin/canon/CORE_CANON.md` (~2KB)
> - `.devin/canon/REDLINES.md` (top 5, ~2KB)
> - `.devin/loop_state.md` (registry, <3KB)
> - `.agents/knowledge_distill.md` (<8KB)
> - `.agents/user_profile.md` (<2KB)
> **All other canon = ON-DEMAND ONLY.** Track in `session_state.loaded_canon`.
> **U04: 3-tier lazy-load**:
> - **Tier S** (<30 min): Steps 1-8
> - **Tier M** (30min-2h): Steps 1-12
> - **Tier L/XL** (2h+): Steps 1-17
> - Unclear → default M

---

## Tier S — Quick Start (1-8)
1. Read `.devin/AGENTS.md` (~3KB)
2. Ensure `.devin/loop_state.md` exists
3. Read registry (<3KB)
4. Read `.agents/user_profile.md` (<2KB)
5. Determine `session_id`
6. Read context flags if exists
7. Check crashed sessions → ask human
8. **Start work**

---

## Tier M — Standard (1-12)
1-8 same as Tier S. Then:
9. **Pre-task audit** — `pre_task_audit.py --root <root> --session <sid>`. Stale >30min → `suspected_crashed`. Overlap → ask human.
10. **GoalSpec** — write to `loop_state/<sid>.md` + `session_state/<sid>.json`:
    `session_id, goal, complexity, scope, subtasks, acceptance_criteria, cost_cap, cumulative_cost`
11. **Update registry** — `loop_memory_sync.py --root <root> --session <sid> --status <status>`. Uses inter-process lock (U21).
12. **Start work**

---

## Tier L/XL — Full (1-17)
1-12 same as Tier M. Then:
13. Deep-memory check (if `~/.deep-memory/.venv` exists)
14. Large-repo init (if >50 source files → `init_deep` skill)
15. Task keyword lookup (optional, only if `context_quick_lookup.md` exists)
16. Project rules check (if `project_rules_dir` set)
17. Differential gap-scan (1-2 scope angles only)

**XL additional**: Interview-mode mandatory — 2-4 focused questions before plan.

---

## Rules (All Tiers)
- Do NOT read all canon at BOOT. Load on demand.
- Do NOT start work without GoalSpec for L/XL.
- Do NOT read every session_state/loop_state at BOOT. Registry first, then one file.
- Do NOT auto-resume crashed sessions. Ask human.
- If complexity unclear → default M. Upgrade if scope grows.

---

## U40: Minimal Mode (Graceful Degradation)
If MCP unreachable, hook error, config parse error, or state dir missing → minimal safe config (pre_tool_use, post_tool_use, stop, ahd_session only).

Keeps: pre_tool_use, post_tool_use, stop, ahd_session.
Disables: HLK, aide-memory hooks, MCP, skills, compaction, cost tracking.

Exit: fix component → restart full config → verify health-check ≥90.