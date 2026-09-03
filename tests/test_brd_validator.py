"""Tests cho brd_validator.py — parse markdown BRD thành BRD object."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from brd_validator import parse_brd_file, parse_brd_text  # noqa: E402


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "brd_sample.md"


def test_parse_sample_fixture():
    brd = parse_brd_file(FIXTURE)
    assert brd.title == "Sample BRD for tests"
    assert brd.version == "1.0.0"
    assert brd.owner == "test-fixture"
    assert len(brd.actors) == 3
    actor_names = {a.name for a in brd.actors}
    assert actor_names == {"customer", "admin", "support"}


def test_parse_fr_001():
    brd = parse_brd_file(FIXTURE)
    fr1 = next(f for f in brd.functional_requirements if f.id == "FR-001")
    assert fr1.actor == "customer"
    assert fr1.use_case == "register"
    assert fr1.priority == "must"
    assert len(fr1.acceptance_criteria) == 3
    assert "Email hợp lệ" in fr1.acceptance_criteria[0]


def test_parse_fr_002():
    brd = parse_brd_file(FIXTURE)
    fr2 = next(f for f in brd.functional_requirements if f.id == "FR-002")
    assert fr2.actor == "admin"
    assert fr2.priority == "should"


def test_parse_nfrs():
    brd = parse_brd_file(FIXTURE)
    nfr1 = next(n for n in brd.non_functional_requirements if n.id == "NFR-001")
    assert nfr1.type == "perf"
    assert nfr1.metric == "response_time_p95"
    nfr2 = next(n for n in brd.non_functional_requirements if n.id == "NFR-002")
    assert nfr2.type == "security"
    assert "bcrypt" in nfr2.threshold


def test_parse_missing_title():
    with pytest.raises(ValueError, match="tiêu đề"):
        parse_brd_text("Some random text without proper BRD header")


def test_parse_missing_version():
    bad = """# BRD — Test

> **Owner**: x

## 1. Business Goal
Long enough business goal description here.

## 2. Actors

| Actor | Role | Permissions |
|-------|------|-------------|
| `a` | x | read |
"""
    with pytest.raises(ValueError, match="Version"):
        parse_brd_text(bad)


def test_parse_fr_missing_field():
    bad = """# BRD — Test

> **Version**: `1.0.0`
> **Owner**: x

## 1. Business Goal
Long enough business goal description here.

## 2. Actors

| Actor | Role | Permissions |
|-------|------|-------------|
| `a` | x | read |

## 3. Functional Requirements (FR)

### FR-001: Test
- **Actor**: a
- **Use case**: y
- **Description**: long enough description
- **Priority**: must
"""
    # Thiếu Acceptance criteria
    with pytest.raises(ValueError, match="FR-001"):
        parse_brd_text(bad)


def test_parse_fr_references_unknown_actor():
    bad = """# BRD — Test

> **Version**: `1.0.0`
> **Owner**: x

## 1. Business Goal
Long enough business goal description here.

## 2. Actors

| Actor | Role | Permissions |
|-------|------|-------------|
| `a` | x | read |

## 3. Functional Requirements (FR)

### FR-001: Test
- **Actor**: ghost
- **Use case**: y
- **Description**: long enough description
- **Priority**: must
- **Acceptance criteria**:
  - [ ] criterion one
"""
    with pytest.raises(Exception) as exc_info:
        parse_brd_text(bad)
    # Pydantic wrap ValueError message
    assert "reference actor" in str(exc_info.value) or "ghost" in str(exc_info.value)
