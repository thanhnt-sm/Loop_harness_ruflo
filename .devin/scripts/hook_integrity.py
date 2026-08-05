#!/usr/bin/env python3
"""U41: Hook integrity verification (SHA256).

Verifies that hook files haven't been tampered with by comparing
SHA256 hashes against a trusted baseline.

Usage:
    python .devin/scripts/hook_integrity.py --generate  # Generate baseline
    python .devin/scripts/hook_integrity.py --verify    # Verify against baseline
    python .devin/scripts/hook_integrity.py --status     # Show status
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


HOOKS_DIR = ".devin/hooks"
BASELINE_FILE = ".devin/hook_hashes.json"


def compute_sha256(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_hook_files(root: Path) -> list[Path]:
    """Get all hook files."""
    hooks_dir = root / HOOKS_DIR
    if not hooks_dir.exists():
        return []
    return sorted(hooks_dir.glob("*.py"))


def generate_baseline(root: Path) -> int:
    """Generate SHA256 baseline for all hooks."""
    hooks = get_hook_files(root)
    if not hooks:
        print("[ERROR] No hook files found")
        return 1

    baseline = {}
    for h in hooks:
        rel = str(h.relative_to(root)).replace("\\", "/")
        baseline[rel] = compute_sha256(h)
        print(f"[HASH] {rel}: {baseline[rel][:16]}...")

    baseline_path = root / BASELINE_FILE
    baseline_data = {
        "_description": "U41: Hook integrity verification baseline",
        "_generated": str(Path.now() if hasattr(Path, 'now') else ""),
        "hooks": baseline,
    }

    from datetime import datetime
    baseline_data["_generated"] = datetime.now().isoformat()

    baseline_path.write_text(json.dumps(baseline_data, indent=2), encoding="utf-8")
    print(f"\n[OK] Baseline generated: {baseline_path} ({len(hooks)} hooks)")
    return 0


def verify_integrity(root: Path) -> int:
    """Verify hooks against baseline."""
    baseline_path = root / BASELINE_FILE
    if not baseline_path.exists():
        print("[ERROR] No baseline found. Run --generate first.")
        return 1

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    stored = baseline.get("hooks", {})

    hooks = get_hook_files(root)
    if not hooks:
        print("[ERROR] No hook files found")
        return 1

    violations = 0
    for h in hooks:
        rel = str(h.relative_to(root)).replace("\\", "/")
        current_hash = compute_sha256(h)

        if rel not in stored:
            print(f"[NEW] {rel}: not in baseline (new hook?)")
            violations += 1
        elif stored[rel] != current_hash:
            print(f"[TAMPERED] {rel}: hash mismatch")
            print(f"  baseline: {stored[rel][:16]}...")
            print(f"  current:  {current_hash[:16]}...")
            violations += 1
        else:
            print(f"[OK] {rel}: verified")

    # Check for missing hooks (in baseline but not on disk)
    for rel in stored:
        if not (root / rel).exists():
            print(f"[MISSING] {rel}: in baseline but not on disk")
            violations += 1

    if violations == 0:
        print(f"\n[OK] All {len(hooks)} hooks verified. No tampering detected.")
        return 0
    else:
        print(f"\n[FAIL] {violations} violation(s) detected. Review above.")
        return 1


def show_status(root: Path) -> int:
    """Show integrity status."""
    baseline_path = root / BASELINE_FILE
    if not baseline_path.exists():
        print("[STATUS] No baseline generated. Run: --generate")
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    stored = baseline.get("hooks", {})
    hooks = get_hook_files(root)

    print(f"Baseline: {len(stored)} hooks")
    print(f"On disk:  {len(hooks)} hooks")
    print(f"Generated: {baseline.get('_generated', 'unknown')}")

    if len(stored) == len(hooks):
        print("[STATUS] Counts match. Run --verify for full check.")
    else:
        print("[STATUS] Count mismatch! Run --verify.")

    return 0


def main():
    import argparse
    from datetime import datetime

    ap = argparse.ArgumentParser(description="U41: Hook integrity verification")
    ap.add_argument("--generate", action="store_true", help="Generate SHA256 baseline")
    ap.add_argument("--verify", action="store_true", help="Verify against baseline")
    ap.add_argument("--status", action="store_true", help="Show status")
    ap.add_argument("--root", default=".", help="Repo root")

    args = ap.parse_args()
    root = Path(args.root).resolve()

    if args.generate:
        return generate_baseline(root)
    elif args.verify:
        return verify_integrity(root)
    elif args.status:
        return show_status(root)
    else:
        ap.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
