#!/usr/bin/env python3
"""Smoke test import cho toàn bộ .py trong .devin/scripts/ và .devin/hooks/.

Mục đích: bắt lỗi ModuleNotFoundError sớm trước khi merge.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _is_valid_module_name(name: str) -> bool:
    """Chỉ chấp nhận tên module Python hợp lệ (alphanumeric + underscore, không bắt đầu bằng số)."""
    return bool(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name))


def _modules_in_dir(root: Path) -> list[tuple[Path, str]]:
    """Lấy danh sách (file, module_name) cho mỗi .py trong thư mục."""
    results = []
    for f in root.glob("*.py"):
        if f.name.startswith("test_"):
            continue
        mod = f.stem
        if not _is_valid_module_name(mod):
            print(f"[SKIP] invalid module name: {f.name}")
            continue
        results.append((f, mod))
    return results


def smoke_test(directories: list[str] | None = None) -> dict:
    """Chạy import smoke test."""
    if directories is None:
        directories = [".devin/scripts", ".devin/hooks"]

    passed = []
    failed = []

    for sub in directories:
        root = REPO_ROOT / sub
        if not root.exists():
            continue
        for f, mod in _modules_in_dir(root):
            env = dict(os.environ, PYTHONPATH=str(root))
            r = subprocess.run(
                [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(root)!r}); import {mod}"],
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("SMOKE_TEST_TIMEOUT", "30")),
            )
            if r.returncode == 0:
                passed.append(str(f.relative_to(REPO_ROOT)))
            else:
                err = r.stderr.strip().splitlines()[-1] if r.stderr else "unknown error"
                failed.append({"file": str(f.relative_to(REPO_ROOT)), "error": err})

    return {"passed": len(passed), "failed": failed}


def main() -> int:
    """CLI entry."""
    result = smoke_test()
    print(f"SMOKE TEST: {result['passed']} passed, {len(result['failed'])} failed")
    for item in result["failed"]:
        print(f"FAIL {item['file']}: {item['error']}")
    return 0 if not result["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
