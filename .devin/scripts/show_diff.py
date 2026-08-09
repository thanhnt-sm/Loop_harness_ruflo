#!/usr/bin/env python3
"""
show_diff.py — hiển thị diff summary giữa bản vendored và upstream cho một source.

Cách dùng:
    python .devin/scripts/show_diff.py --source-id <id> [--tracker PATH]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACKER = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"


def load_tracker(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clone_repo(url: str, dest: Path, branch: str = "main", depth: int = 10) -> bool:
    cmd = ["git", "clone", f"--depth={depth}", "--branch", branch, url, str(dest)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        print(f"[FAIL] git clone: {proc.stderr or proc.stdout}")
        return False
    return True


def parse_repo_url(url: str) -> tuple[str, str] | None:
    clean = url.rstrip("/").replace(".git", "")
    parts = clean.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Show diff between local and upstream for a source.")
    parser.add_argument("--source-id", required=True, help="Source ID")
    parser.add_argument("--tracker", default=str(DEFAULT_TRACKER))
    args = parser.parse_args()

    tracker = load_tracker(Path(args.tracker))
    source = next((s for s in tracker.get("sources", []) if s.get("id") == args.source_id), None)
    if not source:
        print(f"[ERROR] Source not found: {args.source_id}", file=sys.stderr)
        return 1

    url = source.get("url", "")
    branch = source.get("branch", "main")
    vendored_path = source.get("vendored_path", "")

    if not url:
        print("[ERROR] No URL", file=sys.stderr)
        return 1

    tmp = Path(tempfile.gettempdir()) / f"{args.source_id}-diff"
    if tmp.exists():
        shutil.rmtree(tmp)

    if not clone_repo(url, tmp, branch):
        return 1

    target = REPO_ROOT / vendored_path if vendored_path else None
    if target and target.exists():
        # So sánh recursive
        cmd = ["git", "diff", "--no-index", "--stat", str(target), str(tmp)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        # git diff --no-index exit 1 là bình thường
        print(proc.stdout or proc.stderr)
    else:
        # Liệt kê file upstream
        for f in tmp.rglob("*"):
            if f.is_file() and ".git" not in f.parts:
                print(f"[UPSTREAM] {f.relative_to(tmp)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
