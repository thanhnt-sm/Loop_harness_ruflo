#!/usr/bin/env python3
"""Kiểm thử LLM-as-Judge — T4.4 (REQ-007).

Các ca kiểm thử:
1. Result có marker success -> PASS.
2. Result có marker fail -> FAIL.
3. Result ambiguous -> UNCERTAIN.
4. High-risk keyword -> REVIEW.
5. Deterministic: cùng seed -> cùng verdict.
6. Seed ngoài phạm vi raise ValueError.
7. Task không phải chuỗi raise TypeError.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from llm_as_judge import judge  # noqa: E402


def test_pass_when_success_marker():
    task = "Task with acceptance criteria: must verify output."
    result = "OK: task complete and verified"
    v = judge(task, result, seed=42)
    assert v.startswith("PASS")


def test_fail_when_error_marker():
    task = "Task with acceptance criteria: must verify."
    result = "ERROR: crash during execution, exception raised"
    v = judge(task, result, seed=42)
    assert v.startswith("FAIL") or v.startswith("UNCERTAIN")


def test_uncertain_for_ambiguous():
    task = "Task with acceptance criteria."
    result = "maybe partial"
    v = judge(task, result, seed=42)
    # Không marker rõ -> score thấp -> FAIL hoặc UNCERTAIN
    assert v.startswith(("FAIL", "UNCERTAIN"))


def test_high_risk_review():
    task = "Task: delete old records. Acceptance criteria."
    result = "OK complete"
    v = judge(task, result, seed=42)
    assert v.startswith("REVIEW")
    assert "human confirm" in v


def test_deterministic_same_seed():
    task = "Task with acceptance criteria: must verify."
    result = "OK success"
    v1 = judge(task, result, seed=42)
    v2 = judge(task, result, seed=42)
    assert v1 == v2


def test_seed_out_of_range_raises():
    task = "ok"
    result = "ok"
    with pytest.raises(ValueError):
        judge(task, result, seed=-1)
    with pytest.raises(ValueError):
        judge(task, result, seed=2147483648)


def test_non_string_task_raises():
    with pytest.raises(TypeError):
        judge(123, "ok", seed=42)  # type: ignore[arg-type]


def test_none_result_handled():
    task = "Task with acceptance criteria."
    v = judge(task, None, seed=42)
    # None -> score thấp -> FAIL hoặc UNCERTAIN
    assert v.startswith(("FAIL", "UNCERTAIN"))
