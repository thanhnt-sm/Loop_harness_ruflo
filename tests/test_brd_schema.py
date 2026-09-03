"""Tests cho brd_schema.py — Pydantic models cho BRD."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from brd_schema import Actor, BRD, FunctionalRequirement, NonFunctionalRequirement  # noqa: E402


def test_actor_valid():
    a = Actor(name="customer", role="End user", permissions=["read"])
    assert a.name == "customer"
    assert "read" in a.permissions


def test_actor_name_no_whitespace():
    with pytest.raises(ValidationError):
        Actor(name="bad name", role="X")


def test_actor_permission_default():
    a = Actor(name="x", role="X")
    assert a.permissions == ["read"]


def test_fr_pattern_required():
    with pytest.raises(ValidationError):
        FunctionalRequirement(
            id="WRONG-001", actor="x", use_case="y", description="long enough desc",
            priority="must", acceptance_criteria=["ok"]
        )


def test_fr_needs_acceptance_criteria():
    with pytest.raises(ValidationError):
        FunctionalRequirement(
            id="FR-001", actor="x", use_case="y", description="long enough desc",
            priority="must", acceptance_criteria=[]
        )


def test_fr_criterion_too_short():
    with pytest.raises(ValidationError):
        FunctionalRequirement(
            id="FR-001", actor="x", use_case="y", description="long enough desc",
            priority="must", acceptance_criteria=["x"]
        )


def test_nfr_metric_must_be_measurable():
    with pytest.raises(ValidationError):
        NonFunctionalRequirement(id="NFR-001", type="perf", metric="fast", threshold="< 1s")


def test_nfr_metric_ok_with_unit():
    n = NonFunctionalRequirement(id="NFR-001", type="perf", metric="response_time_p95", threshold="< 200ms")
    assert n.id == "NFR-001"


def test_brd_actor_must_exist_for_fr():
    # Pydantic v2 wrap message: "Value error, BRD reference actor ..."  → match 'reference actor'
    with pytest.raises(ValidationError) as exc_info:
        BRD(
            title="Valid Title", business_goal="long enough business goal here",
            version="1.0.0", owner="me",
            actors=[Actor(name="customer", role="x")],
            functional_requirements=[
                FunctionalRequirement(
                    id="FR-001", actor="admin",  # admin không tồn tại
                    use_case="y", description="long enough desc",
                    priority="must", acceptance_criteria=["ok criterion"]
                )
            ]
        )
    assert "reference actor" in str(exc_info.value)


def test_brd_duplicate_fr_ids():
    with pytest.raises(ValidationError) as exc_info:
        BRD(
            title="Valid Title", business_goal="long enough business goal here",
            version="1.0.0", owner="me",
            actors=[Actor(name="a", role="x")],
            functional_requirements=[
                FunctionalRequirement(
                    id="FR-001", actor="a", use_case="y", description="long enough desc",
                    priority="must", acceptance_criteria=["ok criterion"]
                ),
                FunctionalRequirement(
                    id="FR-001", actor="a", use_case="z", description="another desc",
                    priority="should", acceptance_criteria=["another criterion"]
                ),
            ]
        )
    assert "trùng lặp" in str(exc_info.value)


def test_brd_full_valid():
    brd = BRD(
        title="Sample", business_goal="Validate full BRD structure here",
        version="1.0.0", owner="tester",
        actors=[Actor(name="customer", role="end user", permissions=["read", "write"])],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="customer", use_case="register",
                description="User tạo tài khoản mới", priority="must",
                acceptance_criteria=["Email hợp lệ", "Password ≥ 8 ký tự"]
            )
        ],
        non_functional_requirements=[
            NonFunctionalRequirement(id="NFR-001", type="perf", metric="response_time_p95", threshold="< 200ms")
        ]
    )
    assert brd.title == "Sample"
    assert len(brd.functional_requirements) == 1
    assert len(brd.non_functional_requirements) == 1
