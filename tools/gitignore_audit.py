#!/usr/bin/env python3
"""gitignore_audit.py — Audit .gitignore coverage cho mọi provider runtime state.

Cross-platform (Windows + macOS + Linux). Chỉ dùng stdlib Python 3.
Kiểm tra .gitignore có rule cho tất cả provider runtime dirs + OS junk không.
Phát hiện:
  - Provider runtime dir thiếu .gitignore rule (.khuym/, .aide/, .codegraph/, ...)
  - OS junk thiếu .gitignore rule (.DS_Store, Thumbs.db, *.swp, ...)
  - Tracked file nằm trong dir đã có .gitignore rule nhưng rule sai/leaking

Usage:
  python3 tools/gitignore_audit.py              # audit + báo cáo
  python3 tools/gitignore_audit.py --json       # output JSON cho CI
  python3 tools/gitignore_audit.py --strict     # exit 1 nếu bất kỳ rule thiếu

Exit code: 0 = pass, 1 = thiếu rule (với --strict), 2 = lỗi.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Cross-platform encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent

# Required .gitignore rules — mọi provider runtime + OS junk
REQUIRED_RULES: dict[str, str] = {
    # Provider runtime state dirs
    ".khuym/": "Khuym provider runtime state",
    ".aide/": "Aide provider runtime state",
    ".codegraph/": "Codegraph daemon runtime",
    ".opencode/session_state/": "opencode runtime state",
    ".omo/": "omo runtime state",
    ".serena/": "Serena runtime state",
    ".claude/": "Claude Code editor config (recreated by hooks)",
    ".cursor/": "Cursor editor config (recreated by hooks)",
    ".agents/": "Shared agent state (local-only, gitignored)",
    # OS junk
    ".DS_Store": "macOS Finder junk",
    "Thumbs.db": "Windows Explorer junk",
    "desktop.ini": "Windows desktop config junk",
    "*.swp": "Vim swap file",
    "*.swo": "Vim swap file (overflow)",
    "*~": "Editor backup (emacs/vim)",
    "*.orig": "Merge conflict original",
    "*.rej": "Merge conflict reject",
    "*.bak": "Backup file",
    "*.tmp": "Temp file",
    "*.temp": "Temp file",
    # Backups
    "backups/": "Disaster recovery backups (local-only)",
}


def _git(args: list[str], cwd: Path = ROOT) -> str:
    """Chạy git command, trả stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, cwd=str(cwd),
            timeout=30, check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def read_gitignore() -> str:
    """Đọc .gitignore content."""
    gi = ROOT / ".gitignore"
    if not gi.exists():
        return ""
    return gi.read_text(encoding="utf-8", errors="ignore")


def check_rule_present(gitignore_content: str, rule: str) -> bool:
    """Kiểm tra rule có trong .gitignore không (exact line match)."""
    for line in gitignore_content.splitlines():
        stripped = line.strip()
        if stripped == rule:
            return True
        # Cho phép rule không có trailing slash khi dir rule có slash
        if rule.endswith("/") and stripped == rule.rstrip("/"):
            return True
        # Cho phép wildcard match
        if rule.startswith("*") and stripped == rule:
            return True
    return False


def tracked_files_in_dir(dir_path: str) -> list[str]:
    """Liệt kê tracked files nằm trong dir."""
    out = _git(["ls-files", "--", dir_path])
    return [f for f in out.splitlines() if f.strip()]


def audit() -> list[dict]:
    """Audit .gitignore. Trả về list findings."""
    findings: list[dict] = []
    content = read_gitignore()

    # 1. Check required rules
    for rule, desc in REQUIRED_RULES.items():
        if not check_rule_present(content, rule):
            findings.append({
                "rule": rule,
                "description": desc,
                "issue": "missing_rule",
                "severity": "error",
                "fix": f"Thêm '{rule}' vào .gitignore",
            })

    # 2. Check tracked files trong dirs đã có rule (leaking)
    runtime_dirs = [r for r in REQUIRED_RULES if r.endswith("/")]
    for rdir in runtime_dirs:
        tracked = tracked_files_in_dir(rdir)
        if tracked:
            findings.append({
                "rule": rdir,
                "description": f"{len(tracked)} tracked file(s) trong dir đã gitignored",
                "issue": "tracked_despite_gitignore",
                "severity": "error",
                "files": tracked[:10],  # Giới hạn 10 file
                "fix": f"git rm --cached -r {rdir}",
            })

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit .gitignore coverage cho provider runtime + OS junk (cross-platform)"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON cho CI")
    parser.add_argument("--strict", action="store_true", help="Exit 1 nếu thiếu rule")
    args = parser.parse_args()

    findings = audit()
    errors = [f for f in findings if f["severity"] == "error"]

    if args.json:
        print(json.dumps({
            "audit": "gitignore",
            "required_rules": len(REQUIRED_RULES),
            "missing_rules": len([f for f in findings if f["issue"] == "missing_rule"]),
            "leaking_tracked": len([f for f in findings if f["issue"] == "tracked_despite_gitignore"]),
            "findings": findings,
        }, indent=2))
    else:
        print(f"=== .gitignore Audit — {ROOT.name} ===")
        if not findings:
            print("  [PASS] Tất cả required rules có mặt, không có tracked file leaking.")
        else:
            missing = [f for f in findings if f["issue"] == "missing_rule"]
            leaking = [f for f in findings if f["issue"] == "tracked_despite_gitignore"]
            if missing:
                print(f"\n[MISSING RULES ({len(missing)})] — .gitignore thiếu:")
                for f in missing:
                    print(f"  + {f['rule']}")
                    print(f"    {f['description']}")
                    print(f"    fix: {f['fix']}")
            if leaking:
                print(f"\n[LEAKING TRACKED ({len(leaking)})] — tracked file trong dir đã gitignored:")
                for f in leaking:
                    print(f"  ! {f['rule']} ({len(f.get('files', []))} files)")
                    for p in f.get("files", [])[:5]:
                        print(f"    - {p}")
                    print(f"    fix: {f['fix']}")

        print(f"\nKết quả: {len(errors)} error(s), {len(findings) - len(errors)} info")

    if errors and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
