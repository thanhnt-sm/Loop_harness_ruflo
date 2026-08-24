#!/usr/bin/env python3
"""
apply_ahd_apply.py — Core apply commit logic cho AHD patch.

Chứa: apply_commit, get_commits, get_changed_files, get_file_at_rev.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import update_common

from apply_ahd_map import (
    REPO_ROOT,
    get_protected_files,
    is_protected,
    is_risky_new,
    is_upstream_skip,
    map_path,
)
from apply_ahd_merge import merge_3way
from apply_ahd_normalize import normalize_text_after_merge
from apply_ahd_commit import commit_changes, rollback_patched_files, snapshot_rollback, record_ahd_apply
from apply_ahd_verify import verify


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120, input_text: str = "") -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, input=input_text)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def validate_sha(sha: str) -> bool:
    """SHA phải là hex 7-40 ký tự."""
    return bool(re.fullmatch(r"[0-9a-f]{7,40}", sha))


def get_commits(upstream: Path, since: str, until: str) -> list[tuple[str, str]]:
    cmd = ["git", "-C", str(upstream), "log", f"--since={since}", f"--until={until}", "--oneline", "--reverse"]
    code, out, _ = run_cmd(cmd)
    if code != 0:
        return []
    return [(line[:7], line[8:].strip()) for line in out.splitlines() if line.strip()]


def get_changed_files(upstream: Path, sha: str) -> list[str]:
    cmd = ["git", "-C", str(upstream), "diff-tree", "--no-commit-id", "--name-only", "-r", sha]
    _, out, _ = run_cmd(cmd)
    return [l.strip() for l in out.splitlines() if l.strip()]


def get_file_at_rev(upstream: Path, rev: str, path: str) -> str | None:
    code, out, _ = run_cmd(["git", "-C", str(upstream), "show", f"{rev}:{path}"], timeout=30)
    return out if code == 0 else None


def apply_commit(upstream: Path, sha: str, msg: str, protected: list[str], dry_run: bool, auto_commit: bool,
                 allow_partial: bool = False, use_3way: bool = False,
                 resolve_theirs: bool = False, allow_risky_new: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"sha": sha, "msg": msg, "status": "pending", "applied": [], "skipped": [], "error": ""}
    patched_files: list[str] = []

    # Snapshot HEAD trước khi apply — dùng cho rollback an toàn
    code, head_before, _ = run_cmd(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT)
    head_before = head_before.strip() if code == 0 else ""

    files = get_changed_files(upstream, sha)
    if not files:
        result["status"] = "skipped"
        return result

    code, parent, _ = run_cmd(["git", "-C", str(upstream), "rev-parse", f"{sha}^"])
    if code != 0:
        result["status"] = "error"
        result["error"] = "cannot resolve parent"
        return result
    parent = parent.strip()

    blocked = []
    for rel in files:
        if is_upstream_skip(rel):
            continue
        mapped = map_path(rel)
        if not mapped:
            blocked.append(f"unmapped:{rel}")
            continue
        if is_protected(mapped, protected):
            blocked.append(f"protected:{mapped}")
            continue
        old_exists = get_file_at_rev(upstream, parent, rel) is not None
        new_exists = get_file_at_rev(upstream, sha, rel) is not None
        if not old_exists and new_exists and is_risky_new(mapped) and not allow_risky_new:
            blocked.append(f"risky-new:{mapped}")

    if blocked and not allow_partial:
        result["status"] = "blocked"
        result["skipped"] = blocked
        return result

    try:
        for rel in files:
            if is_upstream_skip(rel):
                continue
            mapped = map_path(rel)
            if not mapped:
                result["skipped"].append(rel)
                continue
            if is_protected(mapped, protected):
                result["skipped"].append(mapped)
                continue

            old_text = get_file_at_rev(upstream, parent, rel)
            new_text = get_file_at_rev(upstream, sha, rel)
            target = REPO_ROOT / mapped

            if new_text is None:
                result["skipped"].append(f"delete:{mapped}")
                continue

            if old_text is None:
                if target.exists():
                    result["skipped"].append(f"exists:{mapped}")
                    continue
                if is_risky_new(mapped) and not allow_risky_new:
                    result["skipped"].append(f"risky-new:{mapped}")
                    continue
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(new_text, encoding="utf-8")
                result["applied"].append(mapped)
                patched_files.append(mapped)
                continue

            local_text = target.read_text(encoding="utf-8", errors="replace") if target.exists() else None
            if local_text is not None and local_text != old_text:
                if use_3way and old_text is not None and new_text is not None:
                    merged = merge_3way(local_text, old_text, new_text, resolve_theirs)
                    if merged is None:
                        result["skipped"].append(f"3way-conflict:{mapped}")
                        continue
                    if dry_run:
                        result["applied"].append(f"3way:{mapped}")
                        continue
                    target.write_text(merged, encoding="utf-8")
                    result["applied"].append(f"3way:{mapped}")
                    patched_files.append(mapped)
                    continue
                result["skipped"].append(f"diverged:{mapped}")
                continue

            if local_text is None and is_risky_new(mapped) and not allow_risky_new:
                result["skipped"].append(f"risky-new:{mapped}")
                continue

            if dry_run:
                result["applied"].append(mapped)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_text, encoding="utf-8")
            result["applied"].append(mapped)
            patched_files.append(mapped)

        if not result["applied"]:
            result["status"] = "skipped"
            return result

        if dry_run:
            result["status"] = "dry-run"
            return result

        # Normalize text references
        normalize_text_after_merge(patched_files)

        # Verify
        if not verify(patched_files):
            snapshot_rollback(head_before)
            result["status"] = "verify-failed"
            result["error"] = "verify failed, rolled back"
            return result

        if not commit_changes(sha, msg, auto_commit):
            snapshot_rollback(head_before)
            result["status"] = "commit-failed"
            result["error"] = "commit failed, rolled back"
            return result

        result["status"] = "applied"
        return result

    except Exception as e:
        snapshot_rollback(head_before)
        result["status"] = "error"
        result["error"] = f"exception: {e}"
        print(f"[ERROR] apply_commit exception: {e}")
        print(traceback.format_exc(), file=sys.stderr)
        return result