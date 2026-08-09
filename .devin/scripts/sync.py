#!/usr/bin/env python3
"""sync.py — Generate entry files from distill/canon/ and write to detected tools.

This is the core of the deployer. It:
  1. Reads the canonical body from distill/canon/ (concatenated, tool-agnostic).
  2. For each detected tool, calls the tool's adapter to write the body into the
     tool's native entry file location (project + optional global).
  3. Dedupes by target path (AGY CLI + Antigravity both write AGENTS.md → one write).
  4. Backs up existing files to .bak before overwriting (red line #1).

Usage:
    python scripts/sync.py                  # project-level only, for detected tools
    python scripts/sync.py --global         # also write global entry files
    python scripts/sync.py --canon          # regenerate AGENTS.md from canon (repo entry)
    python scripts/sync.py --tools claude_code,codex   # sync only listed tools
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Allow sync.py to use the shared session helper for locking
sys.path.insert(0, str(ROOT / "core" / "assets" / "runtime" / "hooks"))
import ahd_session  # noqa: E402

from adapters import get_adapter, all_tool_ids  # noqa: E402
from adapters.base import load_registry  # noqa: E402

try:
    from filelock import FileLock, Timeout
except Exception:  # pragma: no cover
    FileLock = None
    Timeout = None

CANON_DIR = ROOT / "distill" / "canon"
REPO_AGENTS_MD = ROOT / "AGENTS.md"
REPO_ENTRY_HEADER = ROOT / "distill" / "repo_entry_header.md"

# Order matters: CORE first, then protocols, then judgment/handoff, red lines last as a guard.
CANON_ORDER = [
    "CORE_CANON.md",
    "BOOT_PROTOCOL.md",
    "MEMORY_PROTOCOL.md",
    "LOOP_PROTOCOL.md",
    "VERIFICATION_PROTOCOL.md",
    "CAVEMAN_PROTOCOL.md",
    "JUDGMENT_RUBRICS.md",
    "HANDOFF_LETTER.md",
    "HARNESS_ENGINEERING.md",
    "REDLINES.md",
]


# --- Canon version-stacking guard (REDLINES.md #17) ---------------------------
# Scans canon file headers for stacked version markers / changelog blocks.
# Version truth = git history + append-only CHANGELOG.md, never in-file stacking.
# See distill/canon/REDLINES.md #17, CORE_CANON.md "Version discipline".

# Patterns that signal in-file version stacking. A single canonical front-matter
# line like "> v1.0 | ..." is allowed (one occurrence). Stacking = 2+ occurrences
# OR explicit changelog/updated markers in the body.
_VERSION_MARKER_PATTERNS = [
    re.compile(r"<!--\s*v\d+", re.IGNORECASE),            # <!-- v2 -->
    re.compile(r"^\s*#\s*v\d+\s", re.IGNORECASE),         # # v3 fixed X
    re.compile(r"<!--\s*updated\s+\d{4}", re.IGNORECASE),  # <!-- updated 2026-07-15 -->
    re.compile(r"^\s*//\s*v\d+\s", re.IGNORECASE),         # // v2
    re.compile(r"^\s*#\s*changelog", re.IGNORECASE),       # # changelog
    re.compile(r"<!--\s*changelog", re.IGNORECASE),        # <!-- changelog
    re.compile(r"^\s*#\s*\d{4}-\d{2}-\d{2}\s", re.IGNORECASE),  # # 2026-07-15 fixed
]

# A single front-matter version line is allowed (e.g. "> v1.0 | ...").
# This regex identifies the allowed single-occurrence header version line.
_ALLOWED_HEADER_VERSION = re.compile(r"^\s*>\s*v\d+\.\d+", re.IGNORECASE)


def _strip_code_spans(line: str) -> str:
    """Remove backtick-wrapped code spans from a line.

    Version markers inside code spans (e.g. `` `<!-- v2 -->` ``) are examples
    cited in rule descriptions, not real in-file markers. Stripping them prevents
    the guard from flagging the canon's own anti-pattern documentation.
    """
    return re.sub(r"`[^`]*`", "", line)


def check_canon_version_stacking() -> list[str]:
    """Scan canon files for in-file version stacking (REDLINES.md #17).

    Returns a list of violation messages (empty = clean). A file fails if:
      - 2+ version markers found in header (first 30 lines), OR
      - any explicit changelog/updated marker found anywhere in the file,
        unless it's the single allowed front-matter version line.

    Code spans (backtick-wrapped) are stripped before matching, so the canon's
    own anti-pattern examples (`` `<!-- v2 -->` ``) don't trigger false positives.

    This is a pre-sync gate: if violations exist, sync aborts with exit code 2
    so the human fixes the canon before it propagates to every tool.
    """
    violations: list[str] = []
    for fname in CANON_ORDER:
        fpath = CANON_DIR / fname
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8")
        lines = text.splitlines()
        header = lines[:30]

        # Count version markers in header (excluding the allowed front-matter line)
        header_hits = 0
        for line in header:
            if _ALLOWED_HEADER_VERSION.match(line):
                continue  # single allowed front-matter version line
            stripped = _strip_code_spans(line)
            for pat in _VERSION_MARKER_PATTERNS:
                if pat.search(stripped):
                    header_hits += 1
                    break  # one hit per line is enough

        if header_hits >= 2:
            violations.append(
                f"{fname}: {header_hits} version markers in header (first 30 lines). "
                f"Stacking detected. Move version history to CHANGELOG.md or git. "
                f"See REDLINES.md #17."
            )

        # Any changelog/updated marker anywhere = stacking (body-level)
        for i, line in enumerate(lines, 1):
            if _ALLOWED_HEADER_VERSION.match(line):
                continue
            stripped = _strip_code_spans(line)
            for pat in _VERSION_MARKER_PATTERNS:
                if pat.search(stripped):
                    violations.append(
                        f"{fname}:{i}: in-file version/changelog marker: "
                        f"{line.strip()[:80]}. Use CHANGELOG.md or git. See REDLINES.md #17."
                    )
                    break

    return violations


def build_canonical_body() -> str:
    """Concatenate canon files into one tool-agnostic body."""
    parts = []
    parts.append("# Agent Harness Deploy — Canonical Harness\n")
    parts.append("> Auto-generated from distill/canon/. Do not edit this generated file; "
                 "edit canon and re-run `python scripts/sync.py --canon`.\n")
    for fname in CANON_ORDER:
        fpath = CANON_DIR / fname
        if not fpath.exists():
            print(f"WARN: canon file missing: {fpath}", file=sys.stderr)
            continue
        parts.append(f"\n\n---\n\n<!-- source: distill/canon/{fname} -->\n")
        parts.append(fpath.read_text(encoding="utf-8").strip())
    return "\n".join(parts) + "\n"


def regenerate_repo_entry(body: str) -> None:
    """Regenerate the repo's own AGENTS.md from the header template + canon body.

    The repo AGENTS.md has two parts:
    1. A hand-maintained header (deploy contract, BOOT protocol, red lines, index) stored
       in `distill/repo_entry_header.md`.
    2. An auto-generated canonical body between CANON-BODY markers.

    This function rebuilds the full file from the header template + markers + canon body.
    This is idempotent: running it twice produces the same file.
    """
    start_marker = "<!-- CANON-BODY-START -->"
    end_marker = "<!-- CANON-BODY-END -->"

    if not REPO_ENTRY_HEADER.exists():
        print(f"WARN: header template {REPO_ENTRY_HEADER} not found; skipping repo entry regen.")
        return

    header = REPO_ENTRY_HEADER.read_text(encoding="utf-8").rstrip()
    # Replace migration placeholders for the repo's own AGENTS.md.
    # The repo entry uses .agents/ as both state root and entry dir (Antigravity-style).
    body_replaced = body.replace("{{STATE_ROOT}}", ".agents").replace("{{ENTRY_DIR}}", ".agents")
    full = (
        header
        + "\n\n---\n\n"
        + start_marker + "\n"
        + "<!-- The section below is auto-generated by `python scripts/sync.py --canon` from distill/canon/.\n"
        + "     Do not edit between the START/END markers — edit canon and re-run. -->\n\n"
        + body_replaced
        + "\n" + end_marker + "\n"
        + "<!-- End of auto-generated canon body. Content above the START marker is hand-maintained. -->\n"
    )
    # Use repo-level lock to protect AGENTS.md from concurrent writes
    ahd_session._locked_text_write(REPO_AGENTS_MD, full)
    print(f"Regenerated canon body in {REPO_AGENTS_MD} (from header template + canon)")


def sync_all(project_root: str = ".", global_too: bool = False,
             only_tools: list[str] | None = None, lock: bool = True) -> int:
    project_root_path = Path(project_root).resolve()
    lock_path = project_root_path / ".agents" / ".agent_harness_deploy.lock"
    acquired = None
    if lock and FileLock:
        acquired = FileLock(str(lock_path))
        try:
            acquired.acquire(timeout=30)
        except Timeout:
            print("[!] Could not acquire sync lock; another sync may be running. Continuing anyway.")
            acquired = None

    try:
        return _sync_all_impl(project_root, global_too, only_tools, project_root_path)
    finally:
        if acquired:
            try:
                acquired.release()
            except Exception:
                pass


def _sync_all_impl(project_root: str, global_too: bool,
                   only_tools: list[str] | None, project_root_path: Path) -> int:
    # Pre-sync gate: reject canon files with in-file version stacking (REDLINES.md #17).
    # This prevents context rot from propagating to every synced tool.
    stacking_violations = check_canon_version_stacking()
    if stacking_violations:
        print("== Canon version-stacking guard: FAIL ==", file=sys.stderr)
        print("Refusing to sync. Fix the canon before propagating to tools.", file=sys.stderr)
        for v in stacking_violations:
            print(f"  [!] {v}", file=sys.stderr)
        print("Fix: move version history to CHANGELOG.md or rely on git commits.", file=sys.stderr)
        print("See distill/canon/REDLINES.md #17.", file=sys.stderr)
        return 2

    body = build_canonical_body()
    tool_ids = only_tools or all_tool_ids()
    seen_paths: set[str] = set()  # dedupe by target path
    entry_seen: set[str] = set()  # dedupe CLI variants before they write
    entries_written = 0
    assets_written = 0
    assets_skipped = 0
    tools_skipped = 0
    failed = 0
    backups = 0

    print("== Agent Harness Deploy — Sync ==")
    for tid in tool_ids:
        adapter = get_adapter(tid, project_root=project_root)
        det = adapter.detect()
        if not det.detected:
            print(f"  [-] {adapter.name:<22} skipped (not detected)")
            tools_skipped += 1
            continue

        # Skip CLI variants that share an entry path with an already-synced tool.
        # This prevents e.g. codex from writing correctly, then codex_cli overwriting
        # with a lower-specificity rewrite.
        entry_keys = set()
        for p in (adapter.project_entry_path(), adapter.global_entry_path()):
            if p:
                entry_keys.add(str(p).lower())
        if entry_keys & entry_seen:
            print(f"  [~] {adapter.name:<22} deduped (entry already synced)")
            continue
        entry_seen.update(entry_keys)

        results = adapter.sync(body, global_too=global_too)
        for r in results:
            key = str(r.target_path).lower()
            if key in seen_paths:
                print(f"  [~] {adapter.name:<22} deduped {r.target_path}")
                continue
            seen_paths.add(key)
            if r.status == "written":
                # Normalize path separators for cross-platform asset detection
                key_norm = key.replace("\\", "/")
                is_asset = "/skills/" in key_norm or "/agents/" in key_norm or "/assets/vault/" in key_norm
                if is_asset:
                    assets_written += 1
                else:
                    entries_written += 1
                if r.backup_path:
                    backups += 1
                bp = f" (backup: {r.backup_path})" if r.backup_path else ""
                tag = "asset" if is_asset else "entry"
                print(f"  [+] {adapter.name:<22} wrote [{tag}] {r.target_path}{bp}")
            elif r.status == "skipped":
                assets_skipped += 1
                print(f"  [=] {adapter.name:<22} identical {r.target_path}")
            elif r.status == "failed":
                failed += 1
                print(f"  [!] {adapter.name:<22} FAILED {r.target_path}: {r.error}")

    print()
    print(f"Summary: entries={entries_written}  assets={assets_written}  "
          f"identical={assets_skipped}  tools_skipped={tools_skipped}  "
          f"failed={failed}  backups={backups}")
    print("Next: python scripts/verify.py")

    # Regenerate repo entry after tool sync so AGENTS.md always has the header + markers.
    regenerate_repo_entry(build_canonical_body())

    return 0 if failed == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync canonical harness to detected tools.")
    ap.add_argument("--global", dest="global_too", action="store_true",
                    help="also write global entry files (~/.claude, ~/.codex, ...)")
    ap.add_argument("--canon", action="store_true",
                    help="regenerate repo AGENTS.md canon body from distill/canon/ (no-op; now always done)")
    ap.add_argument("--tools", default=None,
                    help="comma-separated tool ids to sync (default: all detected)")
    ap.add_argument("--project-root", default=".", help="project root (default: cwd)")
    args = ap.parse_args()

    only = args.tools.split(",") if args.tools else None
    rc = sync_all(project_root=args.project_root, global_too=args.global_too, only_tools=only)

    return rc


if __name__ == "__main__":
    sys.exit(main())
