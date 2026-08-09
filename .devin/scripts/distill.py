#!/usr/bin/env python3
"""distill.py — The main entry point. Detect — Sync — Verify.

This is what runs when a user tells an AI "幫我部屬：[this repo's URL]" and the AI
follows AGENTS.md. It chains the three pipeline steps and prints a final report.

Usage:
    python scripts/distill.py
    python scripts/distill.py --global        # also sync global entry files
    python scripts/distill.py --tools X,Y     # sync only listed tools
    python scripts/distill.py --dry-run       # detect + report, no writes
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Windows consoles often default to a legacy codepage (cp950/cp1252) that can't encode
# box-drawing/arrow characters. Reconfigure stdout/stderr to UTF-8 so the pipeline doesn't
# crash on a UnicodeEncodeError before it even starts.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from filelock import FileLock
except Exception:
    FileLock = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.detect import detect_all  # noqa: E402
from scripts.migrate import run_migration  # noqa: E402
from scripts.sync import sync_all  # noqa: E402
from scripts.verify import verify_all  # noqa: E402

_DEPLOY_LOCK = ROOT / ".agents" / ".agent_harness_deploy.lock"


def main() -> int:
    ap = argparse.ArgumentParser(description="Agent Harness Deploy — full pipeline.")
    ap.add_argument("--global", dest="global_too", action="store_true",
                    help="also sync global entry files")
    ap.add_argument("--tools", default=None, help="comma-separated tool ids to sync")
    ap.add_argument("--dry-run", action="store_true", help="detect only, no writes")
    ap.add_argument("--no-migrate", action="store_true",
                    help="skip legacy global MCP cleanup (Step 0)")
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    print("┌───────────────────────────────────────────────────┐")
    print("│  Agent Harness Deploy — Deploy Pipeline           │")
    print("└───────────────────────────────────────────────────┘")
    print()

    # Step 0: Legacy cleanup — clean up global MCP files polluted by old AHD versions.
    # Old versions wrote to global MCP even without --global. This auto-restores
    # from .bak where safe, so updating the repo + re-deploying fixes old pollution.
    if not args.no_migrate:
        print("→ Step 0/4: Legacy global MCP cleanup...")
        run_migration(report_only=args.dry_run)
        print()
    else:
        print("→ Step 0/4: Skipped (--no-migrate)")
        print()

    # Step 1: Detect
    print("→ Step 1/4: Detecting installed AI tools...")
    det = detect_all(args.project_root)
    detected = [r for r in det if r["detected"]]
    print(f"  Found {len(detected)}/{len(det)} tools:")
    for r in detected:
        print(f"    [+] {r['name']} ({r['tool_id']})")
    if not detected:
        print("  No AI tools detected. Nothing to sync. Exiting.")
        print("  (If you have a tool installed but it wasn't detected, see Docs/12-Troubleshooting.md)")
        return 0
    print()

    if args.dry_run:
        print("Dry-run mode: stopping after detection (no writes).")
        return 0

    # Step 2: Sync (serialized against other distill/sync runs)
    print("→ Step 2/4: Generating canonical body & syncing to detected tools...")
    only = args.tools.split(",") if args.tools else None
    deploy_lock = None
    if FileLock:
        _DEPLOY_LOCK.parent.mkdir(parents=True, exist_ok=True)
        deploy_lock = FileLock(str(_DEPLOY_LOCK))
        try:
            deploy_lock.acquire(timeout=30)
        except Timeout:
            print("[!] Could not acquire deploy lock; another deploy may be running.")
            return 1

    try:
        rc = sync_all(project_root=args.project_root, global_too=args.global_too, only_tools=only, lock=False)
        print()

        # Step 3: Verify
        print("→ Step 3/4: Verifying written files (read-back)...")
        v = verify_all(args.project_root)
        for r in v["checks"]:
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"    [{mark}] {r['name']}: {r['target']}")
        print()

        # Final report
        print("┌─────────────────────────────────────────────────────────┐")
        print("│  Deploy Complete                                        │")
        print("└─────────────────────────────────────────────────────────┘")
        print(f"  Timestamp:    {datetime.now().isoformat(timespec='seconds')}")
        print(f"  Tools synced: {len(detected)}")
        print(f"  Verification: {'PASS' if v['pass'] else 'FAIL'}")
        print()
        if v["pass"]:
            print("  Open any of your AI tools now — they share the same Agent Harness Deploy harness.")
            print("  Rules: distill/canon/   |   Orchestrator: distill/orchestrator/   |   Skills: distill/skills/")
        else:
            print("  Some verification checks FAILED. Review the output above and re-run.")
            print("  See Docs/12-Troubleshooting.md for common issues.")
            return 1
        return rc
    finally:
        if deploy_lock:
            try:
                deploy_lock.release()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
