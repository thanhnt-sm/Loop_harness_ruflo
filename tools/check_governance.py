#!/usr/bin/env python3
# tools/check_governance.py
# Lint "Workspace Governance" — kiểm tra file rác, sai vị trí, và khớp plan ↔ act.
# Canonical: .devin/rules/WORKSPACE_GOVERNANCE.md
# Exit code: 0 = sạch, 1 = lỗi cần sửa, 2 = warning nên xử lý.

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CODE_DIRS = (".devin/scripts", ".devin/hooks", "tests")
JUNK_NAME = re.compile(
    r"(^\.DS_Store$|^Thumbs\.db$|^untitled|^scratch|"
    r".*~$|.*\.(bak|tmp|orig|swp|swo|temp)$|.*\.log$)"
)
REF_RE = re.compile(r"`([^`]+)`")
KNOWN_EXT = {".py", ".json", ".toml", ".yml", ".yaml", ".ps1", ".sh",
             ".js", ".mjs", ".ts", ".md"}


def run(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                             check=False)
        return out.stdout
    except Exception:
        return ""


def git_status() -> list[tuple[str, str]]:
    """Trả về [(code, path)] từ `git status --porcelain`. Code '??' = untracked."""
    out = run(["git", "-C", str(ROOT), "status", "--porcelain"])
    items = []
    for line in out.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:]
        items.append((code, path))
    return items


def tracked_files() -> set[str]:
    return {p for p in run(["git", "-C", str(ROOT), "ls-files"]).splitlines()
            if p.strip()}


def is_junk(name: str) -> bool:
    return bool(JUNK_NAME.match(name))


def walk_untracked_dir(path: str) -> list[str]:
    """Liệt kê file trong thư mục untracked (git status chỉ hiện `?? dir/`)."""
    found = []
    base = ROOT / path
    for dirpath, _dirnames, filenames in os.walk(base):
        for f in filenames:
            found.append(str(Path(dirpath).relative_to(ROOT) / f))
    return found


def normalize(p: str) -> str:
    p = p.strip().lstrip("./")
    return p.rstrip("/")


def collect_plan_refs() -> dict[str, set[str]]:
    """Đọc mọi docs/plans/<slug>/IMPLEMENTATION_PLAN.md → tập path được tham chiếu."""
    plan_dir = ROOT / "docs" / "plans"
    refs: dict[str, set[str]] = {}
    if not plan_dir.is_dir():
        return refs
    for slug_dir in sorted(plan_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        plan_file = slug_dir / "IMPLEMENTATION_PLAN.md"
        if not plan_file.exists():
            continue
        refs[slug_dir.name] = set()
        for line in plan_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            for m in REF_RE.finditer(line):
                cand = normalize(m.group(1))
                if "<" in cand or ">" in cand or "*" in cand or not cand:
                    continue
                ext = Path(cand).suffix
                if ext in KNOWN_EXT or "/" in cand:
                    refs[slug_dir.name].add(cand)
    return refs


def covered_by_plan(refs: dict[str, set[str]], path: str) -> bool:
    p = normalize(path)
    for slug, paths in refs.items():
        for r in paths:
            if r == p:
                return True
            if r.endswith("/") and p.startswith(r):
                return True
            if p.endswith("/") and r.startswith(p):
                return True
    return False


def check_junk_and_layout() -> tuple[list[str], list[str]]:
    """Trả về (errors, warnings)."""
    errors, warnings = [], []
    status = git_status()
    untracked = []
    for code, path in status:
        if code.strip() in ("A", "M", "D", "R", "C"):
            continue  # tracked — đã commit hoặc đang sửa có chủ đích
        if path.endswith("/"):
            continue
        if code.strip() == "??":
            untracked.append(path)

    # Mở rộng file trong thư mục untracked.
    expanded: set[str] = set()
    for p in untracked:
        if os.path.isdir(ROOT / p):
            expanded.update(walk_untracked_dir(p))
        else:
            expanded.add(p)
    untracked = sorted(expanded)

    for p in untracked:
        name = os.path.basename(p)
        if is_junk(name):
            errors.append(f"file rác: {p}")

    for p in untracked:
        if "/" not in p:
            errors.append(f"file mới ở root (vi phạm layout): {p}")

    for p in untracked:
        if p.endswith(".py") and not p.startswith(CODE_DIRS) \
                and not p.startswith("tools/"):
            errors.append(f"python ngoài vùng quy định: {p}")

    return errors, warnings

def check_plan_act() -> tuple[list[str], list[str]]:
    """Kiểm tra khớp plan ↔ act."""
    errors, warnings = [], []
    refs = collect_plan_refs()
    plan_dir = ROOT / "docs" / "plans"

    # 1. Plan không có execution report.
    if plan_dir.is_dir():
        for slug_dir in sorted(plan_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            plan_file = slug_dir / "IMPLEMENTATION_PLAN.md"
            if not plan_file.exists():
                continue
            has_report = (slug_dir / "EXECUTION_REPORT.md").exists() or \
                         (slug_dir / "FINAL_REPORT.md").exists()
            if not has_report:
                warnings.append(
                    f"plan thiếu execution report: docs/plans/{slug_dir.name}/")

    # 2. File code thay đổi nhưng không nằm trong plan nào (act không plan).
    status = git_status()
    changed = []
    for code, path in status:
        if path.endswith("/"):
            continue
        if code.strip() in ("D", "R"):
            continue
        if path.startswith(CODE_DIRS):
            changed.append(path)
    for p in sorted(set(changed)):
        if not covered_by_plan(refs, p):
            warnings.append(f"code thay đổi không nằm trong plan nào: {p}")

    return errors, warnings


def main() -> int:
    plan_act_only = "--plan-act" in sys.argv
    errors: list[str] = []
    warnings: list[str] = []

    if not plan_act_only:
        e, w = check_junk_and_layout()
        errors += e
        warnings += w
    e, w = check_plan_act()
    errors += e
    warnings += w

    print(f"=== Governance Check — {ROOT.name} ===")
    if errors:
        print(f"\n[ERRORS ({len(errors)})] — phải sửa trước khi kết thúc task:")
        for m in sorted(set(errors)):
            print(f"  ✗ {m}")
    if warnings:
        print(f"\n[WARNINGS ({len(warnings)})] — nên xử lý:")
        for m in sorted(set(warnings)):
            print(f"  ⚠ {m}")
    if not errors and not warnings:
        print("  ✓ Sạch — không lỗi, không warning.")
    print(f"\nKết quả: errors={len(errors)}, warnings={len(warnings)}")
    if errors:
        return 1
    if warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
