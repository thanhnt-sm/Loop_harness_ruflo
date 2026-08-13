#!/usr/bin/env python3
"""Kiểm thử coverage_enforce.py — plan coverage tracking hook (R-05)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import coverage_enforce  # noqa: E402


def _run_hook(stdin_payload, cwd):
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "hooks" / "coverage_enforce.py")]
    return subprocess.run(
        cmd,
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _plan_file(tmp_path, content):
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    p = tmp_path / "docs" / "plans" / "IMPLEMENTATION_PLAN.md"
    p.write_text(content, encoding="utf-8")
    return p


# --- _parse_plan ---

def test_parse_plan_task_lines(tmp_path):
    plan = _plan_file(tmp_path, """
- [ ] T01: src/foo.py (functions: bar, baz)
- [x] T02: scripts/util.py (functions: run)
## T03 — src/qux.py (functions: quux)
""")
    parsed = coverage_enforce._parse_plan(plan)
    assert parsed["plan_name"] == "IMPLEMENTATION_PLAN"
    tasks = parsed["tasks"]
    assert tasks["T01"]["file"] == "src/foo.py"
    assert tasks["T01"]["symbols"] == ["bar", "baz"]
    assert tasks["T01"]["status"] == "planned"
    assert tasks["T02"]["status"] == "executed"
    assert tasks["T03"]["file"] == "src/qux.py"


def test_parse_plan_missing_file(tmp_path):
    parsed = coverage_enforce._parse_plan(tmp_path / "nope.md")
    assert parsed["tasks"] == {}


# --- coverage helpers ---

def test_compute_coverage_empty():
    pct, executed, total = coverage_enforce._compute_coverage({"tasks": {}})
    assert (pct, executed, total) == (0.0, 0, 0)


def test_compute_coverage_mixed():
    state = {"tasks": {
        "T01": {"status": "planned"},
        "T02": {"status": "executed"},
        "T03": {"status": "verified"},
    }}
    pct, executed, total = coverage_enforce._compute_coverage(state)
    assert executed == 2
    assert total == 3
    assert pct == round(200 / 3, 2)


def test_compute_gaps():
    state = {"tasks": {
        "T01": {"status": "planned"},
        "T02": {"status": "executed"},
    }}
    assert coverage_enforce._compute_gaps(state) == ["T01"]


def test_normalize_path_strips_only_dot_slash():
    assert coverage_enforce._normalize_path("./src/foo.py") == "src/foo.py"
    assert coverage_enforce._normalize_path("..hidden") == "..hidden"


def test_grep_symbol_in_file_found(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("def target():\n    pass\n", encoding="utf-8")
    assert coverage_enforce._grep_symbol_in_file(f, "target") is True


def test_grep_symbol_in_file_missing(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("def other():\n    pass\n", encoding="utf-8")
    assert coverage_enforce._grep_symbol_in_file(f, "target") is False


# --- _update_coverage ---

def test_update_coverage_marks_executed_and_verified(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    f = src / "foo.py"
    f.write_text("def bar():\n    pass\n", encoding="utf-8")

    plan = {"plan_name": "P", "tasks": {
        "T01": {"file": "src/foo.py", "function": "bar", "symbols": ["bar"], "status": "planned"},
    }}
    state = {"plan_name": "P", "tasks": {}}
    updated = coverage_enforce._update_coverage(state, plan, "src/foo.py", tmp_path)
    assert updated["tasks"]["T01"]["status"] == "verified"
    assert updated["tasks"]["T01"]["last_edited"] == "src/foo.py"


def test_update_coverage_planned_when_symbol_missing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "foo.py").write_text("def other():\n    pass\n", encoding="utf-8")

    plan = {"plan_name": "P", "tasks": {
        "T01": {"file": "src/foo.py", "function": "bar", "symbols": ["bar"], "status": "planned"},
    }}
    state = {"plan_name": "P", "tasks": {}}
    updated = coverage_enforce._update_coverage(state, plan, "src/foo.py", tmp_path)
    assert updated["tasks"]["T01"]["status"] == "executed"


# --- main (end-to-end via subprocess) ---

def test_main_no_plan_file_skips(tmp_path):
    res = _run_hook(
        {"tool_name": "Write", "tool_input": {"file_path": "x.py"}},
        cwd=tmp_path,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout)["total"] == 0


def test_main_invalid_json_skips(tmp_path):
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "hooks" / "coverage_enforce.py")]
    res = subprocess.run(cmd, input="not json", capture_output=True, text=True, cwd=tmp_path)
    assert res.returncode == 0
    assert json.loads(res.stdout)["total"] == 0


def test_main_non_write_tool_tracks_but_does_not_edit(tmp_path):
    _plan_file(tmp_path, "- [ ] T01: src/foo.py (functions: bar)\n")
    # Write vào file không khớp task -> plan tasks được merge vào state, nhưng
    # task T01 vẫn planned (file edit không match task_file).
    res = _run_hook(
        {"tool_name": "Write", "tool_input": {"file_path": "unrelated.py"}},
        cwd=tmp_path,
    )
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["total"] == 1
    assert out["executed"] == 0
    assert out["gaps"] == ["T01"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
