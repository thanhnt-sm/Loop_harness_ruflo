#!/usr/bin/env python3
"""
check_updates.py — kiểm tra các repo trong REPOS_TRACKER có cập nhật mới không.

Cách dùng:
    python .devin/scripts/check_updates.py [--tracker PATH] [--output REPORT.md]

Logic:
1. Đọc REPOS_TRACKER.json.
2. Với mỗi nguồn, gọi GitHub API lấy commit mới nhất.
3. So sánh với current_commit.
4. Cập nhật status, upstream_commit, last_check.
5. Ghi lại REPOS_TRACKER.json và tạo UPDATES_REPORT.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from update_common import (
    REPO_ROOT,
    guard_main_branch,
    is_dirty_workspace,
    load_tracker,
    save_tracker,
)

DEFAULT_TRACKER = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "reports" / "UPDATES_REPORT.md"


def get_github_token() -> str:
    """Lấy GitHub token từ environment nếu có."""
    return os.environ.get("GITHUB_TOKEN", "")


def github_api_get(url: str, token: str = "") -> dict[str, Any]:
    """Gọi GitHub API và trả về JSON."""
    # B310 hardening: chỉ cho phép https tới GitHub — chặn file:/custom scheme
    # và SSRF nếu URL bị injection từ config nguồn.
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return {"error": "Invalid URL", "url": url}
    if parsed.scheme != "https" or parsed.netloc.lower() not in ("api.github.com", "github.com"):
        return {"error": f"Blocked non-GitHub URL: {parsed.netloc}", "url": url}
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Devin-Harness",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"[WARN] Rate limit / forbidden khi gọi {url}: {e}", file=sys.stderr)
            time.sleep(5)
        return {"error": f"HTTP {e.code}: {e.reason}", "url": url}
    except urllib.error.URLError as e:
        return {"error": f"URL error: {e.reason}", "url": url}
    except TimeoutError:
        return {"error": "Request timeout", "url": url}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON response: {e}", "url": url}
    except Exception as e:
        return {"error": f"Unexpected: {e}", "url": url, "traceback": traceback.format_exc()}


def parse_repo_url(url: str) -> tuple[str, str] | None:
    """Trích owner/repo từ URL GitHub."""
    # Hỗ trợ https://github.com/owner/repo.git hoặc https://github.com/owner/repo
    clean = url.rstrip("/").replace(".git", "")
    parts = clean.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None


def check_repo(source: dict[str, Any], token: str) -> dict[str, Any]:
    """Kiểm tra một nguồn repo."""
    parsed = parse_repo_url(source["url"])
    if not parsed:
        return {**source, "status": "invalid-url"}
    owner, repo = parsed
    branch = source.get("branch", "main")
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    data = github_api_get(api_url, token)
    if "error" in data:
        return {**source, "status": "api-error", "api_error": data["error"]}

    upstream_sha = data.get("sha", "")
    upstream_short = upstream_sha[:7]
    current_short = source.get("current_commit", "")
    if not current_short:
        current_short = source.get("current_commit_full", "")[:7]

    status: str
    source_type = source.get("type", "repo")
    if not current_short or current_short.lower() == "unknown":
        # canon-source concepts are manually distilled; cannot auto-compare by SHA
        if source_type == "canon-source":
            status = "manual-review"
        else:
            status = "behind"
    elif upstream_short == current_short or upstream_sha.startswith(current_short):
        status = "up-to-date"
    else:
        status = "behind"

    return {
        **source,
        "upstream_commit": upstream_short,
        "upstream_commit_full": upstream_sha,
        "status": status,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }


def write_report(path: Path, tracker: dict[str, Any]) -> None:
    """Tạo báo cáo markdown từ tracker."""
    lines = [
        "# Upstream Update Report",
        "",
        f"**Generated:** {tracker.get('last_check', '')}",
        f"**Schema version:** {tracker.get('schema_version', '')}",
        "",
        "| ID | Type | Status | Current | Upstream | Strategy | Notes |",
        "|----|------|--------|---------|----------|----------|-------|",
    ]
    for s in tracker.get("sources", []):
        lines.append(
            f"| {s['id']} | {s['type']} | {s['status']} | `{s.get('current_commit', '')}` | "
            f"`{s.get('upstream_commit', '')}` | {s.get('merge_strategy', '')} | {s.get('notes', '')} |"
        )
    lines.extend([
        "",
        "## Recommendations",
        "",
    ])
    behind = [s for s in tracker.get("sources", []) if s.get("status") == "behind"]
    if behind:
        for s in behind:
            lines.append(f"- **{s['id']}** is behind upstream. Use `{s.get('merge_strategy', 'manual')}`.")
    else:
        lines.append("- All tracked sources are up-to-date.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check upstream repos for updates.")
    parser.add_argument("--tracker", default=str(DEFAULT_TRACKER), help="Path to REPOS_TRACKER.json")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to report markdown")
    parser.add_argument("--force", action="store_true", help="Cho phép chạy trên main/master hoặc workspace dirty")
    args = parser.parse_args()

    if not guard_main_branch(args.force):
        return 1
    if is_dirty_workspace() and not args.force:
        print("[ERROR] Workspace có uncommitted changes. Commit/stash hoặc dùng --force.", file=sys.stderr)
        return 1

    tracker_path = Path(args.tracker)
    output_path = Path(args.output)

    if not tracker_path.exists():
        print(f"[ERROR] Tracker not found: {tracker_path}", file=sys.stderr)
        return 1

    tracker = load_tracker(tracker_path)
    token = get_github_token()

    updated_sources = []
    for source in tracker.get("sources", []):
        if source.get("type") == "repo" or source.get("type") == "vendored-skill" or source.get("type") == "canon-source":
            updated_sources.append(check_repo(source, token))
        else:
            updated_sources.append(source)

    tracker["sources"] = updated_sources
    tracker["last_check"] = datetime.now(timezone.utc).isoformat()

    save_tracker(tracker_path, tracker)
    write_report(output_path, tracker)

    print(f"[OK] Tracker updated: {tracker_path}")
    print(f"[OK] Report written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
