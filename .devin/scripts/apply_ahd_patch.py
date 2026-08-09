#!/usr/bin/env python3
"""
apply_ahd_patch.py — surgical cherry-pick AHD commits từ upstream.

Cách dùng:
    python .devin/scripts/apply_ahd_patch.py --upstream PATH --since DATE --until DATE [--dry-run]

Logic:
1. Liệt kê commit trong khoảng thời gian.
2. Với mỗi commit, lấy diff từng file.
3. Map path `distill/` -> `.devin/`, `scripts/` -> `.devin/scripts/`, v.v.
4. Bỏ qua file protected, Docs/, README.md, hoặc file mới ở thư mục rủi ro (adapters/, tests/).
5. Kiểm tra local file có giống bản pre-commit không (giữ nguyên local changes).
6. Copy nội dung từ commit sang local, verify, rồi commit.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[2]


# Ánh xạ cấu trúc upstream -> local
PATH_MAP: dict[str, str] = {
    "distill/canon/": ".devin/canon/",
    "distill/skills/": ".devin/skills/",
    "distill/orchestrator/workers/": ".devin/agents/workers/",
    "distill/orchestrator/": ".devin/agents/",
    "distill/agents/": ".devin/agents/",
    "scripts/": ".devin/scripts/",
    "core/assets/runtime/hooks/": ".devin/hooks/",
    "adapters/": ".devin/adapters/",
}

# File/thư mục tuyệt đối không được đụng
EXTRA_PROTECTED = [
    ".devin/hooks/",
    ".devin/config.json",
    ".devin/mcp_config.json",
    ".devin/canon/BOOT_PROTOCOL.md",
    ".devin/canon/CORE_CANON.md",
    ".devin/canon/REDLINES.md",
    ".devin/AGENTS.md",
    ".devin/AGENTS_full.md",
    "HLK/",
    ".claude/settings.json",
    ".gitignore",
    ".gitattributes",
    ".env",
]

# Các thư mục upstream chỉ là docs/promo, không deploy
SKIP_UPSTREAM_DIRS = ["Docs/", "README", "promo/", ".github/"]

# Các thư mục không được tạo file mới
RISKY_NEW_DIRS = [".devin/adapters/", ".devin/scripts/", ".devin/tests/"]


def load_tracker() -> dict[str, Any]:
    tracker = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"
    with open(tracker, "r", encoding="utf-8") as f:
        return json.load(f)


def get_protected_files() -> list[str]:
    data = load_tracker()
    for s in data.get("sources", []):
        if s.get("id") == "ahd-main-engine":
            return list(set(s.get("protected_files", []) + EXTRA_PROTECTED))
    return EXTRA_PROTECTED


def map_path(rel: str) -> str | None:
    """Ánh xạ đường dẫn upstream sang local."""
    for up, loc in PATH_MAP.items():
        if rel.startswith(up):
            return loc + rel[len(up):]
    if rel == "AGENTS.md":
        return ".devin/AGENTS.md"
    return None


def is_protected(path: str, protected: list[str]) -> bool:
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


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120, input_text: str = "") -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, input=input_text)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


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


def is_upstream_skip(rel: str) -> bool:
    for d in SKIP_UPSTREAM_DIRS:
        if rel.startswith(d) or rel == d.rstrip("/"):
            return True
    return False


def is_risky_new(target: str) -> bool:
    for d in RISKY_NEW_DIRS:
        if target.startswith(d):
            return True
    return False


def verify() -> bool:
    for script in [
        ["pwsh", "tools/verify-workspace.ps1"],
        ["node", "HLK/wrappers/hlk-verify-integrity.js"],
    ]:
        code, out, err = run_cmd(script, cwd=REPO_ROOT, timeout=180)
        if code != 0:
            print(f"[FAIL] {' '.join(script)} exit {code}")
            print(err or out)
            return False
    return True


def commit_changes(sha: str, msg: str) -> bool:
    run_cmd(["git", "add", "-A"], cwd=REPO_ROOT)
    code, out, err = run_cmd(["git", "diff", "--cached", "--stat"], cwd=REPO_ROOT)
    if not out.strip():
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


def apply_commit(upstream: Path, sha: str, msg: str, protected: list[str], dry_run: bool) -> dict[str, Any]:
    result: dict[str, Any] = {"sha": sha, "msg": msg, "status": "pending", "applied": [], "skipped": [], "error": ""}

    # Lấy danh sách file thay đổi trong commit
    files = get_changed_files(upstream, sha)
    if not files:
        result["status"] = "skipped"
        return result

    # Tính parent
    code, parent, _ = run_cmd(["git", "-C", str(upstream), "rev-parse", f"{sha}^"])
    if code != 0:
        result["status"] = "error"
        result["error"] = "cannot resolve parent"
        return result
    parent = parent.strip()

    # Nếu commit có file protected hoặc file rủi ro, bỏ qua toàn bộ để tránh partial code
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
        if not old_exists and new_exists and is_risky_new(mapped):
            blocked.append(f"risky-new:{mapped}")

    if blocked:
        result["status"] = "blocked"
        result["skipped"] = blocked
        return result

    # Duyệt từng file và áp dụng
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

        # Nếu là xóa file (new_text None), bỏ qua (không xóa local)
        if new_text is None:
            result["skipped"].append(f"delete:{mapped}")
            continue

        # Nếu là file mới
        if old_text is None:
            if target.exists():
                # Local đã có file trùng tên, bỏ qua để không ghi đè
                result["skipped"].append(f"exists:{mapped}")
                continue
            if is_risky_new(mapped):
                result["skipped"].append(f"risky-new:{mapped}")
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(new_text, encoding="utf-8")
            result["applied"].append(mapped)
            continue

        # File đã tồn tại: kiểm tra local có giống bản pre-commit không
        local_text = target.read_text(encoding="utf-8", errors="replace") if target.exists() else None
        if local_text is not None and local_text != old_text:
            result["skipped"].append(f"diverged:{mapped}")
            continue

        # Nếu file chưa có local và nằm trong thư mục rủi ro, bỏ qua
        if local_text is None and is_risky_new(mapped):
            result["skipped"].append(f"risky-new:{mapped}")
            continue

        if dry_run:
            result["applied"].append(mapped)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_text, encoding="utf-8")
        result["applied"].append(mapped)

    if not result["applied"]:
        result["status"] = "skipped"
        return result

    if dry_run:
        result["status"] = "dry-run"
        return result

    # Verify
    if not verify():
        # rollback: khôi phục từ git
        run_cmd(["git", "checkout", "--", "."], cwd=REPO_ROOT)
        result["status"] = "verify-failed"
        result["error"] = "verify failed, rolled back"
        return result

    if not commit_changes(sha, msg):
        result["status"] = "commit-failed"
        return result

    result["status"] = "applied"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default="", help="Path to cloned AHD upstream")
    parser.add_argument("--since", default="2026-07-15", help="Start date")
    parser.add_argument("--until", default="2026-08-10", help="End date")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen")
    args = parser.parse_args()

    upstream = Path(args.upstream) if args.upstream else Path(tempfile.gettempdir()) / "ahd-upstream"
    if not upstream.exists():
        print(f"[ERROR] Upstream not found: {upstream}")
        return 1

    protected = get_protected_files()
    commits = get_commits(upstream, args.since, args.until)
    if not commits:
        print("[INFO] No commits found.")
        return 0

    results: list[dict[str, Any]] = []
    for sha, msg in commits:
        print(f"\n[COMMIT] {sha} {msg}")
        res = apply_commit(upstream, sha, msg, protected, args.dry_run)
        results.append(res)
        print(f"  status: {res['status']}")
        if res["applied"]:
            print(f"  applied: {res['applied']}")
        if res["skipped"]:
            print(f"  skipped: {res['skipped']}")
        if res["error"]:
            print(f"  error: {res['error']}")

    # Ghi report
    report_path = REPO_ROOT / "AHD_PATCH_REPORT.md"
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
