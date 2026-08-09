#!/usr/bin/env python3
"""migrate.py — Clean up legacy global config pollution from old AHD versions.

Old versions of Agent Harness Deploy (before the scope fix) wrote to global MCP
files even without --global. This affected 4 tools that have global-only MCP paths:

  - Claude Desktop:  ${APPDATA}/Claude/claude_desktop_config.json
  - Cline:           ${HOME}/.cline/data/settings/cline_mcp_settings.json
  - Roo Code:        ${HOME}/.roo/data/settings/roo_mcp_settings.json
  - Windsurf:        ${HOME}/.codeium/windsurf/mcp_config.json

(Continue was NOT affected — its mcp_template is null, so _merge_mcp was never called.)

The old code created a .bak backup before modifying these files. This script:

  1. Scans all 4 global MCP locations for .bak files from old deploys.
  2. For each .bak found:
     - Compares current file's mcpServers with .bak's mcpServers (after stripping
       _-prefixed keys, which old AHD removed).
     - If they match → no user changes since the old deploy → safe to restore
       from .bak, then remove .bak.
     - If they differ → user added/removed MCP servers after the old deploy →
       skip restore, keep .bak, warn the user to review manually.
  3. Reports what was cleaned / what needs manual attention.

Usage:
    python scripts/migrate.py              # detect + auto-restore where safe
    python scripts/migrate.py --report     # detect + report only (no writes)
    python scripts/migrate.py --restore    # force restore from .bak (even if unsafe)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.base import expand, load_registry  # noqa: E402


def _clean_servers(servers: dict) -> dict:
    """Strip _-prefixed keys from an mcpServers dict (what old AHD did)."""
    cleaned = {}
    for name, cfg in servers.items():
        if name.startswith("_"):
            continue
        if isinstance(cfg, dict):
            cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
        cleaned[name] = cfg
    return cleaned


def _get_mcp_servers_json(path: Path) -> dict | None:
    """Extract mcpServers from a JSON MCP config file. Returns None on parse error."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("mcpServers", {}) if isinstance(data, dict) else {}
    except Exception:
        return None


def _has_ahd_marker(bak_path: Path) -> bool:
    """Check if a .bak file has an AHD-managed sidecar marker.

    New AHD versions write a ``<bak_path>.ahd_managed`` sidecar when creating
    .bak files via --global deploy. Old AHD versions didn't write this marker.
    migrate.py only restores .bak files WITHOUT the marker (legacy pollution).
    """
    marker_path = Path(str(bak_path) + ".ahd_managed")
    return marker_path.exists()


def find_legacy_global_mcp_paths() -> list[tuple[str, Path, Path]]:
    """Find all global-scoped MCP files that old AHD could have polluted.

    Returns list of (tool_id, mcp_path, bak_path) tuples.
    Only includes tools where mcp_file is absolute AND mcp_template is non-null
    (the two conditions required for old _merge_mcp to have written).
    """
    reg = load_registry()
    results = []
    for tool in reg["tools"]:
        rt = tool.get("runtime", {})
        mcp_file = rt.get("mcp_file")
        mcp_template = rt.get("mcp_template")
        if not mcp_file or not mcp_template:
            continue
        expanded = expand(mcp_file)
        if not os.path.isabs(expanded):
            continue  # project-scoped, not affected
        mcp_path = Path(expanded)
        bak_path = mcp_path.with_suffix(mcp_path.suffix + ".bak")
        results.append((tool["id"], mcp_path, bak_path))
    return results


