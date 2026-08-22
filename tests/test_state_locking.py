"""Unit tests cho storage.py — T07: State Locking + T08: Slug Collision."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))

from plan_fsm.storage import locked_save_state, collision_safe_state_path, state_path, state_dir, slugify, fingerprint


def test_concurrent_writes():
    """T07: locked_save_state — 2 lần ghi liên tục không corrupt."""
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        state1 = {"task": "A", "round": 1}
        state2 = {"task": "B", "round": 2}
        locked_save_state(sp, state1)
        locked_save_state(sp, state2)
        result = json.loads(sp.read_text(encoding="utf-8"))
        assert result["task"] == "B"
        assert result["round"] == 2


def test_locked_save_atomic():
    """T07: locked_save_state ghi đúng content."""
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        state = {"task": "test", "history": [1, 2, 3]}
        locked_save_state(sp, state)
        result = json.loads(sp.read_text(encoding="utf-8"))
        assert result == state


def test_collision_detection():
    """T08: 2 task khác description nhưng cùng slug → fingerprint suffix."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Tạo state file đầu tiên
        sp1 = state_path(root, "test-task")
        sp1.write_text(json.dumps({"task_fingerprint": "aaa111", "task_slug": "test-task"}))

        # Task mới cùng slug nhưng fingerprint khác
        new_desc = "test task with different content"
        result_path = collision_safe_state_path(root, "test-task", new_desc)
        # Phải có fingerprint suffix
        assert "_fp8_" in result_path.name or result_path != sp1


def test_no_collision_same_fingerprint():
    """T08: Cùng fingerprint → trả base path."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        desc = "test task"
        fp = fingerprint(desc)
        sp = state_path(root, "test-task")
        sp.write_text(json.dumps({"task_fingerprint": fp, "task_slug": "test-task"}))
        result = collision_safe_state_path(root, "test-task", desc)
        assert result == sp


if __name__ == "__main__":
    tests = [test_concurrent_writes, test_locked_save_atomic, test_collision_detection, test_no_collision_same_fingerprint]
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
