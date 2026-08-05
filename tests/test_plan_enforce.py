#!/usr/bin/env python3
"""Kiểm thử cho plan_enforce.py — PreToolUse enforcement hook."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_STATE_DIR = REPO_ROOT / ".devin" / "plan_state"
SESSION_STATE_DIR = REPO_ROOT / ".devin" / "session_state"
PLANS_DIR = REPO_ROOT / "docs" / "plans"


def _run(stdin_json):
    # Chạy plan_enforce.py với JSON từ stdin
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "hooks" / "plan_enforce.py")]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(cmd, input=json.dumps(stdin_json), capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    return result


def _slugify(text):
    # Logic slugify giống plan_enforce.py
    import re
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60] if slug else "task"


def _create_session(task):
    # Tạo session state mới nhất để hook lấy task
    SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    session_path = SESSION_STATE_DIR / f"test_{int(time.time() * 1000)}.json"
    session_path.write_text(json.dumps({"goal": task}, ensure_ascii=False), encoding="utf-8")


def _create_orchestrator_state(task, approved=False):
    # Tạo orchestrator state cho task
    PLAN_STATE_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(task)
    state = {
        "task_description": task,
        "task_slug": slug,
        "state": "DONE" if approved else "APPROVAL",
        "tier": "M",
        "approval_status": "approved" if approved else "pending",
        "plan_path": str(PLANS_DIR / slug / "IMPLEMENTATION_PLAN.md"),
    }
    (PLAN_STATE_DIR / f"{slug}_orchestrator.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _create_approval_state(task):
    # Tạo approval state cho task
    slug = _slugify(task)
    plan_dir = PLANS_DIR / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "IMPLEMENTATION_PLAN.md").write_text("# Plan", encoding="utf-8")
    state = {
        "plan_file": f"docs/plans/{slug}/IMPLEMENTATION_PLAN.md",
        "status": "approved",
        "reviewer": "tester",
        "date": "",
        "comments": "",
    }
    (PLAN_STATE_DIR / f"{slug}_approved.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def setup_module():
    # Tạo thư mục cần thiết
    PLAN_STATE_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)


def teardown_module():
    # Dọn dẹp state test
    for d in [PLAN_STATE_DIR, SESSION_STATE_DIR]:
        if d.exists():
            for f in d.glob("*test*"):
                if f.is_file():
                    f.unlink()
            for f in d.glob("__test*"):
                if f.is_file():
                    f.unlink()
    if (PLANS_DIR / "__testenforce__").exists():
        shutil.rmtree(PLANS_DIR / "__testenforce__")


def test_no_plan_blocks_write():
    # Không có orchestrator state -> block write
    _create_session("add feature")
    res = _run({"tool_name": "write", "tool_input": {"file_path": "src/app.py", "content": "x"}})
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["allow"] is False
    assert data.get("enforcement") == "plan_required"


def test_s_tier_allows_write():
    # S-tier task -> không cần plan
    _create_session("fix typo")
    res = _run({"tool_name": "write", "tool_input": {"file_path": "src/app.py", "content": "x"}})
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["allow"] is True


def test_approved_plan_allows_write():
    # Có orchestrator state DONE và approval state -> cho phép write
    task = "add jwt auth"
    _create_session(task)
    _create_orchestrator_state(task, approved=True)
    _create_approval_state(task)
    res = _run({"tool_name": "write", "tool_input": {"file_path": "src/app.py", "content": "x"}})
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["allow"] is True


def test_plan_file_exempt():
    # Viết file trong docs/plans được miễn enforcement
    _create_session("add feature no state")
    res = _run({"tool_name": "write", "tool_input": {"file_path": "docs/plans/newtask/IMPLEMENTATION_PLAN.md", "content": "# Plan"}})
    assert res.returncode == 0


def test_template_file_exempt():
    # Viết file trong docs/templates được miễn
    _create_session("add feature no state")
    res = _run({"tool_name": "write", "tool_input": {"file_path": "docs/templates/PLAN_TEMPLATE.md", "content": "# T"}})
    assert res.returncode == 0


def test_non_write_tool_allowed():
    # exec tool không bị enforce
    _create_session("add feature")
    res = _run({"tool_name": "exec", "tool_input": {"command": "ls"}})
    assert res.returncode == 0


def test_fail_closed_on_invalid_json():
    # JSON lỗi -> fail-closed
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "hooks" / "plan_enforce.py")]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(cmd, input="not json", capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["allow"] is False
    assert data.get("enforcement") == "hook_error"


def test_only_current_task_plan_allowed():
    # Có approved plan cho task khác nhưng không cho task hiện tại -> block
    other = "other approved task"
    current = "current unapproved task"
    _create_session(current)
    _create_orchestrator_state(other, approved=True)
    _create_approval_state(other)
    res = _run({"tool_name": "write", "tool_input": {"file_path": "src/app.py", "content": "x"}})
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["allow"] is False


def test_path_traversal_not_exempt():
    # Path traversal qua docs/plans/../secrets không được miễn
    _create_session("add feature")
    res = _run({"tool_name": "write", "tool_input": {"file_path": "docs/plans/../secrets/file.py", "content": "x"}})
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["allow"] is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
