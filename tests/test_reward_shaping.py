#!/usr/bin/env python3
"""Kiểm thử Reward Shaping — T4.5 + T4.6 (REQ-008).

Các ca kiểm thử:
1. shape: cost trong budget -> không penalty.
2. shape: cost vượt budget -> penalty tỷ lệ.
3. shape: security event error -> penalty.
4. shape: action success -> bonus.
5. shape: clamp score trong [-100, 100].
6. detect_hack: phát hiện padding/shortcut/metric_gaming/reward_hack.
7. detect_hack: BenchJack fixture feed -> detect được tất cả.
8. detect_hack: trace sạch -> không phát hiện.
9. Đầu vào không hợp lệ raise lỗi.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from reward_shaping import detect_hack, shape  # noqa: E402
from benchjack_redteam import generate_exploits  # noqa: E402


def test_shape_no_penalty_within_budget():
    score = shape(50.0, [{"status": "success"}], cost=5.0, security_events=[])
    # cost 5 < budget 10 -> không penalty; 1 action success -> +1 bonus
    assert score == 51.0


def test_shape_cost_over_budget_penalty():
    # cost 15 > budget 10 -> penalty (15-10)*2 = 10
    score = shape(50.0, [], cost=15.0, security_events=[])
    assert score == 40.0


def test_shape_security_event_penalty():
    score = shape(
        50.0,
        [],
        cost=0.0,
        security_events=[{"type": "violation", "severity": "error"}],
    )
    # error penalty = 20
    assert score == 30.0


def test_shape_quality_bonus_capped():
    # 15 action success -> bonus capped at 10
    actions = [{"status": "success"} for _ in range(15)]
    score = shape(50.0, actions, cost=0.0, security_events=[])
    assert score == 60.0


def test_shape_clamp_to_range():
    # base 100 + penalty lớn -> clamp về -100
    score = shape(
        100.0,
        [],
        cost=1000.0,
        security_events=[{"severity": "critical"}, {"severity": "critical"}],
    )
    assert score == -100.0


def test_shape_invalid_inputs():
    with pytest.raises(ValueError):
        shape(150.0, [], 0.0, [])  # base ngoài range
    with pytest.raises(ValueError):
        shape(50.0, [], -1.0, [])  # cost âm
    with pytest.raises(TypeError):
        shape(50.0, "not list", 0.0, [])  # type: ignore[arg-type]


def test_detect_hack_padding():
    trace = [{"output": "a" * 100}]
    exploits = detect_hack(trace)
    types = [e.exploit_type for e in exploits]
    assert "padding" in types
    assert all(e.detected for e in exploits)


def test_detect_hack_shortcut():
    trace = [{"command": "skip test verification"}]
    exploits = detect_hack(trace)
    types = [e.exploit_type for e in exploits]
    assert "shortcut" in types


def test_detect_hack_metric_gaming():
    trace = [{"text": "hardcoded result = 'PASS'"}]
    exploits = detect_hack(trace)
    types = [e.exploit_type for e in exploits]
    assert "metric_gaming" in types


def test_detect_hack_reward_hack():
    trace = [{"action": "set score = 100 (high)"}]
    exploits = detect_hack(trace)
    types = [e.exploit_type for e in exploits]
    assert "reward_hack" in types


def test_detect_hack_clean_trace():
    trace = [{"status": "success"}, {"output": "normal output text"}]
    exploits = detect_hack(trace)
    assert exploits == []


def test_benchjack_feed_detected_by_detect_hack():
    """BenchJack fixture -> detect_hack nhận diện tất cả 4 loại."""
    fixtures = generate_exploits()
    assert len(fixtures) == 4
    # Mỗi fixture có evidence chứa pattern -> detect_hack phải nhận diện
    trace = [{"text": e.evidence} for e in fixtures]
    exploits = detect_hack(trace)
    detected_types = {e.exploit_type for e in exploits}
    assert detected_types == {"padding", "metric_gaming", "shortcut", "reward_hack"}


def test_benchjack_fixtures_have_correct_types():
    fixtures = generate_exploits()
    types = [e.exploit_type for e in fixtures]
    assert "padding" in types
    assert "metric_gaming" in types
    assert "shortcut" in types
    assert "reward_hack" in types
    # detected=False ban đầu (chưa qua detect_hack)
    assert all(not e.detected for e in fixtures)


def test_detect_hack_invalid_input():
    with pytest.raises(TypeError):
        detect_hack("not list")  # type: ignore[arg-type]
