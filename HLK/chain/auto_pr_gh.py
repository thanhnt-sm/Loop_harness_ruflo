#!/usr/bin/env python3
"""auto_pr_gh.py — Wrap GitHub CLI (gh) cho auto-PR flow.

Mục đích: cung cấp thin wrapper quanh `gh` CLI để auto_pr_runner có thể
tạo PR, đợi CI, merge thật. Mặc định mode vẫn "simulate"; user opt-in
"AHD_AUTO_PR_MODE=live" hoặc truyền param.

Spec: docs/plans/verify-first-residual.md section 3.1

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
__all__ = [
    "DEFAULT_BASE",
    "DEFAULT_GH_BIN",
    "DEFAULT_TIMEOUT",
    "GHResult",
    "check_auth_status",
    "check_ci",
    "check_gh_installed",
    "check_repo",
    "create_pr",
    "live_auto_merge",
    "merge_pr",
    "preflight",
    "scan_diff_for_secrets",
    "wait_for_ci",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

DEFAULT_GH_BIN = "gh"
DEFAULT_BASE = "main"
DEFAULT_TIMEOUT = 60  # giây


@dataclass
class GHResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    data: Optional[dict] = None  # nếu parse được JSON


def _run(cmd: list[str], timeout: int = DEFAULT_TIMEOUT, input_text: Optional[str] = None) -> GHResult:
    """Chạy 1 lệnh gh, capture output, không raise."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
        )
        return GHResult(
            success=(proc.returncode == 0),
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
        )
    except FileNotFoundError:
        return GHResult(False, "", f"command not found: {cmd[0]}", -1)
    except subprocess.TimeoutExpired:
        return GHResult(False, "", f"timeout after {timeout}s", -2)
    except Exception as e:
        return GHResult(False, "", str(e), -3)


def check_gh_installed(gh_bin: str = DEFAULT_GH_BIN) -> bool:
    """Check `gh` binary có trong PATH."""
    r = _run([gh_bin, "--version"], timeout=10)
    return r.success


def check_auth_status(gh_bin: str = DEFAULT_GH_BIN) -> bool:
    """Check `gh auth status` — fail nếu chưa login."""
    r = _run([gh_bin, "auth", "status"], timeout=10)
    return r.success


def check_repo(gh_bin: str = DEFAULT_GH_BIN) -> bool:
    """Check `gh repo view` — fail nếu không ở trong git repo có remote GH."""
    r = _run([gh_bin, "repo", "view"], timeout=10)
    return r.success


def preflight(gh_bin: str = DEFAULT_GH_BIN) -> tuple[bool, str]:
    """3 pre-checks: gh installed + authed + repo valid. Trả về (ok, message)."""
    if not check_gh_installed(gh_bin):
        return False, f"gh binary not found: {gh_bin}"
    if not check_auth_status(gh_bin):
        return False, f"gh not authenticated. Run: {gh_bin} auth login"
    if not check_repo(gh_bin):
        return False, f"not in a GitHub repo (no remote or no access)"
    return True, "OK"


def scan_diff_for_secrets(body: str) -> tuple[bool, str]:
    """Scan PR body cho secrets trước khi push. Trả về (ok, message)."""
    try:
        from secret_scanner import scan as scan_secrets
        findings = scan_secrets(body)
        if not findings:
            return True, "no secret detected"
        lines = [f"{len(findings)} secret(s) detected:"]
        for f in findings[:5]:  # cap 5 để không quá dài
            lines.append(f"  - {f.type} at line {f.line_no}: {f.match_preview}")
        return False, "\n".join(lines)
    except ImportError:
        # secret_scanner không có → skip (backward compat)
        return True, "secret_scanner not available, skipping scan"


def create_pr(
    title: str,
    body: str,
    base: str = DEFAULT_BASE,
    head: Optional[str] = None,
    draft: bool = False,
    gh_bin: str = DEFAULT_GH_BIN,
    timeout: int = DEFAULT_TIMEOUT,
) -> GHResult:
    """Tạo PR. Trả về GHResult, parse `data` thành {url, number, ...} nếu có.

    Args:
        head: branch chứa commit (None = current branch)
        draft: mở PR ở trạng thái draft
    """
    cmd = [gh_bin, "pr", "create", "--title", title, "--body", body, "--base", base]
    if head:
        cmd += ["--head", head]
    if draft:
        cmd.append("--draft")
    r = _run(cmd, timeout=timeout)
    # gh pr create in URL ở stdout (vd: https://github.com/...)
    url = _extract_url(r.stdout) if r.success else None
    if url:
        r.data = {"url": url, "number": _extract_pr_number(url)}
    return r


