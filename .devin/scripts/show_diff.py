#!/usr/bin/env python3
"""
show_diff.py — hiển thị diff summary giữa bản vendored và upstream cho một source.

Cách dùng:
    python .devin/scripts/show_diff.py --source-id <id> [--tracker PATH] [--force]

Lưu ý:
- `git diff --no-index` luôn return exit code 1 khi có khác biệt; đây là bình thường.
- URL upstream phải là HTTPS từ host tin cậy.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from update_common import (
    REPO_ROOT,
    guard_main_branch,
    load_tracker,
    run_cmd,
    validate_git_url,
)

DEFAULT_TRACKER = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"


def clone_repo(url: str, dest: Path, branch: str = "main", depth: int = 50) -> bool:
    """Clone repo upstream tạm."""
    ok, msg = validate_git_url(url)
    if not ok:
        # Không in msg (có thể chứa dữ liệu phái sinh từ url) ra stderr
        # để tránh clear-text logging sensitive data (CodeQL).
        print("[ERROR] Git URL validation failed", file=sys.stderr)
        return False

    if dest.exists():
        shutil.rmtree(dest)

    # Clone depth mặc định 50; tăng nếu cần bằng --depth
    cmd = ["git", "clone", f"--depth={depth}", "--branch", branch, url, str(dest)]
    code, out, err = run_cmd(cmd, timeout=120)
    if code != 0:
        print(f"[FAIL] git clone: {err or out}", file=sys.stderr)
        return False
    return True


def parse_repo_url(url: str) -> tuple[str, str] | None:
    """Trích owner/repo từ URL GitHub."""
    clean = url.rstrip("/").replace(".git", "")
    parts = clean.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Show diff between local and upstream for a source.")
    parser.add_argument("--source-id", required=True, help="Source ID (xem trong .devin/metadata/REPOS_TRACKER.json)")
    parser.add_argument("--tracker", default=str(DEFAULT_TRACKER))
    parser.add_argument("--force", action="store_true", help="Cho phép chạy trên main/master")
    args = parser.parse_args()

    if not guard_main_branch(args.force):
        return 1

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
    if not clone_repo(url, tmp, branch):
        return 1

    if not vendored_path:
        # Liệt kê file upstream
        for f in tmp.rglob("*"):
            if f.is_file() and ".git" not in f.parts:
                print(f"[UPSTREAM] {f.relative_to(tmp)}")
        return 0

    target = REPO_ROOT / vendored_path
    if not target.exists():
        print(f"[ERROR] Target path does not exist: {target}", file=sys.stderr)
        return 1

    # So sánh recursive
    cmd = ["git", "diff", "--no-index", "--stat", str(target), str(tmp)]
    proc_code, out, err = run_cmd(cmd, timeout=60)
    # git diff --no-index luôn return 1 khi có diff — bình thường
    print(out or err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
