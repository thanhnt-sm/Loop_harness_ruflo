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
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACKER = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"
DEFAULT_OUTPUT = REPO_ROOT / "UPDATES_REPORT.md"


def get_github_token() -> str:
    """Lấy GitHub token từ environment nếu có."""
    return os.environ.get("GITHUB_TOKEN", "")


def github_api_get(url: str, token: str = "") -> dict[str, Any]:
    """Gọi GitHub API và trả về JSON."""
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
        return {"error": f"HTTP {e.code}: {e.reason}", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


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
    if upstream_short == current_short or upstream_sha.startswith(current_short):
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


def load_tracker(path: Path) -> dict[str, Any]:
    """Đọc tracker JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tracker(path: Path, data: dict[str, Any]) -> None:
    """Ghi tracker JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
    args = parser.parse_args()

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
