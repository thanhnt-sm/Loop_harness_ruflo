#!/usr/bin/env python3
"""
merge_updates.py — merge an toàn một nguồn vendored-skill từ REPOS_TRACKER.

Cách dùng:
    python .devin/scripts/merge_updates.py --source-id <id> [--dry-run] [--force-overwrite]

Logic:
1. Guard branch: không chạy trên main/master.
2. Đọc REPOS_TRACKER.json.
3. Tìm source theo id.
4. Backup thư mục đích.
5. Clone / fetch upstream tạm.
6. Phân loại từng file: core, customization, skip.
7. Apply thay đổi:
   - Core file → diff + overwrite nếu upstream mới hơn.
   - Customization (examples, ATTRIBUTION, ...) → giữ local, báo user, chỉ overwrite nếu --force-overwrite.
   - File mới → copy.
   - Skip `promo/`, `.github/`, `.gitignore`, large assets.
8. Chạy verify pipeline.
9. Nếu FAIL → restore từ backup.
"""
from __future__ import annotations

import argparse
import difflib
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

# File/thư mục core — được phép overwrite khi upstream mới hơn
CORE_PATTERNS = [
    "SKILL.md",
    "README*.md",
    "README_*.md",
    "COMMUNITY.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "references/**",
    "scripts/**",
    "SKILL_*.md",
]

# File/thư mục không bao giờ được tự động overwrite (local customization)
CUSTOMIZATION_PATTERNS = [
    "ATTRIBUTION.md",
    "examples/**",
    "local/**",
    "*.local.*",
]

# File/thư mục bỏ qua hoàn toàn
SKIP_PATTERNS = [
    ".github/**",
    ".gitignore",
    ".gitattributes",
    "promo/**",
    "promotion/**",
    "marketing/**",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.mp4",
    "*.mov",
    "*.webp",
    "*.zip",
    "*.tar",
    "*.tar.gz",
]


PROTECTED_PATTERNS = [
    ".env",
    "*.pem",
    "*.key",
    "secrets/**",
    "credentials/**",
    "HLK/**",
    ".devin/hooks/**",
    ".devin/config.json",
    ".devin/mcp_config.json",
    ".devin/canon/BOOT_PROTOCOL.md",
    ".devin/canon/CORE_CANON.md",
    ".devin/canon/REDLINES.md",
    ".devin/AGENTS.md",
    ".devin/AGENTS_full.md",
    ".claude/settings.json",
]


def load_tracker(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tracker(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120, input_text: str = "") -> tuple[int, str, str]:
    """Chạy lệnh và trả (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, input=input_text)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def get_branch() -> str:
    code, out, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
    return out.strip()


def guard_branch(force: bool) -> bool:
    """Không chạy trên main/master trừ khi --force."""
    branch = get_branch()
    if branch in ("main", "master") and not force:
        print(f"[ERROR] Cannot run on '{branch}'. Use feature branch or --force.")
        return False
    return True


def _glob_match(name: str, pat: str) -> bool:
    """fnmatch đơn giản hỗ trợ * và ?."""
    import re as _re
    p = pat.replace(".", r"\.")
    p = p.replace("*", ".*")
    p = p.replace("?", ".")
    return bool(_re.fullmatch(p, name))


def is_protected(path: str, protected: list[str]) -> bool:
    """Kiểm tra path có nằm trong danh sách protected không, hỗ trợ glob."""
    norm = Path(path).as_posix().lower()
    for p in protected:
        pl = p.lower()
        if any(c in pl for c in "*?"):
            if _glob_match(norm, pl):
                return True
            continue
        if pl.endswith("/**"):
            prefix = pl[:-3]
            if norm == prefix or norm.startswith(prefix + "/"):
                return True
        elif norm == pl or norm.startswith(pl + "/") or norm.endswith("/" + pl) or "/" + pl in norm:
            return True
    return False


def classify_file(rel: str) -> str:
    """Phân loại file vendored-skill: core, customization, skip."""
    rel_posix = Path(rel).as_posix()
    for pat in SKIP_PATTERNS:
        if _glob_match(rel_posix, pat):
            return "skip"
    for pat in CORE_PATTERNS:
        if _glob_match(rel_posix, pat):
            return "core"
    for pat in CUSTOMIZATION_PATTERNS:
        if _glob_match(rel_posix, pat):
            return "customization"
    return "core"


def file_hash(path: Path) -> str:
    """Tính SHA-256 nhanh để so sánh nội dung."""
    import hashlib
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def unified_diff_text(local_text: str, upstream_text: str, label_local: str = "local", label_upstream: str = "upstream") -> str:
    """Trả về unified diff của hai chuỗi."""
    return "\n".join(difflib.unified_diff(
        local_text.splitlines(),
        upstream_text.splitlines(),
        fromfile=label_local,
        tofile=label_upstream,
        lineterm="",
    ))


def backup_directory(src: Path, label: str) -> Path:
    """Tạo backup timestamped."""
    DEFAULT_BACKUP.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = DEFAULT_BACKUP / f"{label}-{timestamp}"
    shutil.copytree(src, dest, dirs_exist_ok=True)
    print(f"[OK] Backup: {dest}")
    return dest


def restore_directory(backup: Path, target: Path) -> bool:
    """Phục hồi target từ backup."""
    if not backup.exists():
        print(f"[ERROR] Backup not found: {backup}")
        return False
    if not target.resolve().is_relative_to(REPO_ROOT):
        print(f"[ERROR] Target outside repo: {target}")
        return False
    try:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(backup, target, dirs_exist_ok=True)
        return True
    except Exception as e:
        print(f"[ERROR] Restore failed: {e}")
        return False


def clone_repo(url: str, dest: Path, branch: str = "main", depth: int = 50) -> bool:
    """Clone repo upstream tạm."""
    if dest.exists():
        shutil.rmtree(dest)
    cmd = ["git", "clone", f"--depth={depth}", "--branch", branch, url, str(dest)]
    code, out, err = run_cmd(cmd, timeout=180)
    if code != 0:
        print(f"[FAIL] git clone: {err or out}")
        return False
    return True


def py_compile_files(files: list[Path]) -> bool:
    """Chạy py_compile trên danh sách file .py."""
    ok = True
    for f in files:
        code, _, err = run_cmd([sys.executable, "-m", "py_compile", str(f)], cwd=REPO_ROOT)
        if code != 0:
            print(f"[FAIL] py_compile {f}: {err}")
            ok = False
    return ok


def verify_after_update(touched: list[Path]) -> bool:
    """Chạy verify pipeline sau update."""
    ok = True

    # verify-workspace.ps1
    code, out, err = run_cmd(["pwsh", "tools/verify-workspace.ps1"], cwd=REPO_ROOT, timeout=180)
    if code != 0:
        print(f"[FAIL] verify-workspace.ps1 exit {code}")
        print(err or out)
        ok = False

    # HLK
    code, out, err = run_cmd(["node", "HLK/wrappers/hlk-verify-integrity.js"], cwd=REPO_ROOT, timeout=180)
    if code != 0:
        print(f"[FAIL] hlk-verify-integrity.js exit {code}")
        print(err or out)
        ok = False

    # py_compile
    py_files = [f for f in touched if f.suffix == ".py"]
    if py_files and not py_compile_files(py_files):
        ok = False

    # import smoke test nếu chạm scripts/hooks
    if any(str(f).startswith((".devin/scripts/", ".devin/hooks/")) for f in touched):
        code, out, err = run_cmd([sys.executable, "tools/import_smoke_test.py"], cwd=REPO_ROOT, timeout=120)
        if code != 0:
            print(f"[FAIL] import_smoke_test.py exit {code}")
            print(err or out)
            ok = False

    return ok


def apply_vendored_copy(
    upstream: Path,
    target: Path,
    protected: list[str],
    dry_run: bool,
    force_overwrite: bool,
) -> dict[str, list[str]]:
    """Copy upstream vào target, phân loại core/customization, trả về actions."""
    actions: dict[str, list[str]] = {"copied": [], "overwritten": [], "skipped": [], "protected": []}

    for src in upstream.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(upstream).as_posix()

        # Bỏ qua .git
        if ".git" in rel.split("/"):
            continue

        # Skip patterns
        category = classify_file(rel)
        if category == "skip":
            actions["skipped"].append(f"skip-pattern:{rel}")
            continue

        dst = target / rel

        # Protected
        if is_protected(str(dst.relative_to(REPO_ROOT)), protected) or is_protected(rel, protected):
            actions["protected"].append(rel)
            continue

        upstream_hash = file_hash(src)
        local_hash = file_hash(dst)

        if not dst.exists():
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            actions["copied"].append(rel)
            continue

        if local_hash == upstream_hash:
            actions["skipped"].append(f"identical:{rel}")
            continue

        if category == "core" or force_overwrite:
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            actions["overwritten"].append(rel)
            continue

        # customization: giữ local, hiển thị diff nhắc user
        diff = unified_diff_text(dst.read_text(encoding="utf-8", errors="replace"), src.read_text(encoding="utf-8", errors="replace"), str(dst), str(src))
        print(f"[PRESERVE] local customization: {rel}")
        if diff:
            print(diff[:1000])  # giới hạn diff hiển thị
            if len(diff) > 1000:
                print("... (diff truncated)")
        actions["skipped"].append(f"preserve:{rel}")

    return actions


def source_id_to_label(sid: str) -> str:
    return sid.replace("/", "-").replace("\\", "-")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely merge an upstream source.")
    parser.add_argument("--source-id", required=True, help="Source ID from REPOS_TRACKER.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without applying")
    parser.add_argument("--tracker", default=str(TRACKER), help="Path to tracker")
    parser.add_argument("--force-overwrite", action="store_true", help="Overwrite local customization without prompting")
    parser.add_argument("--force", action="store_true", help="Allow running on main/master")
    args = parser.parse_args()

    if not guard_branch(args.force):
        return 1

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
    protected = list(set(source.get("protected_files", []) + PROTECTED_PATTERNS))
    url = source.get("url", "")
    vendored_path = source.get("vendored_path", "")
    branch = source.get("branch", "main")

    if not url:
        print(f"[ERROR] No URL for {args.source_id}", file=sys.stderr)
        return 1

    if strategy not in ("direct-copy-vendored", "direct-copy"):
        print(f"[INFO] {args.source_id} uses '{strategy}' strategy; not supported by merge_updates.py. Use apply_ahd_patch.py or manual flow.")
        return 0

    if not vendored_path:
        print(f"[ERROR] No vendored_path for {args.source_id}", file=sys.stderr)
        return 1

    target = REPO_ROOT / vendored_path
    if not target.exists():
        print(f"[ERROR] Target path does not exist: {target}", file=sys.stderr)
        return 1

    print(f"[START] Merging {args.source_id} into {target}")
    if args.dry_run:
        print("[DRY-RUN] No files will be modified.")

    backup = backup_directory(target, f"{source_id_to_label(args.source_id)}-pre-merge")

    tmp = Path(tempfile.gettempdir()) / f"{args.source_id}-merge-upstream"
    if not clone_repo(url, tmp, branch):
        return 1

    actions = apply_vendored_copy(tmp, target, protected, args.dry_run, args.force_overwrite)

    print(f"\n[SUMMARY]")
    print(f"  copied:      {len(actions['copied'])}")
    print(f"  overwritten: {len(actions['overwritten'])}")
    print(f"  skipped:     {len(actions['skipped'])}")
    print(f"  protected:   {len(actions['protected'])}")

    if args.dry_run:
        print("[DRY-RUN] Done. No files were modified.")
        return 0

    if not actions["copied"] and not actions["overwritten"] and not actions["protected"]:
        print("[INFO] No files changed.")
        return 0

    touched = [target / a for a in actions["copied"] + actions["overwritten"]]
    if verify_after_update(touched):
        print(f"[OK] Verify passed. {args.source_id} merged successfully.")
        source["current_commit"] = source.get("upstream_commit", "")
        source["current_commit_full"] = source.get("upstream_commit_full", "")
        source["status"] = "up-to-date"
        save_tracker(tracker_path, tracker)
        return 0
    else:
        print(f"[ROLLBACK] Verify failed; restoring from backup {backup}")
        if restore_directory(backup, target):
            print("[OK] Restored. Please fix issues and retry.")
        else:
            print("[CRITICAL] Rollback failed. Manual intervention required.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
