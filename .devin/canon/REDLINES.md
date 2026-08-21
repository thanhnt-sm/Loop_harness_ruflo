# Red Lines — Hard Stops (Caveman Compressed)

> Violate any → stop immediately, escalate human.
> **Full ref**: `docs/REDLINES_full.md` (on-demand)

---

## Top 5 (Always Loaded at BOOT)
1. **No overwrite without backup.** `.bak` existing config before write. No exceptions.
2. **No destructive ops without confirmation.** `rm -rf`, force-push, drop table, bulk-delete → stop, wait human.
3. **No secrets in logs/state.** Never write keys/tokens/passwords to session_state, journal, tool logs.
4. **No auto-resume crashed sessions.** Detect → read state → ask human. Never resume without approval.
5. **No skipping verification.** Every deploy/change ends with verify or read-back. Skip = fail.

---

## Additional (Load `docs/REDLINES_full.md` for Detail)
6. No configs for undetected tools — detection sacred.
7. No canon drift — entry files generated from canon, don't edit directly.
8. No hardcoded paths — use registry + env expansion.
9. No scope creep — deploy harness, don't build features.
10. No reading never-read list — large files (logs, reports >1MB) grep-only.
11. No fabricating detection — "not detected" ≠ "synced".
12. No silent failure — report error verbatim + path.
13. No modifying deployer's own canon during deploy.
14. No reading all `loop_state/*.md` at BOOT — read registry first, then one file.
15. No modifying `HANDOFF_LETTER.md` — runtime edits → `.agents/handoff_letter.md`.
16. No explanatory comments in generated code — comments are debt (arXiv 2605.02741).
17. No in-file version stacking — version truth = git + CHANGELOG.md.
18. No new canon/skill without passing 5-question existence gate.
19. **No skipping Plan phase for M-tier+** — `plan_enforce.py` blocks Write/Edit without approved plan. Use `plan_orchestrator.py`.
20. **No bypassing `plan_orchestrator.py`** — Plan phase must run via orchestrator FSM, not manually. Ensures all steps (SCOUTs, adversarial review, SDD approval, QC, plan approval) execute in order.

---

## Enforcement Layers
| Layer | Bypassable? |
|-------|-------------|
| Prompt | Yes — can ignore |
| Hook | If in repo, model could edit |
| Tool design | Model could try raw shell |
| OS/Account/IAM | **No** — physically cannot |

**Rule**: Use hardest practical layer. OS > hook > tool design > prompt.

---

## L0-L4 Permission Taxonomy
| Tier | Approval? | Example |
|------|-----------|---------|
| L0 | No | grep, ls, read public file |
| L1 | Depends | Read private DB |
| L2 | Usually no | Edit file, git add |
| L3 | **Yes** | git push, deploy, send email |
| L4 | **Mandatory + 2nd verifier** | rm -rf, drop table, payment |

Unclassified = L4 (deny by default).

---

## Risk Formula: Permission × Automation × Trust
Cut one factor → incident probability drops 10x. Cut Permission (OS level) if only one.