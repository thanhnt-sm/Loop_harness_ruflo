#!/usr/bin/env python3
"""Kiểm thử plan_orchestrator.py — step-based Plan Phase FSM v1.

Bộ test phản ánh contract mới: --init trả state_file + next_action,
--step chuyển state theo results. Không còn chế độ one-shot auto-DONE.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/scripts/plan_fsm"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from plan_fsm.storage import fingerprint  # noqa: E402

PLAN_STATE_DIR = REPO_ROOT / ".devin" / "plan_state"


def _run(args):
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "scripts" / "plan_orchestrator.py"), *args]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, env=env)


def _step(state_file: str, results: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
        results_path = f.name
    try:
        res = _run(["--step", "--state", state_file, "--results", results_path])
        assert res.returncode == 0, res.stderr
        return json.loads(res.stdout)
    finally:
        Path(results_path).unlink(missing_ok=True)


def teardown_module():
    for slug in ("add-jwt-authentication", "refactor-the-entire-authentication-architecture-across-multi"):
        for f in PLAN_STATE_DIR.glob(f"{slug}*"):
            f.unlink()


def test_init_s_tier():
    res = _run(["--init", "--task", "fix typo"])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["tier"] == "S"
    assert data["current_state"] == "DONE"
    assert data["next_action"]["action"] == "skip"
    assert not data.get("plan_path")


def test_init_m_tier():
    res = _run(["--init", "--task", "add JWT authentication"])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["tier"] == "M"
    assert data["current_state"] == "BRAINSTORM"
    assert data["task_slug"] == "add-jwt-authentication"
    assert data["task_fingerprint"] == fingerprint("add JWT authentication")
    assert data["next_action"]["action"] == "brainstorm"
    assert Path(data["state_file"]).exists()


def test_init_xl_tier():
    res = _run(["--init", "--task", "refactor the entire authentication architecture across multiple services with security compliance"])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["tier"] == "XL"
    assert data["current_state"] == "BRAINSTORM"
    assert data["next_action"]["action"] == "brainstorm"


def test_init_without_task_fails():
    res = _run(["--init"])
    assert res.returncode == 2


def test_orchestrator_state_written_with_fingerprint():
    res = _run(["--init", "--task", "add JWT authentication"])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    state_file = Path(data["state_file"])
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["state"] == "BRAINSTORM"
    assert state["task_fingerprint"] == fingerprint("add JWT authentication")


def test_step_brainstorm_to_scout():
    res = _run(["--init", "--task", "add JWT authentication"])
    data = json.loads(res.stdout)
    out = _step(data["state_file"], {"action": "brainstorm", "brainstorm_results": []})
    assert out["current_state"] == "ANALYZE"
    assert out["next_action"]["action"] == "dispatch_scouts"


def test_full_plan_phase_walk():
    res = _run(["--init", "--task", "add JWT authentication"])
    data = json.loads(res.stdout)
    state_file = data["state_file"]
    slug = data["task_slug"]

    sdd_path = f"docs/plans/{slug}/SOLUTION_DESIGN.md"
    plan_path = f"docs/plans/{slug}/IMPLEMENTATION_PLAN.md"
    quality_path = f"docs/plans/{slug}/QUALITY_REPORT.md"

    transitions = [
        ("brainstorm", {"brainstorm_results": []}, "ANALYZE", "dispatch_scouts"),
        ("wait_scouts", {"scout_results": []}, "DESIGN", "dispatch_architect"),
        ("dispatch_architect", {"sdd_path": sdd_path}, "REVIEW", "dispatch_reviewers"),
        ("dispatch_reviewers", {"findings": []}, "SDD_APPROVAL", "present_sdd_approval"),
        ("present_sdd_approval", {"decision": "approved"}, "PLAN", "decompose_plan"),
        ("decompose_plan", {"plan_path": plan_path}, "GAP_SCAN", "gap_scan"),
        ("gap_scan", {"gap_findings": []}, "QC", "run_qc"),
        ("run_qc", {"qc_result": {"all_pass": True, "report_path": quality_path}}, "PLAN_ENHANCE", "plan_enhance"),
        ("plan_enhance", {"enhance_findings": []}, "PLAN_APPROVAL", "present_plan_approval"),
        ("present_plan_approval", {"decision": "approved"}, "WRITE_STATE", "write_plan_state"),
        ("write_plan_state", {}, "DONE", "done"),
    ]

    for action, payload, expected_state, next_action in transitions:
        out = _step(state_file, {"action": action, **payload})
        assert out["current_state"] == expected_state, f"After {action}: expected {expected_state}, got {out['current_state']}"
        assert out["next_action"]["action"] == next_action, f"After {action}: expected {next_action}, got {out['next_action']['action']}"

    final_state = json.loads(Path(state_file).read_text(encoding="utf-8"))
    assert final_state["state"] == "DONE"
    assert final_state["plan_approved"] is True
    assert final_state["sdd_approved"] is True
    assert final_state["plan_path"] == plan_path


def test_fingerprint_whitespace_stable():
    assert fingerprint("add   JWT   authentication") == fingerprint("add JWT authentication")


def test_slug_collision_second_task_blocked(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO_ROOT / ".devin" / "hooks"))
    import plan_enforce

    state_dir = tmp_path / ".devin" / "plan_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    slug = "add-jwt-authentication"
    task_a = "add JWT authentication"
    task_b = "add jwt authentication!"

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

    pa = plan_enforce._get_plan_state_for_task(tmp_path, slug, fingerprint(task_a), task_a)
    pb = plan_enforce._get_plan_state_for_task(tmp_path, slug, fingerprint(task_b), task_b)
    assert pa
    assert not pb
