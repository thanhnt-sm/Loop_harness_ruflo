#!/usr/bin/env python3
"""junk_file_scanner.py — Scan file rác trong git repo (tracked + untracked + staged).

Cross-platform (Windows + macOS + Linux). Chỉ dùng stdlib Python 3.
Phát hiện:
  - OS junk: .DS_Store, Thumbs.db, *.swp, *.swo, *~, *.orig, *.rej, *.bak, *.tmp, *.temp
  - Provider runtime state đã commit: .khuym/, .aide/, .codegraph/, .opencode/session_state/
  - Filler content: file chỉ chứa 1 kiểu ký tự lặp lại (vd 'xxxx...')
  - Scratch/untitled files
  - Binary junk đã commit (.DS_Store, Thumbs.db)

Usage:
  python3 tools/junk_file_scanner.py                  # scan tất cả (tracked + untracked)
  python3 tools/junk_file_scanner.py --staged          # chỉ scan staged area (cho pre-commit)
  python3 tools/junk_file_scanner.py --tracked         # chỉ scan tracked files
  python3 tools/junk_file_scanner.py --json            # output JSON cho CI
  python3 tools/junk_file_scanner.py --fix             # git rm --cached junk đã tracked

Exit code: 0 = sạch, 1 = phát hiện junk, 2 = lỗi.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Cross-platform encoding: đảm bảo stdout dùng utf-8 trên cả Windows + macOS
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent

# --- Junk patterns (sync với path_zones.py JUNK_FILENAMES/JUNK_EXTENSIONS) ---
JUNK_EXTENSIONS = (
    ".bak", ".tmp", ".orig", ".swp", ".swo", ".temp", ".rej",
)

JUNK_FILENAMES = (
    ".DS_Store",
    "Thumbs.db",
    ".fuse_hidden",
    "desktop.ini",
    "ehthumbs.db",
)

JUNK_PREFIXES = (
    "untitled",
    "scratch",
    "copy_of",
    "copy -",
)

# Provider runtime state dirs — KHÔNG BAO GIỜ commit
PROVIDER_RUNTIME_DIRS = (
    ".khuym/",
    ".aide/",
    ".codegraph/",
    ".opencode/session_state/",
    ".omo/",
    ".serena/",
    ".claude/",
    ".cursor/",
)

# Filler detection: file chỉ chứa 1 ký tự lặp lại (vd 'xxxx...' hàng nghìn lần)
FILLER_MIN_LEN = 100
FILLER_MIN_RATIO = 0.95  # 95% ký tự giống nhau


def _git(args: list[str], cwd: Path = ROOT) -> str:
    """Chạy git command, trả stdout. Cross-platform."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=30,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def tracked_files() -> list[str]:
    """Liệt kê tất cả file đã được git track."""
    out = _git(["ls-files"])
    return [f for f in out.splitlines() if f.strip()]


def staged_files() -> list[tuple[str, str]]:
    """Liệt kê file trong staged area + status (A/M/D/R).

    Returns:
        List of (status, path) tuples.
        status: 'A' (added), 'M' (modified), 'D' (deleted), 'R' (renamed).
    """
    out = _git(["diff", "--cached", "--name-status"])
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0][0]  # Lấy ký tự đầu (A/M/D/R/C)
            path = parts[-1].strip()  # Path cuối (rename có 2 paths)
            result.append((status, path))
    return result


def untracked_files() -> list[str]:
    """Liệt kê untracked files (git status --porcelain, code '??')."""
    out = _git(["status", "--porcelain"])
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        code = line[:2].strip()
        path = line[3:].strip()
        if code == "??":
            # Mở rộng thư mục untracked
            full = ROOT / path
            if full.is_dir():
                for dirpath, _dirs, files in os.walk(full):
                    for f in files:
                        rel = Path(dirpath).relative_to(ROOT) / f
                        result.append(str(rel).replace("\\", "/"))
            else:
                result.append(path)
    return result


def is_junk_name(filepath: str) -> bool:
    """Kiểm tra tên file có phải junk không (dựa vào tên + extension). Case-insensitive."""
    name = Path(filepath).name.lower()
    if any(name.endswith(ext) for ext in JUNK_EXTENSIONS):
        return True
    # Lower cả pattern để match case-insensitive
    junk_names_lower = tuple(j.lower() for j in JUNK_FILENAMES)
    if name in junk_names_lower:
        return True
    if any(name.startswith(prefix) for prefix in JUNK_PREFIXES):
        return True
    return False


def is_provider_runtime(filepath: str) -> bool:
    """Kiểm tra file có nằm trong provider runtime dir không."""
    norm = filepath.replace("\\", "/").lower()
    for pdir in PROVIDER_RUNTIME_DIRS:
        if norm.startswith(pdir.lower()):
            return True
    return False


