#!/usr/bin/env python3
"""Kiểm thử dag_executor durable — T2.7 (REB-007).

Các ca kiểm thử:
1. execute chạy DAG 10 node mix serial/parallel đến hoàn thành.
2. resume từ run_id hoàn thành ngay (lấy state đã lưu).
3. Checkpoint được ghi sau mỗi batch.
4. Retry transient: runner lỗi lần đầu, thành công lần sau.
5. on_node_complete cập nhật state.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


def _make_workflow_10():
    return {
        "workflow_id": "wf-dag-10",
        "tasks": [
            {"id": "t1", "goal": "g1", "dependencies": []},
            {"id": "t2", "goal": "g2", "dependencies": []},
            {"id": "t3", "goal": "g3", "dependencies": ["t1"]},
            {"id": "t4", "goal": "g4", "dependencies": ["t2"]},
            {"id": "t5", "goal": "g5", "dependencies": ["t3", "t4"]},
            {"id": "t6", "goal": "g6", "dependencies": ["t1"]},
            {"id": "t7", "goal": "g7", "dependencies": ["t2"]},
            {"id": "t8", "goal": "g8", "dependencies": ["t6", "t7"]},
            {"id": "t9", "goal": "g9", "dependencies": ["t5"]},
            {"id": "t10", "goal": "g10", "dependencies": ["t8", "t9"]},
        ],
    }


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    devin_dir = tmp_path / ".devin"
    (devin_dir / "plan_state").mkdir(parents=True, exist_ok=True)
    (devin_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    (devin_dir / "idempotency").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    # dag_executor dùng _repo_root nội bộ
    import dag_executor
    monkeypatch.setattr(dag_executor, "_repo_root", lambda: tmp_path)
    return tmp_path


def test_execute_10_nodes_complete(patched_root, monkeypatch):
    import dag_executor
    wf = _make_workflow_10()
    result = dag_executor.execute(wf, batch_size=3)
    assert result.success is True
    assert result.status["all_complete"] is True
    assert result.status["total_tasks"] == 10
    for i in range(1, 11):
        assert f"t{i}" in result.results


def test_resume_uses_saved_state(patched_root, monkeypatch):
    import dag_executor
    wf = _make_workflow_10()
    r1 = dag_executor.execute(wf, batch_size=5)
    assert r1.success
    # Resume từ cùng run_id phải hoàn thành ngay
    r2 = dag_executor.resume("wf-dag-10")
    assert r2.success
    assert r2.status["all_complete"] is True


def test_checkpoint_files_created(patched_root, monkeypatch):
    import dag_executor
    wf = _make_workflow_10()
    dag_executor.execute(wf, batch_size=2)
    ckpt_dir = patched_root / ".devin" / "checkpoints" / "wf-dag-10"
    assert ckpt_dir.exists()
    files = list(ckpt_dir.glob("*.json"))
    assert len(files) >= 1


def test_retry_transient_then_success(patched_root, monkeypatch):
    import dag_executor
    calls = {"t3": 0}

    def flaky_runner(task_id, goal):
        if task_id == "t3":
            calls[task_id] += 1
            if calls[task_id] < 2:
                raise RuntimeError("transient")
        return {"ok": True, "task_id": task_id}

    wf = _make_workflow_10()
    result = dag_executor.execute(wf, batch_size=3, runner=flaky_runner, max_retries=2)
    assert result.success is True
    assert calls["t3"] == 2


def test_on_node_complete(patched_root, monkeypatch):
    import dag_executor
    wf = {"workflow_id": "wf-onc", "tasks": [{"id": "a", "goal": "ga", "dependencies": []}]}
    state = dag_executor._init_state(wf)
    dag_executor._save_state(state)
    dag_executor.on_node_complete("a", {"ok": True}, run_id="wf-onc")
    state = dag_executor._load_state("wf-onc")
    assert state["tasks"]["a"]["status"] == "complete"
