"""Unit tests cho dag_schema.py — T01: Shared DAG Schema + Migration."""
import json
import sys
from pathlib import Path

# Thêm scripts dir vào path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))

from dag_schema import validate_workflow, migrate_old_schema, normalize_workflow, SCHEMA_VERSION


def test_new_schema_valid():
    """Workflow JSON với tasks, edges, schema_version:1 → valid=True."""
    workflow = {
        "workflow_id": "test-wf",
        "schema_version": 1,
        "tasks": [
            {"id": "T1", "goal": "task 1", "dependencies": []},
            {"id": "T2", "goal": "task 2", "dependencies": ["T1"]},
        ],
        "edges": [{"from": "T1", "to": "T2"}],
    }
    valid, reason = validate_workflow(workflow)
    assert valid, f"Expected valid=True, got reason: {reason}"
    assert reason == ""


def test_old_schema_migration():
    """Workflow JSON cũ với nodes, edges → migrate_old_schema converts nodes→tasks."""
    old_workflow = {
        "workflow_id": "test-old",
        "nodes": [
            {"task_id": "T1", "description": "task 1", "deps": [], "file": "foo.py", "function": "bar"},
            {"task_id": "T2", "description": "task 2", "deps": ["T1"]},
        ],
        "edges": [{"from": "T1", "to": "T2"}],
    }
    migrated = migrate_old_schema(old_workflow)
    assert "tasks" in migrated
    assert "nodes" not in migrated
    assert migrated["schema_version"] == SCHEMA_VERSION
    assert len(migrated["tasks"]) == 2
    assert migrated["tasks"][0]["id"] == "T1"
    assert migrated["tasks"][0]["goal"] == "task 1"
    assert migrated["tasks"][0]["dependencies"] == []
    assert migrated["tasks"][0]["file"] == "foo.py"
    assert migrated["tasks"][1]["id"] == "T2"
    assert migrated["tasks"][1]["dependencies"] == ["T1"]


def test_strict_validation_reject_both():
    """JSON có cả tasks và nodes → valid=False, reason contains 'cannot have both'."""
    confused = {
        "workflow_id": "confused",
        "tasks": [{"id": "T1", "goal": "x", "dependencies": []}],
        "nodes": [{"task_id": "T1", "description": "x", "deps": []}],
        "edges": [],
    }
    valid, reason = validate_workflow(confused)
    assert not valid, "Expected valid=False for both tasks and nodes"
    assert "cannot have both" in reason


def test_normalize_workflow_old_schema():
    """normalize_workflow: old schema → migrated + validated."""
    old = {
        "workflow_id": "old",
        "nodes": [{"task_id": "T1", "description": "do something", "deps": []}],
        "edges": [],
    }
    normalized, error = normalize_workflow(old)
    assert normalized is not None, f"Expected normalized, got error: {error}"
    assert error == ""
    assert "tasks" in normalized
    assert "nodes" not in normalized
    assert normalized["schema_version"] == SCHEMA_VERSION


def test_normalize_workflow_new_schema():
    """normalize_workflow: new schema → unchanged + schema_version added."""
    new = {
        "workflow_id": "new",
        "tasks": [{"id": "T1", "goal": "do", "dependencies": []}],
        "edges": [],
    }
    normalized, error = normalize_workflow(new)
    assert normalized is not None
    assert error == ""
    assert normalized["schema_version"] == SCHEMA_VERSION


def test_missing_workflow_id():
    """Workflow thiếu workflow_id → invalid."""
    bad = {"tasks": [{"id": "T1", "goal": "x", "dependencies": []}]}
    valid, reason = validate_workflow(bad)
    assert not valid
    assert "workflow_id" in reason


def test_empty_workflow():
    """Workflow không có tasks hoặc nodes → invalid."""
    bad = {"workflow_id": "empty"}
    valid, reason = validate_workflow(bad)
    assert not valid
    assert "thiếu" in reason


def test_task_missing_id():
    """Task thiếu id → invalid."""
    bad = {
        "workflow_id": "bad",
        "tasks": [{"goal": "no id", "dependencies": []}],
    }
    valid, reason = validate_workflow(bad)
    assert not valid
    assert "id" in reason


if __name__ == "__main__":
    # Chạy tất cả tests
    tests = [
        test_new_schema_valid, test_old_schema_migration,
        test_strict_validation_reject_both, test_normalize_workflow_old_schema,
        test_normalize_workflow_new_schema, test_missing_workflow_id,
        test_empty_workflow, test_task_missing_id,
    ]
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
