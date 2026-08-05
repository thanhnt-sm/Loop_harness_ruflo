#!/usr/bin/env python3
"""Kiểm thử cho plan_orchestrator.py — FSM state machine."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_STATE_DIR = REPO_ROOT / ".devin" / "plan_state"
PLANS_DIR = REPO_ROOT / "docs" / "plans"


def _run(args, input_text=""):
    # Chạy plan_orchestrator.py với các tham số
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "scripts" / "plan_orchestrator.py"), *args]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(cmd, input=input_text, capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    return result


def _step(state_file, action, extra=None):
    # Gọi --step với kết quả từ action (ghi tạm results vào file)
    payload = {"action": action}
    if extra:
        payload.update(extra)
    tmp = PLAN_STATE_DIR / "_test_results.json"
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    res = _run(["--step", "--state", str(state_file), "--results", str(tmp)])
    if res.returncode != 0:
        print("STDERR:", res.stderr)
    assert res.returncode == 0, f"--step failed: {res.stderr}"
    return json.loads(res.stdout)


def _state(state_file):
    # Đọc state file từ disk
    return json.loads(Path(state_file).read_text(encoding="utf-8"))


def _fast_forward_to_qc(state_file):
    # Đẩy FSM từ ANALYZE → DESIGN → REVIEW → PLAN → QC
    s = _state(state_file)["state"]
    if s == "ANALYZE":
        _step(state_file, "wait_scouts", {"scout_results": []})
    s = _state(state_file)["state"]
    if s == "DESIGN":
        _step(state_file, "dispatch_architect", {"sdd_path": str(PLANS_DIR / "__test__" / "SOLUTION_DESIGN.md")})
    s = _state(state_file)["state"]
    if s == "REVIEW":
        _step(state_file, "dispatch_reviewers", {"findings": []})
    s = _state(state_file)["state"]
    if s == "PLAN":
        _step(state_file, "decompose_plan", {"plan_path": str(PLANS_DIR / "__test__" / "IMPLEMENTATION_PLAN.md")})


def setup_module():
    # Tạo thư mục test trước mỗi module
    PLAN_STATE_DIR.mkdir(parents=True, exist_ok=True)
    (PLANS_DIR / "__test__").mkdir(parents=True, exist_ok=True)


def teardown_module():
    # Dọn dẹp thư mục test sau module
    if (PLANS_DIR / "__test__").exists():
        shutil.rmtree(PLANS_DIR / "__test__")
    for f in PLAN_STATE_DIR.glob("__test__*"):
        f.unlink()


def test_init_s_tier():
    # Task đơn giản phân loại S-tier và skip Plan Phase
    res = _run(["--init", "--task", "fix typo"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["tier"] == "S"
    assert data["current_state"] == "DONE"
    assert data["next_action"]["action"] == "skip"


def test_init_m_tier():
    # Task trung bình phân loại M-tier và bắt đầu từ ANALYZE
    res = _run(["--init", "--task", "add JWT authentication"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["tier"] == "M"
    assert data["current_state"] == "ANALYZE"
    assert data["next_action"]["action"] == "dispatch_scouts"


def test_init_xl_tier():
    # Task lớn phân loại XL-tier
    res = _run(["--init", "--task", "refactor the entire authentication architecture across multiple services with security compliance"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["tier"] == "XL"
    assert data["current_state"] == "ANALYZE"


def test_full_happy_path():
    # Luồng hoàn chỉnh: ANALYZE → DESIGN → REVIEW → PLAN → QC → APPROVAL → WRITE_STATE → DONE
    res = _run(["--init", "--task", "full happy path test"])
    data = json.loads(res.stdout)
    state_file = data["state_file"]
    _step(state_file, "wait_scouts", {"scout_results": []})
    _step(state_file, "dispatch_architect", {"sdd_path": str(PLANS_DIR / "__test__" / "SOLUTION_DESIGN.md")})
    _step(state_file, "dispatch_reviewers", {"findings": []})
    _step(state_file, "decompose_plan", {"plan_path": str(PLANS_DIR / "__test__" / "IMPLEMENTATION_PLAN.md")})
    _step(state_file, "run_qc", {"qc_result": {"all_pass": True, "report_path": "qr.md"}})
    _step(state_file, "present_approval", {"decision": "approved"})
    final = _step(state_file, "write_plan_state")
    assert final["current_state"] == "DONE"
    assert final["next_action"]["action"] == "done"


def test_rejection_path():
    # User từ chối plan -> chuyển REJECTED
    res = _run(["--init", "--task", "rejection path test"])
    data = json.loads(res.stdout)
    state_file = data["state_file"]
    _fast_forward_to_qc(state_file)
    _step(state_file, "run_qc", {"qc_result": {"all_pass": True, "report_path": "qr.md"}})
    final = _step(state_file, "present_approval", {"decision": "rejected", "reason": "scope too large"})
    assert final["current_state"] == "REJECTED"


def test_changes_requested_path():
    # User yêu cầu sửa -> quay lại DESIGN
    res = _run(["--init", "--task", "changes requested path test"])
    data = json.loads(res.stdout)
    state_file = data["state_file"]
    _fast_forward_to_qc(state_file)
    _step(state_file, "run_qc", {"qc_result": {"all_pass": True, "report_path": "qr.md"}})
    final = _step(state_file, "present_approval", {"decision": "changes_requested", "modifications": "add rollback"})
    assert final["current_state"] == "DESIGN"


def test_revision_loop_then_pass():
    # Review phát hiện BLOCKING, revision, rồi pass
    res = _run(["--init", "--task", "revision loop pass test"])
    data = json.loads(res.stdout)
    state_file = data["state_file"]
    _step(state_file, "wait_scouts", {"scout_results": []})
    _step(state_file, "dispatch_architect", {"sdd_path": str(PLANS_DIR / "__test__" / "SOLUTION_DESIGN.md")})
    _step(state_file, "dispatch_reviewers", {"findings": [{"severity": "BLOCKING", "issue": "missing auth"}]})
    _step(state_file, "dispatch_revision", {"sdd_path": str(PLANS_DIR / "__test__" / "SOLUTION_DESIGN.md")})
    final = _step(state_file, "dispatch_reviewers", {"findings": []})
    assert final["current_state"] == "PLAN"


def test_qc_max_rounds_escalate():
    # QC fail 3 lần -> ESCALATE
    res = _run(["--init", "--task", "qc escalate test"])
    data = json.loads(res.stdout)
    state_file = data["state_file"]
    for round_ in range(3):
        _fast_forward_to_qc(state_file)
        _step(state_file, "run_qc", {"qc_result": {"all_pass": False, "report_path": "qr.md"}})
    final = _state(state_file)
    assert final["state"] == "ESCALATE"
    assert final["qc_round"] == 3


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
