# BOOT Protocol — Startup Sequence

> Order is mandatory. Do not skip or reorder. Total BOOT payload target: <16KB.
>
> **U04: 3-tier lazy-load model** — BOOT steps vary by task complexity:
> - **Tier S** (Small, <30 min): Steps 1-8 only. Skip 9-17.
> - **Tier M** (Medium, 30min-2h): Steps 1-12. Skip 13-17.
> - **Tier L/XL** (Large, 2h+): All steps 1-17.
>
> Determine tier from task description. If unclear, default to M.

---

## Tier S — Quick start (small tasks, <30 min)

Steps 1-8 only. No GoalSpec, no pre-task audit, no gap-scan.

1. **Read entry file** — `.devin/AGENTS.md` (~5KB summary).
   **Do NOT load** `.devin/AGENTS_full.md` (186KB) — load canon on-demand.
2. **Ensure registry exists** — `.devin/loop_state.md`. Create if missing.
3. **Read registry** — `.devin/loop_state.md` (<3KB).
4. **Read user profile** — `.agents/user_profile.md` (<2KB).
5. **Determine `session_id`** — use tool-supplied or generate new.
6. **Read context flags** — `.devin/context_flags/<session_id>.json` if exists.
7. **Check for crashed sessions** — if `active_session` is `crashed` or `suspected_crashed`, ask human. Never auto-resume.
8. **Start work** — no GoalSpec needed for S tasks. Work happens now.

---

## Tier M — Standard start (medium tasks, 30min-2h)

Steps 1-12. Includes GoalSpec but skips deep-memory, large-repo init, gap-scan.

1-8. **Same as Tier S** (above).

9. **Pre-task / crash audit** — preferred: `from pre_task_audit import run_inline; run_inline(root, files, tags, session_id)` (U13 inline, saves ~200ms). Fallback subprocess: `python .devin/scripts/pre_task_audit.py --files <files> --tags <tags> --session <session_id>`.
   - Compares `last_heartbeat`, `last_state_write`, `owned_files`, `tags` against new task.
   - If stale (>30 min), mark `suspected_crashed`.
   - If overlap, ask human. **Never auto-resume.**
10. **Output GoalSpec** — write to `.devin/loop_state/<session_id>.md` and `.devin/session_state/<session_id>.json`:
    ```yaml
    session_id: "s-..."
    goal: "[one-line summary]"
    complexity: "M"
    context_fill_pct: 0
    caveman_level: "full"
    scope:
      angles_required: ["angle1"]
      files_to_check: ["path1"]
      sensor_mode: "code" | "doc"
    subtasks: []
    acceptance_criteria: []
    human_in_loop_triggers: []
    estimated_iterations: N
    cost_cap: 5.0  # U17: max USD per task (default $5, adjust per complexity)
    cumulative_cost: 0.0  # U17: tracked by post_tool_use hook
    ```
    JSON must include `status: in_progress`, `state_written: false`, `last_state_write`, `last_heartbeat`, `owned_files`, `affected_files`, `tags`.
11. **Update registry** — append session to `.devin/loop_state.md`, set `active_session`. Preferred: `from loop_memory_sync import run_inline; ok, err = run_inline(root, session_id, status)` (U13 inline, saves ~200ms). Fallback subprocess: `python .devin/scripts/loop_memory_sync.py`.
12. **Start work** — GoalSpec done, work begins.

---

## Tier L/XL — Full start (large tasks, 2h+)

All steps 1-17. Includes deep-memory, large-repo init, gap-scan, interview-mode.

1-12. **Same as Tier M** (above). Set `complexity: "L"` or `"XL"` in GoalSpec.

13. **Deep-memory check** (optional) — if `~/.deep-memory/.venv` exists, run retrieval. If not, set `deep_memory_offline: true`. Do not fabricate memory.
14. **Large-repo init** (optional) — if repo has >50 source files or >20 directories, consider `init_deep` skill.
15. **Task keyword lookup** — if `.agents/context_quick_lookup.md` exists (<3KB), read it. Maps task keywords to required docs (O(1) lookup).
16. **Project rules check** — if `user_profile.md` has `project_rules_dir`, note path. If `project_rules_index` set, read index (<3KB). Load individual rules on demand only.
17. **Differential gap-scan** — scan 1-2 scope angles only. See `.devin/skills/gap-scan.md`.

**XL additional**: Interview-mode planning mandatory (see `CORE_CANON.md §6`). 2-4 focused questions before plan. Skipping for XL = red line.

---

## Rules (all tiers)

- Do NOT read all Docs at BOOT. Load on demand.
- Do NOT read full `context.md` if a quick-lookup variant exists.
- Do NOT start work without a GoalSpec for L/XL tasks.
- Do NOT read every `session_state/*.json` or `loop_state/*.md` at BOOT.
  Read the registry first; only read the one session state that matches.
- Do NOT auto-resume a crashed or in-progress session. Detect it, ask human.
- BOOT is for orientation. Work happens after.
- **U04**: If task complexity is unclear, default to M. Upgrade to L/XL if scope grows.

## Multi-thinking mode activation

At BOOT, activate the default thinking mode set:
- **Skeptic** — default. Every claim needs evidence.
- **Architect** — for planning/decomposition tasks.
- **Auditor** — for verification/completion tasks.

Switch modes explicitly when the task changes character. State the active mode in output.

## Rule placement (Lost in the Middle)

> See `HARNESS_ENGINEERING.md` for the full principle.
> Short version: critical rules go at the top of the entry file (first 30 lines = "golden position"). Rules buried at line 300 of a 600-line file are effectively unwritten.
