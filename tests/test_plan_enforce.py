#!/usr/bin/env python3
"""T5.3: Kiểm thử plan_enforce.py riêng biệt — mở rộng test_plan_enforce.

Bao phủ các nhánh còn thiếu trong plan_enforce:
- _plan_state_name_from_path cho các case khác nhau.
- _get_plan_state_for_task khi orchestrator state không DONE.
- _get_plan_state_for_task khi approval_status != approved.
- _get_plan_state_for_task khi plan_path rỗng.
- _get_plan_state_for_task khi state file corrupt.
- _get_session_state với file corrupt.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import plan_enforce  # noqa: E402


def test_plan_state_name_from_path_docs_plans():
    # plan trong docs/plans/<slug>/ -> <slug>_approved
    name = plan_enforce._plan_state_name_from_path("docs/plans/my-task/IMPLEMENTATION_PLAN.md")
    assert name == "my-task_approved"


def test_plan_state_name_from_path_outside_plans():
    # plan ngoài docs/plans/ -> dùng stem
    name = plan_enforce._plan_state_name_from_path("docs/PLAN.md")
    assert name == "PLAN"


def test_plan_state_name_from_path_empty():
    assert plan_enforce._plan_state_name_from_path("") == ""


def test_plan_state_name_from_path_docs_but_no_plans():
    name = plan_enforce._plan_state_name_from_path("docs/other/plan.md")
    assert name == "plan"


def test_get_plan_state_orchestrator_not_done(tmp_path):
    # Orchestrator state != DONE -> {}
    plan_state_dir = tmp_path / ".devin" / "plan_state"
    plan_state_dir.mkdir(parents=True, exist_ok=True)
    (plan_state_dir / "my-task_orchestrator.json").write_text(
        json.dumps({"state": "PLAN", "approval_status": "approved", "plan_path": "x"}),
        encoding="utf-8",
    )
    assert plan_enforce._get_plan_state_for_task(tmp_path, "my-task") == {}


def test_get_plan_state_not_approved(tmp_path):
    plan_state_dir = tmp_path / ".devin" / "plan_state"
    plan_state_dir.mkdir(parents=True, exist_ok=True)
    (plan_state_dir / "my-task_orchestrator.json").write_text(
        json.dumps({"state": "DONE", "approval_status": "rejected", "plan_path": "x"}),
        encoding="utf-8",
    )
    assert plan_enforce._get_plan_state_for_task(tmp_path, "my-task") == {}


def test_get_plan_state_empty_plan_path(tmp_path):
    plan_state_dir = tmp_path / ".devin" / "plan_state"
    plan_state_dir.mkdir(parents=True, exist_ok=True)
    (plan_state_dir / "my-task_orchestrator.json").write_text(
        json.dumps({"state": "DONE", "approval_status": "approved", "plan_path": ""}),
        encoding="utf-8",
    )
    assert plan_enforce._get_plan_state_for_task(tmp_path, "my-task") == {}


def test_get_plan_state_corrupt_orchestrator(tmp_path):
    plan_state_dir = tmp_path / ".devin" / "plan_state"
    plan_state_dir.mkdir(parents=True, exist_ok=True)
    (plan_state_dir / "my-task_orchestrator.json").write_text("{bad json", encoding="utf-8")
    assert plan_enforce._get_plan_state_for_task(tmp_path, "my-task") == {}


def test_get_plan_state_corrupt_plan_state(tmp_path):
    plan_state_dir = tmp_path / ".devin" / "plan_state"
    plan_state_dir.mkdir(parents=True, exist_ok=True)
    (plan_state_dir / "my-task_orchestrator.json").write_text(
        json.dumps({
            "state": "DONE",
            "approval_status": "approved",
            "plan_path": "docs/plans/my-task/PLAN.md",
        }),
        encoding="utf-8",
    )
    # Plan state file corrupt
    (plan_state_dir / "my-task_approved.json").write_text("{bad", encoding="utf-8")
    assert plan_enforce._get_plan_state_for_task(tmp_path, "my-task") == {}


def test_get_plan_state_missing_plan_state_file(tmp_path):
    plan_state_dir = tmp_path / ".devin" / "plan_state"
    plan_state_dir.mkdir(parents=True, exist_ok=True)
    (plan_state_dir / "my-task_orchestrator.json").write_text(
        json.dumps({
            "state": "DONE",
            "approval_status": "approved",
            "plan_path": "docs/plans/my-task/PLAN.md",
        }),
        encoding="utf-8",
    )
    # Không có my-task_approved.json -> {}
    assert plan_enforce._get_plan_state_for_task(tmp_path, "my-task") == {}


def test_get_session_state_corrupt(tmp_path):
    state_dir = tmp_path / ".devin" / "session_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "bad.json").write_text("{not json", encoding="utf-8")
    assert plan_enforce._get_session_state(tmp_path) == {}


def test_get_session_state_empty_dir(tmp_path):
    state_dir = tmp_path / ".devin" / "session_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    assert plan_enforce._get_session_state(tmp_path) == {}


def test_get_session_state_no_dir(tmp_path):
    # Không có session_state dir -> {}
    assert plan_enforce._get_session_state(tmp_path) == {}


def test_get_session_state_reads_latest(tmp_path):
    state_dir = tmp_path / ".devin" / "session_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    import time
    (state_dir / "old.json").write_text(
        json.dumps({"goal": "old"}), encoding="utf-8",
    )
    time.sleep(0.05)
    (state_dir / "new.json").write_text(
        json.dumps({"goal": "new"}), encoding="utf-8",
    )
    state = plan_enforce._get_session_state(tmp_path)
    assert state["goal"] == "new"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