def merge_pr(
    pr_url: str,
    method: Literal["squash", "merge", "rebase"] = "squash",
    gh_bin: str = DEFAULT_GH_BIN,
    timeout: int = DEFAULT_TIMEOUT,
) -> GHResult:
    """Merge PR đã tồn tại."""
    cmd = [gh_bin, "pr", "merge, pr_url, --{method}".replace(", pr_url,", pr_url).replace(",", "")]
    # Fix syntax: simpler
    cmd = [gh_bin, "pr", "merge", pr_url, f"--{method}"]
    r = _run(cmd, timeout=timeout)
    return r


def check_ci(
    pr_url: str,
    required_checks: list[str],
    gh_bin: str = DEFAULT_GH_BIN,
    timeout: int = 30,
) -> tuple[bool, list[str]]:
    """Check CI status. Trả về (all_passed, list of failed checks)."""
    r = _run([gh_bin, "pr", "checks", pr_url, "--json", "name,state"], timeout=timeout)
    if not r.success:
        return False, [f"gh pr checks failed: {r.stderr[:200]}"]
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False, ["cannot parse gh pr checks output"]
    failed = []
    for check in data:
        name = check.get("name", "")
        state = check.get("state", "")
        if name in required_checks and state != "SUCCESS":
            failed.append(f"{name}={state}")
    return len(failed) == 0, failed


def wait_for_ci(
    pr_url: str,
    required_checks: list[str],
    max_wait_seconds: int = 300,
    poll_interval: int = 10,
    gh_bin: str = DEFAULT_GH_BIN,
) -> tuple[bool, str]:
    """Polling CI cho đến khi tất cả required check pass hoặc timeout.

    Trả về (passed, reason).
    """
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        passed, failed = check_ci(pr_url, required_checks, gh_bin)
        if passed:
            return True, "all required checks passed"
        if failed:
            return False, f"failed checks: {', '.join(failed[:5])}"
        time.sleep(poll_interval)
    return False, f"timeout after {max_wait_seconds}s"


def _extract_url(stdout: str) -> Optional[str]:
    """Extract GitHub PR URL từ gh output."""
    import re
    m = re.search(r"https://github\.com/[^\s]+", stdout)
    return m.group(0) if m else None


def _extract_pr_number(url: str) -> Optional[int]:
    import re
    m = re.search(r"/pull/(\d+)", url)
    return int(m.group(1)) if m else None


def live_auto_merge(
    title: str,
    body: str,
    branch_prefix: str,
    base: str = DEFAULT_BASE,
    required_ci: Optional[list[str]] = None,
    merge_method: Literal["squash", "merge", "rebase"] = "squash",
    gh_bin: str = DEFAULT_GH_BIN,
    ci_max_wait: int = 300,
) -> dict:
    """End-to-end live: preflight + create PR + wait CI + merge.

    Trả về dict với keys: success, pr_url, merge_sha, reason.
    """
    result = {
        "success": False,
        "pr_url": None,
        "merge_sha": None,
        "reason": "",
    }
    # 0. Secret scan (chạy đầu tiên để fail-fast trước khi gọi gh)
    secret_ok, secret_msg = scan_diff_for_secrets(body)
    if not secret_ok:
        result["reason"] = f"secret detected, refusing to push: {secret_msg}"
        return result
    # 1. Pre-flight
    ok, msg = preflight(gh_bin)
    if not ok:
        result["reason"] = f"preflight: {msg}"
        return result
    # 2. Create PR (draft = True nếu branch prefix chứa 'draft')
    draft = "draft" in branch_prefix.lower()
    pr_r = create_pr(title, body, base=base, draft=draft, gh_bin=gh_bin)
    if not pr_r.success:
        result["reason"] = f"create_pr failed: {pr_r.stderr[:200]}"
        return result
    if not pr_r.data or not pr_r.data.get("url"):
        result["reason"] = "create_pr succeeded but no URL"
        return result
    pr_url = pr_r.data["url"]
    result["pr_url"] = pr_url
    if draft:
        result["reason"] = "draft PR created (not auto-merged)"
        result["success"] = True
        return result
    # 3. Wait CI
    if required_ci:
        ci_passed, ci_msg = wait_for_ci(pr_url, required_ci, ci_max_wait, gh_bin=gh_bin)
        if not ci_passed:
            result["reason"] = f"CI: {ci_msg}"
            return result
    # 4. Merge
    merge_r = merge_pr(pr_url, method=merge_method, gh_bin=gh_bin)
    if not merge_r.success:
        result["reason"] = f"merge failed: {merge_r.stderr[:200]}"
        return result
    result["success"] = True
    result["reason"] = "merged successfully"
    return result
