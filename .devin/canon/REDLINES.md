# Red Lines — Hard Stops (Top 5 + Summary)

> Violating any line → stop work immediately, escalate to human.
> **Full reference**: `docs/REDLINES_full.md` (load on-demand for detail)

## Top 5 Red Lines (always loaded at BOOT)

1. **No overwrite without backup.** `.bak` existing config before writing. No exceptions.
2. **No destructive ops without confirmation.** rm -rf, force-push, drop table, bulk-delete → stop, wait for human.
3. **No secrets in logs/state.** Never write keys/tokens/passwords into session_state, journal, or tool logs.
4. **No auto-resume crashed sessions.** Detect → read state → ask human. Never resume without approval.
5. **No skipping verification.** Every deploy/change ends with verify or read-back. Skip = fail.

## Additional red lines (load `docs/REDLINES_full.md` for detail)

6. No configs for undetected tools — detection is sacred.
7. No canon drift — entry files generated from canon, don't edit directly.
8. No hardcoded paths — use registry + env expansion.
9. No scope creep — deploy harness, don't build features.
10. No reading never-read list — large files (logs, reports >1MB) are grep-only.
11. No fabricating detection results — "not detected" ≠ "synced".
12. No silent failure — report error verbatim + path.
13. No modifying deployer's own canon during deploy.
14. No reading all `loop_state/*.md` at BOOT — read registry first, then one file.
15. No modifying `HANDOFF_LETTER.md` — runtime edits go to `.agents/handoff_letter.md`.
16. No explanatory comments in generated code — comments are debt (arXiv 2605.02741).
17. No in-file version stacking — version truth = git + CHANGELOG.md.
18. No new canon/skill without passing the 5-question existence gate.

## Enforcement layers (full detail in docs/REDLINES_full.md)

| Layer | Bypassable? |
|-------|-------------|
| Prompt | Yes — can ignore |
| Hook | If in repo, model could edit |
| Tool design | Model could try raw shell |
| OS/Account/IAM | No — physically cannot |

**Rule**: Use hardest practical layer. OS > hook > tool design > prompt.

## L0-L4 permission taxonomy

| Tier | Approval? | Example |
|------|-----------|---------|
| L0 | No | grep, ls, read public file |
| L1 | Depends | Read private DB |
| L2 | Usually no | Edit file, git add |
| L3 | **Yes** | git push, deploy, send email |
| L4 | **Mandatory + 2nd verifier** | rm -rf, drop table, payment |

Unclassified = L4 (deny by default).

## Risk formula: Permission × Automation × Trust

Cut one factor → incident probability drops 10x. Cut Permission (OS level) if can only cut one.
