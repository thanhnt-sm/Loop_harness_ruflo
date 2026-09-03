#!/usr/bin/env python3
"""Golden Set Miner — Mine golden tasks from merged PRs (60-90 days old).

Implements V1: Private versioned golden set from merged PRs + production failures.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


# Paths
GOLDEN_DIR = Path("tests/golden")
TASKS_DIR = GOLDEN_DIR / "tasks"
MANIFEST_FILE = GOLDEN_DIR / "manifest.json"


@dataclass
class GoldenTask:
    """A versioned golden task mined from merged PR."""
    task_id: str
    repo: str
    issue: str
    pr: str
    base_sha: str
    head_sha: str
    description: str
    golden_diff: str
    content_hash: str  # SHA256 of golden_diff for contamination detection
    created_at: str
    difficulty: str    # easy/medium/hard
    tags: list[str]
    source: str = "merged_pr"  # merged_pr, production_failure, manual


def _run_git(cmd: list[str], cwd: Path) -> str:
    """Run git command and return stdout."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, check=False
    )
    return result.stdout.strip()


def _get_merged_prs(
    repo_path: Path,
    min_days: int = 60,
    max_days: int = 90,
) -> list[dict]:
    """Get merged PRs from git log in date range."""
    since_date = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d")
    until_date = (datetime.now() - timedelta(days=min_days)).strftime("%Y-%m-%d")

    # Get merge commits with PR info
    log_format = "%H|%s|%ad"
    cmd = [
        "git", "log",
        f"--since={since_date}",
        f"--until={until_date}",
        "--merges",
        f"--pretty=format:{log_format}",
        "--date=short",
    ]
    output = _run_git(cmd, repo_path)

    prs = []
    for line in output.splitlines():
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        sha, subject, date = parts
        # Extract PR number from merge commit message
        # Typical: "Merge pull request #123 from user/branch"
        pr_num = None
        if "pull request" in subject.lower():
            import re
            match = re.search(r'#(\d+)', subject)
            if match:
                pr_num = match.group(1)

        prs.append({
            "sha": sha,
            "subject": subject,
            "date": date,
            "pr_number": pr_num,
        })

    return prs


def _get_pr_diff(repo_path: Path, pr_sha: str) -> str:
    """Get the diff for a merged PR (from first parent)."""
    # Get the merge commit's parents
    cmd = ["git", "rev-parse", f"{pr_sha}^1", f"{pr_sha}^2"]
    output = _run_git(cmd, repo_path)
    parents = output.split()
    if len(parents) != 2:
        return ""

    base_sha, head_sha = parents[0], parents[1]
    # Get diff between parents
    cmd = ["git", "diff", base_sha, head_sha]
    return _run_git(cmd, repo_path)


def _estimate_difficulty(diff: str) -> str:
    """Estimate task difficulty from diff size."""
    files_changed = diff.count("diff --git")
    lines_added = diff.count("\n+")
    lines_removed = diff.count("\n-")
    total_changes = lines_added + lines_removed

    if files_changed <= 1 and total_changes <= 50:
        return "easy"
    elif files_changed <= 3 and total_changes <= 200:
        return "medium"
    else:
        return "hard"


def _extract_tags(diff: str, subject: str) -> list[str]:
    """Extract tags from diff and commit message."""
    tags = []
    # From file extensions
    if ".py" in diff:
        tags.append("python")
    if ".ts" in diff or ".js" in diff:
        tags.append("typescript")
    if ".json" in diff:
        tags.append("config")
    if ".md" in diff:
        tags.append("docs")
    if "test" in diff.lower():
        tags.append("test")
    # From subject
    if "fix" in subject.lower():
        tags.append("bugfix")
    if "feat" in subject.lower() or "feature" in subject.lower():
        tags.append("feature")
    if "refactor" in subject.lower():
        tags.append("refactor")
    return tags


