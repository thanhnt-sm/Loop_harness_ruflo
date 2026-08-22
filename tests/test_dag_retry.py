"""Unit tests cho dag_executor — T12: Retry/Branch State Machine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))
from dag_executor import _handle_failure, _retry_task, _branch_task, MAX_RETRIES


def _make_state(task_id="T1"):
    return {
        "workflow_id": "test",
        "tasks": {task_id: {"status": "failed", "result": None, "completed_at": None}},
    }


def test_retry_on_failure():
    """Failed task → retry_pending (retry_count < MAX_RETRIES)."""
    state = _make_state()
    next_status = _handle_failure(state, "T1", "timeout error")
    assert next_status == "retry_pending"
    assert state["tasks"]["T1"]["retry_count"] == 1
    assert state["tasks"]["T1"]["last_error"] == "timeout error"


def test_max_retries_human_review():
    """Sau MAX_RETRIES → human_review."""
    state = _make_state()
    state["tasks"]["T1"]["retry_count"] = MAX_RETRIES
    next_status = _handle_failure(state, "T1", "persistent error")
    assert next_status == "human_review"


def test_retry_task_transition():
    """retry_pending → retrying."""
    state = _make_state()
    _handle_failure(state, "T1", "error")
    result = _retry_task(state, "T1")
    assert result["retried"] is True
    assert result["next_status"] == "retrying"


def test_branch_task():
    """Branch task được tạo với branch_of."""
    state = _make_state()
    result = _branch_task(state, "T1", "condition_A")
    assert result["branched"] is True
    assert "T1_branch_" in result["branch_task_id"]
    assert state["tasks"][result["branch_task_id"]]["branch_of"] == "T1"


if __name__ == "__main__":
    tests = [test_retry_on_failure, test_max_retries_human_review, test_retry_task_transition, test_branch_task]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
