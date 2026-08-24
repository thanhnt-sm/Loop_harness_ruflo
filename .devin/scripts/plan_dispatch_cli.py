#!/usr/bin/env python3
"""plan_dispatch_cli.py — CLI entry point for plan_dispatch.

Module containing the main() function for command-line invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .plan_dispatch import analyze
    from .plan_dispatch_parse import _plan_to_subtasks
except ImportError:  # pragma: no cover - fallback for direct script execution
    from plan_dispatch import analyze
    from plan_dispatch_parse import _plan_to_subtasks


# Worktree script location
try:
    import ahd_session
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session

ROOT = ahd_session.get_repo_root()
if (ROOT / "scripts" / "worktree.py").exists():
    WORKTREE_SCRIPT = ROOT / "scripts" / "worktree.py"
else:
    WORKTREE_SCRIPT = ahd_session.get_config_root(ROOT) / "scripts" / "worktree.py"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Analyze subtasks for file ownership, conflicts, and Nuwa angle assignment."
    )
    ap.add_argument("--analyze", action="store_true", help="Run analysis")
    ap.add_argument("--subtasks", help="Path to subtasks.json")
    ap.add_argument("--plan", help="Path to IMPLEMENTATION_PLAN.md (derive subtasks from plan)")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    ap.add_argument("--session", default="", help="Session ID to prefix worktree names")
    args = ap.parse_args()

    if not args.analyze:
        ap.print_help()
        return 1

    if not args.subtasks and not args.plan:
        print("  [!] Cần --subtasks <file.json> hoặc --plan <plan.md>")
        return 1

    if args.subtasks:
        subtask_path = Path(args.subtasks)
        if not subtask_path.exists():
            print(f"  [!] Subtasks file not found: {subtask_path}")
            return 1
        subtasks = json.loads(subtask_path.read_text(encoding="utf-8-sig"))
    else:
        plan_path = Path(args.plan)
        if not plan_path.exists():
            print(f"  [!] Plan file not found: {plan_path}")
            return 1
        subtasks = _plan_to_subtasks(plan_path)

    if not subtasks:
        print("  [!] No subtasks found.")
        return 1

    result = analyze(subtasks, args.session)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("== Agent Harness Deploy Dispatch Planner ==")
        print()
        for st in result["subtasks"]:
            tag = "PARALLEL" if st["parallel_safe"] else "SERIAL"
            print(f"  [{tag}] {st['id']}: {st['goal']}")
            print(f"         Worktree: {st['worktree']}")
            print(f"         Owned:    {st['owned_files']}")
            if st["shared_files"]:
                print(f"         Shared:   {st['shared_files']} (wait for owner)")
            print(f"         Nuwa:     {st['nuwa_angles']}")
            if st["conflicts"]:
                for c in st["conflicts"]:
                    print(f"         Conflict: {c['file']} (with {c['subtasks']})")
            print()

        if result["conflicts"]:
            print("  Conflicts:")
            for c in result["conflicts"]:
                print(f"    {c['file']}: {c['subtasks']} -> {c['resolution']}")
            print()

        # Deadlock detection output
        if result.get("deadlock_detected"):
            print("  [!] DEADLOCK DETECTED — circular dependency:")
            print(f"      Cycle nodes: {result['cycle_nodes']}")
            print("      Escalate to human. Cannot auto-resolve.")
            print()
        else:
            print(f"  Dispatch order: {result.get('dispatch_order', [])}")
            groups = result.get("parallel_groups", [])
            if groups:
                print("  Parallel groups:")
                for i, group in enumerate(groups):
                    print(f"    Level {i}: {group} (run in parallel)")
            print()

        print(f"  Worktrees: {result['worktrees']}")
        print(f"  Summary:   {result['summary']}")
        print()
        print("  Next:")
        worktree_rel = WORKTREE_SCRIPT.relative_to(ROOT)
        for wt in result["worktrees"]:
            print(f"    python {worktree_rel} create {wt} --session {args.session}")
        print("    (dispatch Workers with owned_files from above)")
        print("    (after all report: merge each worktree, then clean)")

    return 0