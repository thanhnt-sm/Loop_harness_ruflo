#!/usr/bin/env python3
"""
apply_ahd_cli.py — CLI entry point và workspace setup cho AHD patch.

Chứa: main, guard_main_branch, setup_feature_branch, setup_worktree,
      stash_local_changes, pop_stash, validate_sha, validate_worktree_path.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import update_common

from apply_ahd_map import REPO_ROOT, get_protected_files
from apply_ahd_apply import apply_commit, get_commits
from apply_ahd_commit import record_ahd_apply
from apply_ahd_verify import run_cmd


def _audit_log(event: str, **kwargs: Any) -> None:
    """Ghi security event vào .devin/logs/security_audit.log."""
    log_dir = REPO_ROOT / ".devin" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "security_audit.log"
    entry = {"event": event, **kwargs}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def validate_sha(sha: str) -> bool:
    """SHA phải là hex 7-40 ký tự."""
    return bool(re.fullmatch(r"[0-9a-f]{7,40}", sha))


def validate_worktree_path(path: str, repo_root: Path) -> Path | None:
    """Worktree phải là relative path, không chứa .., nằm trong repo root."""
    if path.startswith(("/", "\\")) or ":" in path[:2]:
        return None
    if ".." in Path(path).parts:
        return None
    resolved = (repo_root / path).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return None
    return resolved


def guard_main_branch(force: bool) -> tuple[bool, str]:
    """Không cho chạy trực tiếp trên main/master trừ khi --force."""
    code, branch, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
    branch = branch.strip()
    if branch in ("main", "master") and not force:
        return False, branch
    return True, branch


def setup_feature_branch() -> str | None:
    """Tạo feature branch từ main. Trả về None nếu không tạo được."""
    branch = f"feat/ahd-update-{int(time.time())}"
    # Kiểm tra branch đã tồn tại chưa để tránh lỗi trùng tên
    code, out, _ = run_cmd(["git", "branch", "--list", branch], cwd=REPO_ROOT)
    if out.strip():
        branch = f"{branch}-{int(time.time() * 1000) % 1000}"
    code, _, err = run_cmd(["git", "checkout", "-b", branch], cwd=REPO_ROOT)
    if code != 0:
        print(f"[ERROR] Cannot create feature branch: {err}")
        return None
    return branch


def setup_worktree(worktree_path: Path, branch: str = "main") -> Path | None:
    """Tạo worktree từ branch. Trả về None nếu không tạo được."""
    worktree_path.mkdir(parents=True, exist_ok=True)
    # Tạo branch mới để tránh xung đột với worktree hiện có trên cùng branch
    new_branch = f"ahd-wt-{int(time.time())}"
    code, _, err = run_cmd(
        ["git", "worktree", "add", "-b", new_branch, str(worktree_path), branch],
        cwd=REPO_ROOT,
    )
    if code != 0:
        print(f"[ERROR] Cannot create worktree: {err}")
        return None
    return worktree_path


def stash_local_changes() -> bool:
    """Stash local changes chưa commit; trả về True nếu thực sự stash."""
    code, out, _ = run_cmd(["git", "status", "--short"], cwd=REPO_ROOT)
    if not out.strip():
        return False
    code, _, err = run_cmd(["git", "stash", "push", "-m", "pre-ahd-patch"], cwd=REPO_ROOT)
    if code != 0:
        print(f"[WARN] Stash failed: {err}")
        return False
    return True


def pop_stash() -> None:
    """Pop stash nếu có; thất bại thì cảnh báo chứ không crash."""
    code, _, err = run_cmd(["git", "stash", "pop"], cwd=REPO_ROOT)
    if code != 0:
        print(f"[WARN] Stash pop failed: {err}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True, help="Path to clone AHD upstream (vd: /tmp/ahd-upstream hoặc .)")
    parser.add_argument("--since", required=True, help="Ngày bắt đầu (YYYY-MM-DD)")
    parser.add_argument("--until", required=True, help="Ngày kết thúc (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen")
    parser.add_argument("--auto-commit", action="store_true", help="Auto-commit after verify (default: no)")
    parser.add_argument("--worktree", default="", help="Run in a git worktree")
    parser.add_argument("--force", action="store_true", help="Allow running on main/master or dirty workspace")
    parser.add_argument("--max-commits", type=int, default=10, help="Số commit tối đa xử lý (default: 10)")
    parser.add_argument("--allow-partial", action="store_true", help="Apply non-protected files even if commit contains protected files")
    parser.add_argument("--3way", dest="use_3way", action="store_true", help="Use 3-way merge for diverged files")
    parser.add_argument("--resolve-theirs", action="store_true", help="Resolve 3-way conflicts by preferring upstream (theirs)")
    parser.add_argument("--allow-risky-new", action="store_true", help="Allow creating new files in adapters/scripts")
    parser.add_argument("--source-id", default="", help="ID nguồn trong REPOS_TRACKER.json để tự động cập nhật current_commit sau khi apply")
    args = parser.parse_args()

    # Guard branch + workspace
    ok, branch = guard_main_branch(args.force)
    if not ok:
        print(f"[ERROR] Cannot run on '{branch}'. Use feature branch or --force.")
        return 1
    if update_common.is_dirty_workspace() and not args.force:
        print("[ERROR] Workspace có uncommitted changes. Commit/stash hoặc dùng --force.")
        return 1

    # Validate upstream/worktree paths
    upstream = Path(args.upstream) if args.upstream else Path(tempfile.gettempdir()) / "ahd-upstream"
    if not upstream.exists():
        print(f"[ERROR] Upstream not found: {upstream}")
        return 1

    worktree: Path | None = None
    if args.worktree:
        wp = validate_worktree_path(args.worktree, REPO_ROOT)
        if not wp:
            print(f"[ERROR] Invalid worktree path: {args.worktree}")
            return 1
        worktree = wp

    original_cwd = REPO_ROOT
    stashed = False
    try:
        if worktree:
            setup_worktree(worktree)
            original_cwd = worktree
        else:
            stashed = stash_local_changes()

        protected = get_protected_files()
        commits = get_commits(upstream, args.since, args.until)
        if not commits:
            print("[INFO] No commits found.")
            return 0

        if len(commits) > args.max_commits:
            print(f"[ERROR] Tìm thấy {len(commits)} commits, vượt quá --max-commits={args.max_commits}.")
            print("[HINT] Chia nhỏ khoảng thời gian hoặc tăng --max-commits một cách có chủ đích.")
            return 1

        results: list[dict[str, Any]] = []
        for sha, msg in commits:
            if not validate_sha(sha):
                print(f"[SKIP] Invalid SHA: {sha}")
                continue
            print(f"\n[COMMIT] {sha} {msg}")
            res = apply_commit(
                upstream, sha, msg, protected, args.dry_run, args.auto_commit,
                args.allow_partial, args.use_3way, args.resolve_theirs, args.allow_risky_new
            )
            results.append(res)
            print(f"  status: {res['status']}")
            if res["applied"]:
                print(f"  applied: {res['applied']}")
            if res["skipped"]:
                print(f"  skipped: {res['skipped']}")
            if res["error"]:
                print(f"  error: {res['error']}")

        # Cập nhật tracker (R01) nếu có --source-id và apply thật thành công
        if args.source_id and not args.dry_run:
            applied_shas = [r["sha"] for r in results if r["status"] == "applied"]
            if applied_shas:
                record_ahd_apply(args.source_id, applied_shas[-1], upstream)

        # Ghi report (R03: dry-run không ghi file tracked để tránh dirty workspace)
        if not args.dry_run:
            report_path = REPO_ROOT / ".devin" / "metadata" / "AHD_PATCH_REPORT.md"
            lines = ["# AHD Cherry-Pick Report", "", f"Upstream: {upstream}", f"Range: {args.since} .. {args.until}", ""]
            for r in results:
                lines.append(f"## {r['sha']} — {r['msg']}")
                lines.append(f"- **status**: {r['status']}")
                lines.append(f"- **applied**: {', '.join(r['applied']) or 'none'}")
                lines.append(f"- **skipped**: {', '.join(r['skipped']) or 'none'}")
                if r["error"]:
                    lines.append(f"- **error**: {r['error']}")
                lines.append("")
            report_path.write_text("\n".join(lines), encoding="utf-8")
            print(f"\n[OK] Report: {report_path}")
        else:
            print("\n[DRY-RUN] No tracked files modified. Report not written.")
        return 0
    finally:
        if stashed:
            pop_stash()