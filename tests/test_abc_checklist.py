#!/usr/bin/env python3
"""Kiểm thử ABC Checklist — T4.3 (REQ-007).

Các ca kiểm thử:
1. Task hợp lệ + outcome success + trace tốt -> pass=True.
2. Task thiếu acceptance criteria -> task_valid=False -> pass=False.
3. Outcome không có marker thành công -> outcome_valid=False.
4. Process score thấp -> pass=False.
5. LLM-as-judge deterministic (cùng seed -> cùng verdict).
6. High-risk task -> judge_verdict chứa REVIEW.
7. Đầu vào không hợp lệ raise lỗi.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from abc_checklist import evaluate  # noqa: E402


def test_evaluate_pass_when_all_good():
    task = "Implement feature X. Acceptance criteria: must pass test_verify."
    result = "OK: feature X complete and verified"
    trace = [{"status": "success"}, {"status": "success"}, {"ok": True}]
    report = evaluate(task, result, trace, run_id="r1", seed=42)
    assert report.task_valid is True
    assert report.outcome_valid is True
    assert report.process_score == 1.0
    assert report.pass_ is True
    assert "PASS" in report.judge_verdict or "REVIEW" in report.judge_verdict


def test_task_missing_criteria_fails():
    task = "do something"  # quá ngắn, không có keyword
    result = "OK done"
    trace = [{"status": "success"}]
    report = evaluate(task, result, trace, seed=42)
    assert report.task_valid is False
    assert report.pass_ is False


def test_outcome_no_success_marker_fails():
    task = "Task with acceptance criteria: must verify output."
    result = "random text without markers"
    trace = [{"status": "success"}]
    report = evaluate(task, result, trace, seed=42)
    assert report.outcome_valid is False
    assert report.pass_ is False


def test_low_process_score_fails():
    task = "Task with acceptance criteria: must verify."
    result = "OK success"
    trace = [{"status": "success"}, {"status": "failed"}, {"status": "failed"}]
    report = evaluate(task, result, trace, seed=42)
    # process_score = 1/3 < 0.6
    assert report.process_score < 0.6
    assert report.pass_ is False


def test_judge_deterministic_same_seed():
    task = "Task with acceptance criteria."
    result = "OK"
    trace = [{"status": "success"}]
    r1 = evaluate(task, result, trace, seed=42)
    r2 = evaluate(task, result, trace, seed=42)
    assert r1.judge_verdict == r2.judge_verdict
    assert r1.judge_seed == 42


def test_high_risk_triggers_review():
    task = "Task: delete old data. Acceptance criteria: must verify."
    result = "OK complete"
    trace = [{"status": "success"}]
    report = evaluate(task, result, trace, seed=42)
    # High-risk keyword 'delete' -> REVIEW
    assert "REVIEW" in report.judge_verdict


def test_invalid_inputs_raise():
    with pytest.raises(TypeError):
        evaluate(123, "ok", [])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        evaluate("ok", "ok", "not list")  # type: ignore[arg-type]


def test_empty_trace_zero_score():
    task = "Task with acceptance criteria: must verify."
    result = "OK"
    report = evaluate(task, result, [], seed=42)
    assert report.process_score == 0.0
    assert report.pass_ is False
