#!/usr/bin/env python3
"""
apply_ahd_verify.py — Verify pipeline cho AHD patch.

Chứa: verify.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from apply_ahd_map import get_protected_files
import update_common
REPO_ROOT = update_common.REPO_ROOT


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120, input_text: str = "") -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, input=input_text)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def verify(patched_files: list[str]) -> bool:
    """Verify pipeline: py_compile, import smoke, qa_doc_audit."""
    # py_compile cho .py mới/thay đổi
    py_files = [f for f in patched_files if f.endswith(".py")]
    for pf in py_files:
        f = REPO_ROOT / pf
        if not f.exists():
            continue
        code, out, err = run_cmd([sys.executable, "-m", "py_compile", str(f)], cwd=REPO_ROOT)
        if code != 0:
            print(f"[FAIL] py_compile {pf}: {err or out}")
            return False

    # import smoke test
    code, out, err = run_cmd([sys.executable, "tools/import_smoke_test.py"], cwd=REPO_ROOT)
    if code != 0:
        print(f"[FAIL] import smoke test: {err or out}")
        return False

    # qa_doc_audit
    code, out, err = run_cmd([sys.executable, ".devin/scripts/qa_doc_audit.py"], cwd=REPO_ROOT)
    if code != 0:
        print(f"[FAIL] qa_doc_audit: {err or out}")
        return False
    try:
        report = json.loads(out)
    except json.JSONDecodeError:
        print("[FAIL] qa_doc_audit output not JSON")
        return False
    if report.get("stale_refs"):
        print(f"[FAIL] stale refs found: {report['stale_refs'][:5]}")
        return False

    # workspace verify
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