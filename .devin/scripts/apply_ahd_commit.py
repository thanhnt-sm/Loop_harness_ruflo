#!/usr/bin/env python3
"""
apply_ahd_commit.py — Commit và rollback logic cho AHD patch.

Chứa: commit_changes, rollback_patched_files, snapshot_rollback, record_ahd_apply.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import update_common

from apply_ahd_map import REPO_ROOT, TRACKER_PATH, get_protected_files
from apply_ahd_verify import run_cmd


def _audit_log(event: str, **kwargs: Any) -> None:
    """Ghi security event vào .devin/logs/security_audit.log."""
    log_dir = REPO_ROOT / ".devin" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "security_audit.log"
    entry = {"event": event, **kwargs}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def commit_changes(sha: str, msg: str, auto_commit: bool) -> bool:
    run_cmd(["git", "add", "-A"], cwd=REPO_ROOT)
    code, out, _ = run_cmd(["git", "diff", "--cached", "--stat"], cwd=REPO_ROOT)
    if not out.strip():
        return True
    if not auto_commit:
        print("[INFO] Staged changes. Run `git commit` manually to approve.")
        print(out)
        return True
    code, out, err = run_cmd([
        "git", "commit", "-m", f"cherry-pick AHD {sha}: {msg}",
        "-m", "Path-mapped from upstream masteryee-labs/Tool.Agent-Harness-Deploy.",
        "-m", "Verified: verify-workspace.ps1 + hlk-verify-integrity.js PASS.",
        "-m", "Generated with [Devin](https://devin.ai)",
        "-m", "Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>",
    ], cwd=REPO_ROOT)
    if code != 0:
        print(f"[FAIL] commit: {err}")
        return False
    return True


def rollback_patched_files(patched_files: list[str]) -> None:
    """Rollback chỉ các file đã patch."""
    if not patched_files:
        return
    cmd = ["git", "checkout", "--"]
    for pf in patched_files:
        target = REPO_ROOT / pf
        if target.exists():
            cmd.append(pf)
    run_cmd(cmd, cwd=REPO_ROOT)
    _audit_log("rollback-executed", files=patched_files)


def snapshot_rollback(head_before: str) -> None:
    """Rollback toàn bộ working tree về snapshot trước khi apply commit."""
    if not head_before:
        return
    run_cmd(["git", "reset", "--hard", head_before], cwd=REPO_ROOT)
    run_cmd(["git", "clean", "-fd"], cwd=REPO_ROOT)
    _audit_log("snapshot-rollback-executed", head_before=head_before)


def record_ahd_apply(source_id: str, sha: str, upstream: Path) -> None:
    """Ghi nhận commit đã apply vào REPOS_TRACKER.json (R01)."""
    tracker = update_common.load_tracker(TRACKER_PATH)

    found = False
    for s in tracker.get("sources", []):
        if s.get("id") == source_id:
            found = True
            s["current_commit"] = sha[:7]
            s["current_commit_full"] = sha
            s["status"] = "up-to-date"
            s["last_checked"] = datetime.now(timezone.utc).isoformat()
            break

    if not found:
        # Nếu chưa có source, thêm mới (trường hợp apply thủ công)
        tracker.setdefault("sources", []).append({
            "id": source_id,
            "type": "repo",
            "url": str(upstream),
            "branch": "main",
            "current_commit": sha[:7],
            "current_commit_full": sha,
            "upstream_commit": sha[:7],
            "upstream_commit_full": sha,
            "status": "up-to-date",
            "merge_strategy": "surgical-cherry-pick",
        })

    try:
        update_common.save_tracker(TRACKER_PATH, tracker)
        print(f"[OK] Tracker updated: {source_id} -> {sha[:7]}")
    except Exception as e:
        print(f"[WARN] Cannot save tracker after apply: {e}")