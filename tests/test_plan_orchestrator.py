#!/usr/bin/env python3
"""Kiểm thử plan_orchestrator.py — Graph-based orchestrator v2.

v1 (FSM, --step) đã được thay bằng v2 (StateGraph, --init chạy trọn luồng).
Bộ test này phản ánh interface thực: --init --task trả JSON một-shot với
task_slug / task_fingerprint / tier / state / plan_approved.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/scripts/plan_fsm"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from plan_fsm.storage import fingerprint  # noqa: E402

PLAN_STATE_DIR = REPO_ROOT / ".devin" / "plan_state"
PLANS_DIR = REPO_ROOT / "docs" / "plans"

# Slug tạo bởi các test M/XL — cần dọn ở teardown.
_TEST_SLUGS = (
    "add-jwt-authentication",
    "refactor-the-entire-authentication-architecture-across-multi",
)


def _run(args):
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "scripts" / "plan_orchestrator.py"), *args]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    return result


def teardown_module():
    for slug in _TEST_SLUGS:
        for f in PLAN_STATE_DIR.glob(f"{slug}*"):
            f.unlink()


def test_init_s_tier():
    # Task đơn giản phân loại S-tier, skip Plan Phase -> DONE, không cần plan.
    res = _run(["--init", "--task", "fix typo"])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["tier"] == "S"
    assert data["state"] == "DONE"
    assert not data.get("plan_path")


def test_init_m_tier():
    # Task trung bình: chạy trọn graph -> DONE + plan approved.
    res = _run(["--init", "--task", "add JWT authentication"])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["tier"] == "M"
    assert data["state"] == "DONE"
    assert data["task_slug"] == "add-jwt-authentication"
    assert data["task_fingerprint"] == fingerprint("add JWT authentication")
    assert data["plan_path"]
    assert data["plan_approved"] is True


def test_init_xl_tier():
    # Task lớn phân loại XL-tier.
    res = _run(["--init", "--task", "refactor the entire authentication architecture across multiple services with security compliance"])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["tier"] == "XL"
    assert data["state"] == "DONE"
    assert data["plan_approved"] is True


def test_init_without_task_fails():
    # Thiếu --task -> argparse error (exit 2).
    res = _run(["--init"])
    assert res.returncode == 2


def test_orchestrator_state_written_with_fingerprint():
    # State file trên disk phải đủ metadata để plan_enforce bind đúng task.
    res = _run(["--init", "--task", "add JWT authentication"])
    assert res.returncode == 0, res.stderr
    state_file = PLAN_STATE_DIR / "add-jwt-authentication_orchestrator.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["state"] == "DONE"
    assert state["approval_status"] == "approved"
    assert state["task_fingerprint"] == fingerprint("add JWT authentication")


def test_fingerprint_whitespace_stable():
    # Fingerprint chỉ chuẩn hóa khoảng trắng — 2 cách viết cùng task cho cùng fp.
    assert fingerprint("add   JWT   authentication") == fingerprint("add JWT authentication")


def test_slug_collision_second_task_blocked(tmp_path, monkeypatch):
    # V5-02: hai task trùng slug nhưng khác nội dung -> plan_enforce phải block task thứ 2.
    sys.path.insert(0, str(REPO_ROOT / ".devin" / "hooks"))
    import plan_enforce

    state_dir = tmp_path / ".devin" / "plan_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    slug = "add-jwt-authentication"
    task_a = "add JWT authentication"
    task_b = "add jwt authentication!"  # cùng slug, khác nội dung

    assert fingerprint(task_a) != fingerprint(task_b)

    (state_dir / f"{slug}_orchestrator.json").write_text(json.dumps({
        "state": "DONE",
        "approval_status": "approved",
        "task_description": task_a,
        "task_fingerprint": fingerprint(task_a),
        "plan_path": f"docs/plans/{slug}/IMPLEMENTATION_PLAN.md",
    }), encoding="utf-8")
    (state_dir / f"{slug}_approved.json").write_text(
        json.dumps({"status": "approved"}), encoding="utf-8",
    )

    monkeypatch.setattr(plan_enforce, "_repo_root", lambda: tmp_path)

    # Task A (đúng) -> ALLOW; Task B (collision) -> BLOCK.
    pa = plan_enforce._get_plan_state_for_task(tmp_path, slug, fingerprint(task_a), task_a)
    pb = plan_enforce._get_plan_state_for_task(tmp_path, slug, fingerprint(task_b), task_b)
    assert pa
    assert not pb


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
