#!/usr/bin/env python3
"""Kiểm thử BenchJack Red-team — T4.6 (REQ-008).

Các ca kiểm thử:
1. generate_exploits trả 4 loại exploit.
2. Mỗi exploit có field đầy đủ (description, penalty, evidence).
3. exploit_type nằm trong Literal cho phép.
4. detected=False ban đầu.
5. evidence không rỗng.
6. Fixture feed vào detect_hack -> nhận diện được.
7. Deterministic: gọi 2 lần -> cùng kết quả.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from benchjack_redteam import generate_exploits  # noqa: E402
from data_models import Exploit  # noqa: E402
from reward_shaping import detect_hack  # noqa: E402

_ALLOWED_TYPES = {"padding", "metric_gaming", "shortcut", "reward_hack"}


def test_generate_exploits_returns_four_types():
    exploits = generate_exploits()
    assert len(exploits) == 4
    types = {e.exploit_type for e in exploits}
    assert types == _ALLOWED_TYPES


def test_exploits_are_pydantic_models():
    exploits = generate_exploits()
    for e in exploits:
        assert isinstance(e, Exploit)


def test_exploits_have_required_fields():
    exploits = generate_exploits()
    for e in exploits:
        assert e.description
        assert e.evidence
        assert -100.0 <= e.penalty <= 100.0
        assert e.detected is False


def test_exploit_types_in_literal():
    exploits = generate_exploits()
    for e in exploits:
        assert e.exploit_type in _ALLOWED_TYPES


def test_deterministic_generation():
    e1 = generate_exploits()
    e2 = generate_exploits()
    assert [e.model_dump() for e in e1] == [e.model_dump() for e in e2]


def test_fixture_feed_detected_by_detect_hack():
    """Mỗi fixture evidence phải chứa pattern mà detect_hack nhận diện."""
    fixtures = generate_exploits()
    for fx in fixtures:
        trace = [{"text": fx.evidence}]
        detected = detect_hack(trace)
        assert any(d.exploit_type == fx.exploit_type for d in detected), (
            f"fixture {fx.exploit_type} không bị detect_hack nhận diện"
        )


def test_all_fixtures_in_one_trace_detected():
    fixtures = generate_exploits()
    trace = [{"text": e.evidence} for e in fixtures]
    detected = detect_hack(trace)
    detected_types = {d.exploit_type for d in detected}
    assert detected_types == _ALLOWED_TYPES