def is_filler_content(filepath: str) -> bool:
    """Kiểm tra file có phải filler content không (chỉ 1 ký tự lặp lại).

    Cross-platform: đọc binary, decode utf-8 với errors='ignore'.
    """
    full = ROOT / filepath
    if not full.exists() or not full.is_file():
        return False
    try:
        size = full.stat().st_size
        if size < FILLER_MIN_LEN:
            return False
        # Đọc tối đa 10KB để check
        with open(full, "rb") as f:
            data = f.read(10240)
        text = data.decode("utf-8", errors="ignore")
        if not text.strip():
            return True  # File rỗng hoặc chỉ whitespace
        # Đếm tần suất ký tự
        from collections import Counter
        counts = Counter(text)
        most_common_char, most_common_count = counts.most_common(1)[0]
        ratio = most_common_count / len(text)
        if ratio >= FILLER_MIN_RATIO and most_common_char in ("x", "X", " ", "\n", "\t", "0", "1"):
            return True
    except Exception:
        return False
    return False


def is_binary_junk(filepath: str) -> bool:
    """Kiểm tra file binary có phải junk không (.DS_Store, Thumbs.db). Case-insensitive."""
    name = Path(filepath).name.lower()
    binary_junk_names = (".ds_store", "thumbs.db", "desktop.ini")
    if name in binary_junk_names:
        return True
    return False


def scan(mode: str = "all") -> list[dict]:
    """Scan junk files theo mode.

    Args:
        mode: "all" | "tracked" | "untracked" | "staged"

    Returns:
        List of {"path": str, "reason": str, "type": str} dicts.
    """
    findings: list[dict] = []

    if mode in ("all", "tracked"):
        for f in tracked_files():
            if is_junk_name(f):
                findings.append({"path": f, "reason": "junk filename pattern", "type": "junk_name"})
            elif is_binary_junk(f):
                findings.append({"path": f, "reason": "binary junk (OS artifact)", "type": "binary_junk"})
            elif is_provider_runtime(f):
                findings.append({"path": f, "reason": "provider runtime state (should be gitignored)", "type": "provider_runtime"})
            elif is_filler_content(f):
                findings.append({"path": f, "reason": "filler content (repeated single char)", "type": "filler"})

    if mode in ("all", "untracked"):
        for f in untracked_files():
            if is_junk_name(f):
                findings.append({"path": f, "reason": "junk filename pattern (untracked)", "type": "junk_name"})
            elif is_provider_runtime(f):
                findings.append({"path": f, "reason": "provider runtime state (untracked)", "type": "provider_runtime"})

    if mode == "staged":
        for status, f in staged_files():
            # Skip deletion — file đang được XÓA là hành động dọn rác, không phải thêm rác
            if status == "D":
                continue
            if is_junk_name(f):
                findings.append({"path": f, "reason": "junk filename in staged area", "type": "junk_name"})
            elif is_binary_junk(f):
                findings.append({"path": f, "reason": "binary junk in staged area", "type": "binary_junk"})
            elif is_provider_runtime(f):
                findings.append({"path": f, "reason": "provider runtime state in staged area", "type": "provider_runtime"})
            elif is_filler_content(f):
                findings.append({"path": f, "reason": "filler content in staged area", "type": "filler"})

    # Dedup
    seen = set()
    unique = []
    for item in findings:
        key = item["path"]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def fix_tracked_junk(findings: list[dict]) -> list[str]:
    """git rm --cached cho junk files đã tracked. Trả về list paths đã untrack."""
    fixed = []
    for item in findings:
        if item["type"] in ("junk_name", "binary_junk", "provider_runtime", "filler"):
            path = item["path"]
            result = _git(["rm", "--cached", "--", path])
            if result:
                fixed.append(path)
    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan junk files trong git repo (cross-platform Windows + macOS)"
    )
    parser.add_argument("--staged", action="store_true", help="Chỉ scan staged area (cho pre-commit)")
    parser.add_argument("--tracked", action="store_true", help="Chỉ scan tracked files")
    parser.add_argument("--untracked", action="store_true", help="Chỉ scan untracked files")
    parser.add_argument("--json", action="store_true", help="Output JSON cho CI integration")
    parser.add_argument("--fix", action="store_true", help="git rm --cached junk đã tracked")
    args = parser.parse_args()

    if args.staged:
        mode = "staged"
    elif args.tracked:
        mode = "tracked"
    elif args.untracked:
        mode = "untracked"
    else:
        mode = "all"

    findings = scan(mode)

    if args.json:
        print(json.dumps({"junk_count": len(findings), "findings": findings}, indent=2))
    else:
        if findings:
            print(f"=== Junk File Scanner — {ROOT.name} ===")
            print(f"\n[FOUND {len(findings)} junk file(s)]")
            for item in sorted(findings, key=lambda x: x["path"]):
                print(f"  ✗ {item['path']}")
                print(f"    reason: {item['reason']} ({item['type']})")
            print()
            if args.fix:
                fixed = fix_tracked_junk(findings)
                if fixed:
                    print(f"[FIXED] git rm --cached {len(fixed)} file(s):")
                    for p in fixed:
                        print(f"  ✓ untracked: {p}")
                else:
                    print("[FIX] Không có tracked junk để untrack.")
        else:
            if not args.json:
                print(f"=== Junk File Scanner — {ROOT.name} ===")
                print("  ✓ Sạch — không phát hiện junk file.")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
