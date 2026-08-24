#!/usr/bin/env python3
"""harness_upgrade_execute.py — Execution functions cho harness upgrade loop.

Chứa _build_execute_task, _changed_files, _revert_unauthorized_changes,
_auto_execute_target, _get_target_coverage.
"""

from __future__ import annotations

import sys
import json
import re
import subprocess
import sys as sys_module
from pathlib import Path
from typing import Optional

# Thêm thư mục .devin/scripts để import khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_upgrade_constants import REPO_ROOT, RESTRICTED_PATTERNS
from harness_upgrade_utils import _python, _run


def _build_execute_task(target: str) -> str:
    """Xây dựng prompt chặt cho devin -p dựa trên target.

    Giới hạn: chỉ sửa tests, .cmd/.sh wrappers nếu cần, hoặc file config tối thiểu.
    KHÔNG sửa source .devin/scripts/*.py, .devin/hooks/*.py, sbom/, hook_hashes.json,
    .env, HLK/, hoặc các security policy.
    """
    base = (
        "You are in a harness upgrade loop. Make the smallest safe change, "
        "preferably in tests/ or cross-platform wrapper files, then run pytest to verify. "
        "DO NOT modify source code in .devin/scripts/*.py, .devin/hooks/*.py, "
        "sbom/python.sbom.json, .devin/hook_hashes.json, .env, HLK/, or security policies. "
        "DO NOT regenerate SBOM or hook hashes unless explicitly needed."
    )
    if target.startswith("proactive:improve coverage for "):
        module = target[len("proactive:improve coverage for "):]
        return (
            f"{base} Improve test coverage for {module}. "
            f"Add focused unit tests in tests/ (or .devin/scripts/test_*.py if appropriate) "
            f"that exercise the uncovered lines. Run pytest for that module to verify."
        )

    if target.startswith("audit:"):
        parts = target.split(":", 3)
        if len(parts) >= 3:
            source = parts[1]
            detail = parts[2]
            return (
                f"{base} Fix the {source} audit finding: {detail}. "
                f"Verify with the relevant audit script after the fix."
            )
        return f"{base} Fix the audit finding: {target}."

    # Test target
    return (
        f"{base} Fix the failing test {target}. "
        f"If the test fails because a Windows external command is missing, "
        f"add cross-platform wrappers (e.g. .cmd) or adjust the test to use venv python directly. "
        f"Run the failing test to verify."
    )


def _changed_files() -> set[str]:
    """Trả về set file đang thay đổi hoặc untracked so với HEAD (git status --porcelain)."""
    rc, out, _ = _run(["git", "status", "--porcelain"], timeout=30)
    if rc != 0:
        return set()
    files: set[str] = set()
    for line in out.splitlines():
        if line.startswith("?? ") or line.startswith("!! "):
            # Untracked / ignored
            files.add(line[3:].strip())
        elif len(line) >= 3:
            files.add(line[2:].strip().split(" -> ", 1)[-1])
    return files


def _revert_unauthorized_changes(before: set[str]) -> list[str]:
    """Revert các file bị devin -p sửa nằm trong RESTRICTED_PATTERNS và chưa dirty trước đó.

    Trả về danh sách file đã revert/xóa.
    """
    after = _changed_files()
    new_changed = after - before
    unauthorized = [f for f in new_changed if any(re.search(p, f) for p in RESTRICTED_PATTERNS)]
    if not unauthorized:
        return []
    print(f"[harness_upgrade_loop] devin -p chạm file cấm: {unauthorized}", file=sys.stderr)
    tracked = [f for f in unauthorized if Path(f).exists() and _run(["git", "ls-files", "--error-unmatch", f], timeout=10)[0] == 0]
    untracked = [f for f in unauthorized if f not in tracked]
    if tracked:
        _run(["git", "checkout", "HEAD", "--"] + tracked, timeout=30)
    for f in untracked:
        Path(f).unlink(missing_ok=True)
        # Nếu là thư mục rỗng do devin -p tạo, xóa luôn
        p = Path(f).parent
        try:
            if p != REPO_ROOT and p.exists() and not any(p.iterdir()):
                p.rmdir()
        except OSError:
            pass
    return unauthorized


def _auto_execute_target(target: str, timeout: int = 1800) -> tuple[int, str, str]:
    """Tự động gọi devin -p để thực thi target.

    Trả (rc, stdout, stderr) như _run().
    Sau khi chạy xong, kiểm tra và revert các thay đổi trái phép.
    """
    before = _changed_files()
    task = _build_execute_task(target)
    print(f"[harness_upgrade_loop] Auto-execute target via devin -p: {target}")
    # devin CLI phải có trên PATH
    rc, out, err = _run(
        ["devin", "-p", "--permission-mode", "accept-edits", "--", task],
        timeout=timeout,
    )
    if rc == 0:
        unauthorized = _revert_unauthorized_changes(before)
        if unauthorized:
            return 1, "", f"Unauthorized changes reverted: {unauthorized}"
    return rc, out, err


def _get_target_coverage(target: str) -> Optional[float]:
    """Lấy percent_covered của module trong target proactive từ coverage.json."""
    prefix = "proactive:improve coverage for "
    if not target.startswith(prefix):
        return None
    module = target[len(prefix):]
    cov_file = REPO_ROOT / "coverage.json"
    if not cov_file.exists():
        return None
    try:
        data = json.loads(cov_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Tìm key khớp module (có thể dùng \ hoặc /)
    for fname, info in data.get("files", {}).items():
        if Path(fname).as_posix() == module:
            return float(info.get("summary", {}).get("percent_covered", 0))
    return None