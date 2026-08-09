#!/usr/bin/env python3
"""
merge_updates.py — merge an toàn một nguồn từ REPOS_TRACKER.

Cách dùng:
    python .devin/scripts/merge_updates.py --source-id <id> [--dry-run]

Logic:
1. Đọc REPOS_TRACKER.json.
2. Tìm source theo id.
3. Kiểm tra impact zone: nếu chứa HLK/ hoặc file protected → BLOCK.
4. Backup thư mục đích.
5. Clone / fetch upstream tạm.
6. Apply thay đổi (copy hoặc cherry-pick tùy strategy).
7. Chạy verify-workspace.ps1 và hlk-verify-integrity.js.
8. Nếu FAIL → rollback.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"
DEFAULT_BACKUP = REPO_ROOT / "backups"


def load_tracker(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tracker(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str, str]:
    """Chạy lệnh và trả (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def verify_workspace() -> bool:
    """Chạy verify-workspace.ps1 và hlk-verify-integrity.js."""
    ok = True
    for script in [
        ["pwsh", "tools/verify-workspace.ps1"],
        ["node", "HLK/wrappers/hlk-verify-integrity.js"],
    ]:
        code, out, err = run_cmd(script, cwd=REPO_ROOT, timeout=180)
        if code != 0:
            print(f"[FAIL] {' '.join(script)} exit {code}")
            print(out or err)
            ok = False
    return ok


def is_protected(path: str, protected: list[str]) -> bool:
    """Kiểm tra path có nằm trong danh sách protected không."""
    norm = Path(path).as_posix().lower()
    for p in protected:
        pl = p.lower()
        if pl.endswith("/**"):
            prefix = pl[:-3]
            if norm == prefix or norm.startswith(prefix + "/"):
                return True
        elif norm == pl or norm.startswith(pl + "/"):
            return True
    return False


def backup_directory(src: Path, label: str) -> Path:
    """Tạo backup timestamped."""
    DEFAULT_BACKUP.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = DEFAULT_BACKUP / f"{label}-{timestamp}"
    shutil.copytree(src, dest, dirs_exist_ok=True)
    print(f"[OK] Backup: {dest}")
    return dest


def clone_repo(url: str, dest: Path, depth: int = 50) -> bool:
    """Clone repo upstream tạm."""
    cmd = ["git", "clone", f"--depth={depth}", url, str(dest)]
    code, out, err = run_cmd(cmd, timeout=180)
    if code != 0:
        print(f"[FAIL] git clone: {err or out}")
        return False
    return True


def apply_copy(source: dict[str, Any], upstream: Path, target: Path, protected: list[str]) -> int:
    """Copy các file từ upstream vào target, bỏ qua protected."""
    copied = 0
    for src in upstream.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(upstream).as_posix()
        if is_protected(str(target / rel), protected):
            print(f"[SKIP] protected: {rel}")
            continue
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Tránh copy file .git
        if ".git" in rel.split("/"):
            continue
        shutil.copy2(src, dst)
        copied += 1
    return copied


def source_id_to_label(sid: str) -> str:
    return sid.replace("/", "-").replace("\\", "-")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely merge an upstream source.")
    parser.add_argument("--source-id", required=True, help="Source ID from REPOS_TRACKER.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without applying")
    parser.add_argument("--tracker", default=str(TRACKER), help="Path to tracker")
    args = parser.parse_args()

    tracker_path = Path(args.tracker)
    if not tracker_path.exists():
        print(f"[ERROR] Tracker not found: {tracker_path}", file=sys.stderr)
        return 1

    tracker = load_tracker(tracker_path)
    source = next((s for s in tracker.get("sources", []) if s.get("id") == args.source_id), None)
    if not source:
        print(f"[ERROR] Source not found: {args.source_id}", file=sys.stderr)
        return 1

    if source.get("status") == "up-to-date":
        print(f"[INFO] {args.source_id} is up-to-date; nothing to merge.")
        return 0

    if source.get("status") == "reference-only":
        print(f"[WARN] {args.source_id} is reference-only; manual canon update required.")
        return 0

    strategy = source.get("merge_strategy", "")
    impact = source.get("impact_zone", [])
    protected = source.get("protected_files", [])
    url = source.get("url", "")
    vendored_path = source.get("vendored_path", "")

    if any(is_protected(p, protected) for p in impact):
        print(f"[BLOCK] Impact zone contains protected files. Aborting.")
        return 1

    target = None
    if vendored_path:
        target = REPO_ROOT / vendored_path
    elif strategy == "surgical-cherry-pick":
        print(f"[INFO] Surgical cherry-pick for {args.source_id} not yet automated; use manual flow.")
        return 0
    else:
        print(f"[ERROR] Unknown merge strategy: {strategy}", file=sys.stderr)
        return 1

    if not target or not target.exists():
        print(f"[ERROR] Target path does not exist: {target}", file=sys.stderr)
        return 1

    print(f"[START] Merging {args.source_id} into {target}")
    if args.dry_run:
        print("[DRY-RUN] No files will be modified.")

    backup = backup_directory(target, f"{source_id_to_label(args.source_id)}-pre-merge")

    if not clone_repo(url, Path(tempfile.gettempdir()) / f"{args.source_id}-upstream"):
        return 1
    upstream = Path(tempfile.gettempdir()) / f"{args.source_id}-upstream"

    if args.dry_run:
        print(f"[DRY-RUN] Would copy from {upstream} to {target}, skipping protected files.")
        return 0

    copied = apply_copy(source, upstream, target, protected)
    print(f"[INFO] Copied {copied} files.")

    if verify_workspace():
        print(f"[OK] Verify passed. {args.source_id} merged successfully.")
        # Cập nhật tracker
        source["current_commit"] = source.get("upstream_commit", "")
        source["current_commit_full"] = source.get("upstream_commit_full", "")
        source["status"] = "up-to-date"
        save_tracker(tracker_path, tracker)
        return 0
    else:
        print(f"[ROLLBACK] Verify failed; restoring from backup {backup}")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(backup, target, dirs_exist_ok=True)
        if not verify_workspace():
            print("[CRITICAL] Rollback verify also failed. Manual intervention required.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
