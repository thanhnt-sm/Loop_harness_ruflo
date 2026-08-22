#!/usr/bin/env python3
"""T5.2: Kiểm thử dag_compile.py — parse plan, build DAG, topo sort, validate.

Bao phủ:
- parse_plan: trích task từ markdown.
- build_dag: tạo nodes + edges.
- topological_sort: acyclic + cycle detection.
- validate_dag: dependency tồn tại, orphan, cycle.
- compile_plan: end-to-end, ghi workflow JSON.
- main: CLI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import dag_compile  # noqa: E402


_PLAN_MD = """# Plan

## Task T1: Setup project
- File: src/main.py
- Function: main
- Deps: none
- Acceptance: runs without error

## Task T2: Add utils
- File: src/utils.py
- Function: helper
- Deps: T1
- Acceptance: helper returns 42

## Task T3: Add tests
- File: tests/test_utils.py
- Function: test_helper
- Deps: T2
- Acceptance: all tests pass
"""


def test_parse_plan_extracts_tasks():
    tasks = dag_compile.parse_plan(_PLAN_MD)
    assert len(tasks) == 3
    assert tasks[0]["task_id"] == "T1"
    assert tasks[0]["description"] == "Setup project"
    assert tasks[0]["file"] == "src/main.py"
    assert tasks[0]["function"] == "main"
    assert tasks[0]["deps"] == []
    assert tasks[0]["acceptance_criteria"] == "runs without error"
    assert tasks[1]["deps"] == ["T1"]
    assert tasks[2]["deps"] == ["T2"]


def test_parse_plan_empty_returns_empty():
    assert dag_compile.parse_plan("# No tasks") == []
    assert dag_compile.parse_plan("") == []


def test_parse_plan_deps_none():
    md = "## Task X: do thing\n- Deps: none\n"
    tasks = dag_compile.parse_plan(md)
    assert tasks[0]["deps"] == []


def test_parse_plan_deps_na_and_dash():
    for val in ("N/A", "-"):
        md = f"## Task X: do thing\n- Deps: {val}\n"
        tasks = dag_compile.parse_plan(md)
        assert tasks[0]["deps"] == []


def test_parse_plan_multiple_deps():
    md = "## Task X: do thing\n- Deps: T1, T2; T3\n"
    tasks = dag_compile.parse_plan(md)
    assert tasks[0]["deps"] == ["T1", "T2", "T3"]


def test_build_dag():
    tasks = dag_compile.parse_plan(_PLAN_MD)
    nodes, edges = dag_compile.build_dag(tasks)
    assert len(nodes) == 3
    # V1 schema: nodes có key 'id' (không phải 'task_id')
    assert all("id" in n for n in nodes)
    # 2 edges: T1->T2, T2->T3
    assert len(edges) == 2
    assert {"from": "T1", "to": "T2"} in edges
    assert {"from": "T2", "to": "T3"} in edges


def test_topological_sort_acyclic():
    tasks = dag_compile.parse_plan(_PLAN_MD)
    nodes, edges = dag_compile.build_dag(tasks)
    sorted_ids, cycle = dag_compile.topological_sort(nodes, edges)
    assert cycle == []
    assert len(sorted_ids) == 3
    # T1 phải trước T2, T2 trước T3
    assert sorted_ids.index("T1") < sorted_ids.index("T2")
    assert sorted_ids.index("T2") < sorted_ids.index("T3")


def test_topological_sort_cycle_detected():
    nodes = [
        {"id": "A", "dependencies": ["B"]},
        {"id": "B", "dependencies": ["A"]},
    ]
    edges = [{"from": "B", "to": "A"}, {"from": "A", "to": "B"}]
    sorted_ids, cycle = dag_compile.topological_sort(nodes, edges)
    assert cycle  # có chu trình
    assert set(cycle) == {"A", "B"}


def test_validate_dag_valid():
    tasks = dag_compile.parse_plan(_PLAN_MD)
    nodes, edges = dag_compile.build_dag(tasks)
    valid, errors = dag_compile.validate_dag(nodes, edges)
    assert valid is True
    assert errors == []


def test_validate_dag_missing_dependency():
    nodes = [{"id": "T1", "dependencies": ["MISSING"]}]
    edges = [{"from": "MISSING", "to": "T1"}]
    valid, errors = dag_compile.validate_dag(nodes, edges)
    assert valid is False
    assert any("khong ton tai" in e for e in errors)


def test_validate_dag_cycle():
    nodes = [
        {"id": "A", "dependencies": ["B"]},
        {"id": "B", "dependencies": ["A"]},
    ]
    edges = [{"from": "B", "to": "A"}, {"from": "A", "to": "B"}]
    valid, errors = dag_compile.validate_dag(nodes, edges)
    assert valid is False
    assert any("chu trinh" in e for e in errors)


def test_validate_dag_orphan():
    nodes = [
        {"id": "A", "dependencies": []},
        {"id": "B", "dependencies": []},
    ]
    edges = []
    valid, errors = dag_compile.validate_dag(nodes, edges)
    # 2 node không liên kết -> orphan
    assert valid is False
    assert any("orphan" in e for e in errors)


def test_validate_dag_single_node_no_orphan():
    nodes = [{"id": "A", "dependencies": []}]
    edges = []
    valid, errors = dag_compile.validate_dag(nodes, edges)
    # 1 node thì không coi là orphan
    assert valid is True


def test_compile_plan_writes_workflow(tmp_path):
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(_PLAN_MD, encoding="utf-8")
    output = tmp_path / "workflow.json"
    code = dag_compile.compile_plan(tmp_path, plan_file, output)
    assert code == 0
    assert output.exists()
    wf = json.loads(output.read_text(encoding="utf-8"))
    assert wf["workflow_id"] == "plan"
    assert len(wf["tasks"]) == 3
    assert len(wf["edges"]) == 2
    assert "compiled_at" in wf


def test_compile_plan_default_output_path(tmp_path):
    plan_file = tmp_path / "myplan.md"
    plan_file.write_text(_PLAN_MD, encoding="utf-8")
    code = dag_compile.compile_plan(tmp_path, plan_file, None)
    assert code == 0
    default_output = tmp_path / ".devin" / "plan_state" / "myplan_workflow.json"
    assert default_output.exists()


def test_compile_plan_missing_file(tmp_path):
    code = dag_compile.compile_plan(tmp_path, tmp_path / "nope.md", None)
    assert code == 1


def test_compile_plan_no_tasks(tmp_path):
    plan_file = tmp_path / "empty.md"
    plan_file.write_text("# No tasks here", encoding="utf-8")
    code = dag_compile.compile_plan(tmp_path, plan_file, None)
    assert code == 1


def test_compile_plan_invalid_dag(tmp_path):
    plan_file = tmp_path / "cyclic.md"
    plan_file.write_text(
        "## Task A: a\n- Deps: B\n\n## Task B: b\n- Deps: A\n",
        encoding="utf-8",
    )
    code = dag_compile.compile_plan(tmp_path, plan_file, None)
    assert code == 1


def test_main_writes_workflow(tmp_path, monkeypatch):
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(_PLAN_MD, encoding="utf-8")
    output = tmp_path / "out.json"
    code = dag_compile.main.__wrapped__() if hasattr(dag_compile.main, "__wrapped__") else None
    # Gọi main qua sys.argv
    monkeypatch.setattr(sys, "argv", [
        "dag_compile.py", str(plan_file), "--output", str(output), "--root", str(tmp_path),
    ])
    code = dag_compile.main()
    assert code == 0
    assert output.exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
