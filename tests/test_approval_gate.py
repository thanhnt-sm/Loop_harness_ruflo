#!/usr/bin/env python3
"""Kiểm thử cho approval_gate.py."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(args):
    # Chạy approval_gate.py với các tham số
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "scripts" / "approval_gate.py"), *args]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    return result


def _plan_dir(task):
    # Đường dẫn docs/plans/<task_slug>
    return REPO_ROOT / "docs" / "plans" / task


def setup_module():
    # Tạo thư mục test
    (_plan_dir("__test_approval__")).mkdir(parents=True, exist_ok=True)
    (_plan_dir("__test_approval__2")).mkdir(parents=True, exist_ok=True)


def teardown_module():
    # Xóa thư mục test và state
    for slug in ["__test_approval__", "__test_approval__2"]:
        d = _plan_dir(slug)
        if d.exists():
            shutil.rmtree(d)
    state_dir = REPO_ROOT / ".devin" / "plan_state"
    for f in state_dir.glob("__test_approval__*"):
        f.unlink()


def test_approve_creates_unique_state():
    # Approve tạo state file duy nhất theo task_slug
    plan = _plan_dir("__test_approval__") / "IMPLEMENTATION_PLAN.md"
    plan.write_text("# Plan", encoding="utf-8")
    res = _run([str(plan), "--approve", "--reviewer", "tester"])
    assert res.returncode == 0
    state = json.loads(res.stdout)
    assert state["status"] == "approved"
    assert state["plan_file"] == str(Path("docs/plans/__test_approval__/IMPLEMENTATION_PLAN.md"))
    state_file = REPO_ROOT / ".devin" / "plan_state" / "__test_approval___approved.json"
    assert state_file.exists()


def test_no_approval_blocks_write():
    # Plan chưa approve -> check trả denied
    plan = _plan_dir("__test_approval__") / "ANOTHER_PLAN.md"
    plan.write_text("# Another", encoding="utf-8")
    state_file = REPO_ROOT / ".devin" / "plan_state" / "__test_approval___approved.json"
    if state_file.exists():
        state_file.unlink()
    res = _run([str(plan), "--status"])
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["status"] == "pending"


def test_same_stem_unique_filenames():
    # Hai plan cùng tên IMPLEMENTATION_PLAN.md ở task khác nhau không ghi đè
    plan1 = _plan_dir("__test_approval__") / "IMPLEMENTATION_PLAN.md"
    plan2 = _plan_dir("__test_approval__2") / "IMPLEMENTATION_PLAN.md"
    plan1.write_text("# Plan 1", encoding="utf-8")
    plan2.write_text("# Plan 2", encoding="utf-8")
    res1 = _run([str(plan1), "--approve", "--reviewer", "t1"])
    res2 = _run([str(plan2), "--approve", "--reviewer", "t2"])
    assert res1.returncode == 0
    assert res2.returncode == 0
    state1 = json.loads((REPO_ROOT / ".devin" / "plan_state" / "__test_approval___approved.json").read_text(encoding="utf-8"))
    state2 = json.loads((REPO_ROOT / ".devin" / "plan_state" / "__test_approval__2_approved.json").read_text(encoding="utf-8"))
    assert state1["plan_file"] == str(Path("docs/plans/__test_approval__/IMPLEMENTATION_PLAN.md"))
    assert state2["plan_file"] == str(Path("docs/plans/__test_approval__2/IMPLEMENTATION_PLAN.md"))


def test_reject_marks_rejected():
    # Reject plan -> status rejected
    plan = _plan_dir("__test_approval__") / "IMPLEMENTATION_PLAN.md"
    plan.write_text("# Plan", encoding="utf-8")
    res = _run([str(plan), "--reject", "--reviewer", "tester", "--reason", "scope too large"])
    assert res.returncode != 0
    state = json.loads(res.stdout)
    assert state["status"] == "rejected"
    assert state["comments"] == "scope too large"


def test_request_changes_marks_changes_requested():
    # Request changes -> status changes_requested
    plan = _plan_dir("__test_approval__") / "IMPLEMENTATION_PLAN.md"
    plan.write_text("# Plan", encoding="utf-8")
    res = _run([str(plan), "--request-changes", "--reviewer", "tester", "--reason", "add tests"])
    assert res.returncode != 0
    state = json.loads(res.stdout)
    assert state["status"] == "changes_requested"
    assert state["comments"] == "add tests"


def test_fail_closed_on_missing_plan():
    # Plan file không tồn tại -> lỗi
    res = _run(["nonexistent.md", "--status"])
    assert res.returncode != 0


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