def mine_merged_prs(
    repo_path: Path = Path("."),
    min_days: int = 60,
    max_days: int = 90,
    max_files: int = 5,
    max_lines: int = 1000,
) -> list[GoldenTask]:
    """Mine golden tasks from merged PRs in date range."""
    prs = _get_merged_prs(repo_path, min_days, max_days)
    tasks = []

    for pr in prs:
        if not pr["pr_number"]:
            continue

        diff = _get_pr_diff(repo_path, pr["sha"])
        if not diff:
            continue

        # Filter by complexity
        files_changed = diff.count("diff --git")
        lines_changed = diff.count("\n+") + diff.count("\n-")
        if files_changed > max_files or lines_changed > max_lines:
            continue

        # Create task
        task_id = f"golden-{pr['pr_number']}-{pr['sha'][:8]}"
        content_hash = hashlib.sha256(diff.encode()).hexdigest()[:16]
        difficulty = _estimate_difficulty(diff)
        tags = _extract_tags(diff, pr["subject"])

        task = GoldenTask(
            task_id=task_id,
            repo=str(repo_path.name),
            issue=f"#{pr['pr_number']}",
            pr=f"#{pr['pr_number']}",
            base_sha=pr["sha"] + "^1",
            head_sha=pr["sha"] + "^2",
            description=pr["subject"],
            golden_diff=diff,
            content_hash=content_hash,
            created_at=pr["date"],
            difficulty=difficulty,
            tags=tags,
        )
        tasks.append(task)

    return tasks


def save_golden_task(task: GoldenTask) -> None:
    """Save task to tests/golden/tasks/{task_id}.json"""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = TASKS_DIR / f"{task.task_id}.json"
    task_file.write_text(json.dumps(asdict(task), ensure_ascii=False, indent=2))
    _update_manifest(task)


def _update_manifest(task: GoldenTask) -> None:
    """Update manifest with new task."""
    manifest = load_golden_manifest()
    manifest["tasks"][task.task_id] = {
        "task_id": task.task_id,
        "repo": task.repo,
        "issue": task.issue,
        "pr": task.pr,
        "difficulty": task.difficulty,
        "tags": task.tags,
        "content_hash": task.content_hash,
        "created_at": task.created_at,
        "source": task.source,
    }
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["total_tasks"] = len(manifest["tasks"])

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def load_golden_manifest() -> dict:
    """Load manifest with all task IDs and metadata."""
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "tasks": {}, "updated_at": "", "total_tasks": 0}


def load_golden_task(task_id: str) -> Optional[GoldenTask]:
    """Load a single golden task."""
    task_file = TASKS_DIR / f"{task_id}.json"
    if not task_file.exists():
        return None
    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
        return GoldenTask(**data)
    except Exception:
        return None


def list_golden_tasks(
    difficulty: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> list[GoldenTask]:
    """List tasks with optional filters."""
    manifest = load_golden_manifest()
    tasks = []
    for task_id in manifest["tasks"]:
        task = load_golden_task(task_id)
        if task:
            if difficulty and task.difficulty != difficulty:
                continue
            if tags and not any(t in task.tags for t in tags):
                continue
            tasks.append(task)
    return tasks


def get_golden_stats() -> dict:
    """Get statistics about golden set."""
    manifest = load_golden_manifest()
    tasks = list_golden_tasks()
    difficulties = {"easy": 0, "medium": 0, "hard": 0}
    tags_set = set()
    for task in tasks:
        difficulties[task.difficulty] += 1
        tags_set.update(task.tags)
    return {
        "total_tasks": len(tasks),
        "difficulties": difficulties,
        "unique_tags": sorted(tags_set),
        "manifest_updated": manifest.get("updated_at", ""),
    }


def _cli() -> int:
    """CLI: mine golden tasks and save them."""
    import argparse
    ap = argparse.ArgumentParser(description="Mine golden tasks from merged PRs")
    ap.add_argument("--repo", default=".", help="Repository path")
    ap.add_argument("--min-days", type=int, default=60, help="Minimum days ago")
    ap.add_argument("--max-days", type=int, default=90, help="Maximum days ago")
    ap.add_argument("--max-files", type=int, default=5, help="Max files changed")
    ap.add_argument("--max-lines", type=int, default=1000, help="Max lines changed")
    ap.add_argument("--save", action="store_true", help="Save tasks to disk")
    args = ap.parse_args()

    tasks = mine_merged_prs(
        repo_path=Path(args.repo),
        min_days=args.min_days,
        max_days=args.max_days,
        max_files=args.max_files,
        max_lines=args.max_lines,
    )

    print(f"Found {len(tasks)} golden tasks")
    for task in tasks:
        print(f"  {task.task_id} [{task.difficulty}] {task.description[:60]}")
        if args.save:
            save_golden_task(task)

    if args.save:
        print(f"Saved to {TASKS_DIR}")
        stats = get_golden_stats()
        print(f"Total in golden set: {stats['total_tasks']}")

    return 0


if __name__ == "__main__":
    from datetime import timezone
    import argparse
    raise SystemExit(_cli())