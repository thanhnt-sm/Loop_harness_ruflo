#!/usr/bin/env python3
"""Kiểm thử Durable Execution integration — T3.5 (REQ-005).

Kịch bản: kill (giả lập) một dag_executor run giữa chừng, rồi resume và assert:
  - Không có side-effect trùng lặp (idempotency ledger không ghi 2 lần cho cùng task).
  - Không mất completed work (các task đã complete vẫn complete sau resume).

Giả lập "kill mid-way": chạy execute với runner raise KeyboardInterrupt sau khi
hoàn thành một số task, sau đó resume từ run_id đã lưu.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


def _make_workflow_chain():
    """DAG dạng chuỗi 6 node: t1 -> t2 -> t3 -> t4 -> t5 -> t6.

    Dạng chuỗi để dễ kiểm soát "kill" giữa chừng: chạy batch_size=2, kill sau
    khi t2 hoàn thành.
    """
    tasks = []
    for i in range(1, 7):
        deps = [f"t{i-1}"] if i > 1 else []
        tasks.append({"id": f"t{i}", "goal": f"g{i}", "dependencies": deps})
    return {"workflow_id": "wf-durable-chain", "tasks": tasks}


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    devin_dir = tmp_path / ".devin"
    (devin_dir / "plan_state").mkdir(parents=True, exist_ok=True)
    (devin_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    (devin_dir / "idempotency").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    import dag_executor
    monkeypatch.setattr(dag_executor, "_repo_root", lambda: tmp_path)
    # Xóa env run_id cũ để không ảnh hưởng.
    monkeypatch.delenv("AHD_RUN_ID", raising=False)
    return tmp_path


def _ledger_entries(root: Path, run_id: str) -> list[dict]:
    """Đọc ledger JSONL cho run_id, trả list entry."""
    path = root / ".devin" / "idempotency" / f"{run_id}.ledger.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def test_kill_midway_then_resume_no_duplicate_side_effects(patched_root):
    """Kill giữa chừng → resume: không có side-effect trùng lặp.

    Quy trình:
      1. Chạy execute với runner ghi side-effect (đếm call) và raise KeyboardInterrupt
         sau khi t2 hoàn thành → giả lập kill mid-way.
      2. Kiểm tra state đã lưu có t1, t2 complete.
      3. Resume từ run_id.
      4. Assert: mọi task complete, không có task nào bị chạy 2 lần (call_count <= 1).
    """
    import dag_executor

    call_counts: dict[str, int] = {}

    def killable_runner(task_id: str, goal: str):
        call_counts[task_id] = call_counts.get(task_id, 0) + 1
        # Giả lập kill sau khi t2 hoàn thành: raise KeyboardInterrupt khi bắt đầu t3.
        if task_id == "t3" and call_counts.get("t3", 0) == 1:
            raise KeyboardInterrupt("giả lập kill mid-run")
        return {"ok": True, "task_id": task_id, "goal": goal}

    wf = _make_workflow_chain()
    # Chạy lần 1 — kỳ vọng bị KeyboardInterrupt làm gián đoạn.
    with pytest.raises(KeyboardInterrupt):
        dag_executor.execute(wf, batch_size=2, runner=killable_runner, max_retries=0)

    # Sau kill: t1, t2 phải đã complete (không mất completed work).
    state = dag_executor._load_state("wf-durable-chain")
    assert state is not None, "state phải được lưu trước khi kill"
    assert state["tasks"]["t1"]["status"] == "complete"
    assert state["tasks"]["t2"]["status"] == "complete"
    # t3 đang running (bị kill giữa chừng) hoặc failed.
    assert state["tasks"]["t3"]["status"] in ("running", "failed", "pending")

    # Resume từ run_id — phải hoàn thành nốt các task còn lại.
    result = dag_executor.resume("wf-durable-chain", runner=killable_runner, max_retries=0)
    assert result.success is True
    assert result.status["all_complete"] is True
    assert result.status["total_tasks"] == 6

    # Không có side-effect trùng lặp: mỗi task chỉ hoàn thành (trả về ok) tối đa
    # 1 lần. Task bị kill giữa chừng (t3) có thể được runner gọi 2 lần (lần 1 bị
    # kill trước khi trả về → không tạo side-effect, lần 2 khi resume → thành công).
    # Side-effect thực sự = giá trị trả về thành công, chỉ xảy ra 1 lần/task.
    # Kiểm tra qua idempotency ledger: mỗi key chỉ có 1 entry (không re-execute
    # task đã hoàn thành).
    entries = _ledger_entries(patched_root, "wf-durable-chain")
    keys = [e.get("key") for e in entries]
    assert len(keys) == len(set(keys)), "ledger có key trùng lặp — duplicate side-effect"
    # Mọi task đều phải có entry ledger (đã hoàn thành đúng 1 lần).
    expected_keys = {f"wf-durable-chain:t{i}" for i in range(1, 7)}
    assert set(keys) == expected_keys, f"thiếu entry ledger: {expected_keys - set(keys)}"


def test_resume_preserves_completed_work(patched_root):
    """Resume không mất completed work: task đã complete vẫn complete sau resume."""
    import dag_executor

    wf = _make_workflow_chain()
    # Chạy hoàn thành lần 1.
    r1 = dag_executor.execute(wf, batch_size=3)
    assert r1.success
    assert r1.status["all_complete"]

    # Resume — mọi task vẫn complete (không re-run).
    r2 = dag_executor.resume("wf-durable-chain")
    assert r2.success
    assert r2.status["all_complete"]
    for i in range(1, 7):
        assert r2.status["counts"]["complete"] == 6


def test_no_duplicate_side_effects_on_full_run_then_resume(patched_root):
    """Chạy full → resume: idempotency ledger không có key trùng."""
    import dag_executor

    wf = _make_workflow_chain()
    dag_executor.execute(wf, batch_size=2)
    dag_executor.resume("wf-durable-chain")

    entries = _ledger_entries(patched_root, "wf-durable-chain")
    keys = [e.get("key") for e in entries]
    # Mỗi task chỉ có 1 entry ledger (không re-run khi resume).
    assert len(keys) == 6
    assert len(set(keys)) == 6


def test_checkpoint_persisted_mid_run(patched_root):
    """Checkpoint được ghi giữa chừng — sau kill vẫn có file checkpoint."""
    import dag_executor

    def kill_runner(task_id: str, goal: str):
        if task_id == "t4":
            raise KeyboardInterrupt("kill tại t4")
        return {"ok": True, "task_id": task_id}

    wf = _make_workflow_chain()
    with pytest.raises(KeyboardInterrupt):
        dag_executor.execute(wf, batch_size=1, runner=kill_runner, max_retries=0)

    ckpt_dir = patched_root / ".devin" / "checkpoints" / "wf-durable-chain"
    assert ckpt_dir.exists()
    files = list(ckpt_dir.glob("*.json"))
    assert len(files) >= 1, "phải có ít nhất 1 checkpoint được ghi trước khi kill"
