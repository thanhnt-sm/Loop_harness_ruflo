#!/usr/bin/env python3
"""Kiểm thử parser trích file_path và function từ task raw trong plan."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / ".devin" / "scripts"))

from plan_quality_check import _extract_file_path, _extract_function
from coverage_matrix import _extract_file_path as cm_extract_file_path
from coverage_matrix import _extract_function as cm_extract_function


def test_extract_file_path_from_field():
    raw = "Update dispatch logic. file: .devin/scripts/plan_dispatch.py func: main() AC: pass"
    assert _extract_file_path(raw) == ".devin/scripts/plan_dispatch.py"
    assert cm_extract_file_path(raw) == ".devin/scripts/plan_dispatch.py"


def test_extract_file_path_ignores_goal_path():
    raw = "Update event_bus.py logic. file: .devin/scripts/event_bus.py func: publish()"
    assert _extract_file_path(raw) == ".devin/scripts/event_bus.py"
    assert cm_extract_file_path(raw) == ".devin/scripts/event_bus.py"


def test_extract_file_path_with_backticks():
    raw = "Refactor. file: `src/core/adapter.py` func: parse()"
    assert _extract_file_path(raw) == "src/core/adapter.py"
    assert cm_extract_file_path(raw) == "src/core/adapter.py"


def test_extract_file_path_fallback():
    raw = "Update plan_quality_check.py parser"
    assert _extract_file_path(raw) == "plan_quality_check.py"
    assert cm_extract_file_path(raw) == "plan_quality_check.py"


def test_extract_file_path_missing():
    raw = "Do something with no file"
    assert _extract_file_path(raw) == ""
    assert cm_extract_file_path(raw) == ""


def test_extract_function_with_parens():
    raw = "file: a.py func: main() AC: pass"
    assert _extract_function(raw) == "main"
    assert cm_extract_function(raw) == "main"


def test_extract_function_without_parens():
    raw = "file: a.py func: my_helper AC: pass"
    assert _extract_function(raw) == "my_helper"
    assert cm_extract_function(raw) == "my_helper"


def test_extract_function_with_function_keyword():
    raw = "file: a.py function: parseData()"
    assert _extract_function(raw) == "parseData"
    assert cm_extract_function(raw) == "parseData"


def test_extract_function_missing():
    raw = "file: a.py AC: pass"
    assert _extract_function(raw) == ""
    assert cm_extract_function(raw) == ""


def test_parse_full_task_line():
    from plan_quality_check import _parse_tasks
    from coverage_matrix import _parse_tasks as cm_parse_tasks

    text = """
## Tasks

- **T1**: Update event bus publisher. file: .devin/scripts/event_bus.py func: publish() AC: works R1
- **T2**: Update blackboard writer. file: .devin/scripts/blackboard.py func: write() R2
"""
    tasks = _parse_tasks(text)
    cm_tasks = cm_parse_tasks(text)

    assert tasks[0]["id"] == "T1"
    assert tasks[0]["file_path"] == ".devin/scripts/event_bus.py"
    assert tasks[0]["function"] == "publish"

    assert tasks[1]["id"] == "T2"
    assert tasks[1]["file_path"] == ".devin/scripts/blackboard.py"
    assert tasks[1]["function"] == "write"

    assert cm_tasks[0]["file_path"] == ".devin/scripts/event_bus.py"
    assert cm_tasks[0]["function"] == "publish"
    assert cm_tasks[1]["file_path"] == ".devin/scripts/blackboard.py"
    assert cm_tasks[1]["function"] == "write"