def check_one(tool_id: str, mcp_path: Path, bak_path: Path) -> dict:
    """Check one global MCP location for legacy pollution.

    Returns a dict with:
      - status: "clean" | "safe_restore" | "unsafe_skip" | "no_bak" | "managed"
      - detail: human-readable explanation
      - mcp_path, bak_path

    Status meanings:
      - "clean": no file, no .bak — nothing to do
      - "no_bak": file exists but no .bak — cannot auto-restore
      - "managed": .bak has AHD marker — created by new AHD --global, NOT legacy pollution, skip
      - "safe_restore": .bak without marker, no user changes since old deploy — safe to restore
      - "unsafe_skip": .bak without marker, but user changed mcpServers — manual review needed
    """
    if not bak_path.exists():
        if mcp_path.exists():
            return {"status": "no_bak", "detail": "file exists but no .bak — cannot auto-restore",
                    "tool_id": tool_id, "mcp_path": mcp_path, "bak_path": bak_path}
        return {"status": "clean", "detail": "no file, no .bak — nothing to clean",
                "tool_id": tool_id, "mcp_path": mcp_path, "bak_path": bak_path}

    # .bak exists — check if it's managed by new AHD (has sidecar marker).
    # New AHD --global deploys create .bak WITH a marker. These are normal backups,
    # NOT legacy pollution. migrate.py must NOT restore them — doing so would
    # undo the user's intentional --global deploy.
    if _has_ahd_marker(bak_path):
        return {"status": "managed",
                "detail": ".bak has AHD marker — created by new AHD --global deploy, not legacy pollution, skipping",
                "tool_id": tool_id, "mcp_path": mcp_path, "bak_path": bak_path}

    # .bak exists — check if safe to restore
    if not mcp_path.exists():
        # File was deleted but .bak remains — safe to restore
        return {"status": "safe_restore", "detail": "file deleted, .bak exists — restoring",
                "tool_id": tool_id, "mcp_path": mcp_path, "bak_path": bak_path}

    # Both exist — compare mcpServers
    current_servers = _get_mcp_servers_json(mcp_path)
    bak_servers = _get_mcp_servers_json(bak_path)

    if current_servers is None or bak_servers is None:
        # Can't parse as JSON — can't safely compare. Let user decide.
        return {"status": "unsafe_skip", "detail": "cannot parse JSON — manual review needed",
                "tool_id": tool_id, "mcp_path": mcp_path, "bak_path": bak_path}

    # Strip _-prefixed keys (what old AHD did) and compare
    current_clean = _clean_servers(current_servers)
    bak_clean = _clean_servers(bak_servers)

    if current_clean == bak_clean:
        return {"status": "safe_restore",
                "detail": "no user changes to mcpServers since old deploy — safe to restore",
                "tool_id": tool_id, "mcp_path": mcp_path, "bak_path": bak_path}
    else:
        current_names = set(current_clean.keys())
        bak_names = set(bak_clean.keys())
        added = current_names - bak_names
        removed = bak_names - current_names
        parts = []
        if added:
            parts.append(f"added: {sorted(added)}")
        if removed:
            parts.append(f"removed: {sorted(removed)}")
        return {"status": "unsafe_skip",
                "detail": f"user changed mcpServers ({'; '.join(parts)}) — manual review needed",
                "tool_id": tool_id, "mcp_path": mcp_path, "bak_path": bak_path}


def run_migration(*, report_only: bool = False, force_restore: bool = False) -> int:
    """Run the migration. Returns 0 if all clean/safe, 1 if manual attention needed."""
    paths = find_legacy_global_mcp_paths()

    print("== Agent Harness Deploy — Legacy Global MCP Cleanup ==")
    print(f"Scanning {len(paths)} global MCP locations for old-deploy pollution...")
    print()

    restored = 0
    skipped_unsafe = 0
    already_clean = 0
    no_bak = 0
    managed = 0

    for tool_id, mcp_path, bak_path in paths:
        result = check_one(tool_id, mcp_path, bak_path)
        status = result["status"]
        icon = {"clean": "[-]", "safe_restore": "[+]", "unsafe_skip": "[!]",
                "no_bak": "[?]", "managed": "[=]"}.get(status, "[?]")

        print(f"  {icon} {tool_id:20} {mcp_path}")
        print(f"      {result['detail']}")

        if status == "clean":
            already_clean += 1
            continue

        if status == "managed":
            managed += 1
            continue

        if status == "no_bak":
            no_bak += 1
            continue

        if status == "safe_restore":
            if report_only:
                print(f"      (report mode — would restore from {bak_path})")
            else:
                shutil.copy2(bak_path, mcp_path)
                bak_path.unlink()
                # Also remove the marker sidecar if it exists (cleanup)
                marker = Path(str(bak_path) + ".ahd_managed")
                if marker.exists():
                    marker.unlink()
                print(f"      restored from .bak, .bak removed")
                restored += 1
            continue

        if status == "unsafe_skip":
            if force_restore and not report_only:
                shutil.copy2(bak_path, mcp_path)
                bak_path.unlink()
                marker = Path(str(bak_path) + ".ahd_managed")
                if marker.exists():
                    marker.unlink()
                print(f"      FORCE restored from .bak (--restore), .bak removed")
                restored += 1
            else:
                skipped_unsafe += 1
                if not report_only:
                    print(f"      kept .bak for manual review")
            continue

    print()
    print(f"Summary: restored={restored}  unsafe={skipped_unsafe}  "
          f"clean={already_clean}  no_bak={no_bak}  managed={managed}")

    if skipped_unsafe > 0:
        print()
        print("Some global MCP files have user changes and were NOT auto-restored.")
        print("To review: compare the .bak with the current file, merge manually if needed.")
        print("To force-restore anyway: python scripts/migrate.py --restore")
        return 1

    if no_bak > 0:
        print()
        print("Some global MCP files exist but have no .bak — cannot auto-restore.")
        print("These files may have been reformatted by old AHD but the original is lost.")
        print("The damage is cosmetic (JSON reformatting + _-prefixed keys stripped).")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Clean up legacy global MCP pollution from old AHD versions.")
    ap.add_argument("--report", action="store_true",
                    help="detect + report only, no writes")
    ap.add_argument("--restore", action="store_true",
                    help="force restore from .bak even if user changes detected (destructive)")
    args = ap.parse_args()

    if args.report and args.restore:
        print("Cannot use --report and --restore together.", file=sys.stderr)
        return 2

    return run_migration(report_only=args.report, force_restore=args.restore)


if __name__ == "__main__":
    sys.exit(main())
