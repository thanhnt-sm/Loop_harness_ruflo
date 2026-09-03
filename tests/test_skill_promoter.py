"""Tests cho skill_promoter.py — auto-promote pattern-fail thành skill mới."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skill_promoter import (  # noqa: E402
    FailureObservation,
    find_promotion_candidates,
    render_skill_markdown,
    write_drafts_to_queue,
)


def make_obs(pattern: str, executor: str, failed: bool) -> FailureObservation:
    return FailureObservation(pattern=pattern, executor=executor, task_id="t1", failed=failed)


def test_no_candidates_when_too_few():
    obs = [make_obs("p1", "sonnet", True)]
    candidates = find_promotion_candidates(obs, min_occurrences=3)
    assert candidates == []


def test_no_candidates_when_low_fail_rate():
    """3 obs, 1 fail → fail_rate 0.33 < 0.5 → no promote."""
    obs = [
        make_obs("p1", "sonnet", False),
        make_obs("p1", "sonnet", False),
        make_obs("p1", "sonnet", True),
    ]
    candidates = find_promotion_candidates(obs, min_fail_rate=0.5)
    assert candidates == []


def test_no_candidates_when_only_one_executor():
    """3 fails nhưng chỉ 1 executor → anti-abuse fail."""
    obs = [
        make_obs("p1", "sonnet", True),
        make_obs("p1", "sonnet", True),
        make_obs("p1", "sonnet", True),
    ]
    candidates = find_promotion_candidates(obs, min_executors=2)
    assert candidates == []


def test_promote_when_criteria_met():
    """3 obs, 3 fails, 3 executors khác nhau → promote."""
    obs = [
        make_obs("read config first", "sonnet", True),
        make_obs("read config first", "haiku", True),
        make_obs("read config first", "opus", True),
    ]
    candidates = find_promotion_candidates(obs)
    assert len(candidates) == 1
    draft = candidates[0]
    assert draft.based_on_pattern == "read config first"
    assert draft.occurrences == 3
    assert draft.fail_rate == 1.0
    assert set(draft.executors_observed) == {"sonnet", "haiku", "opus"}


def test_render_skill_markdown():
    draft = find_promotion_candidates([
        make_obs("check test env", "sonnet", True),
        make_obs("check test env", "haiku", True),
        make_obs("check test env", "opus", True),
    ])[0]
    md = render_skill_markdown(draft)
    assert "---" in md
    assert "Auto-generated" in md
    assert "check test env" in md
    assert "## Trigger" in md
    assert "## Steps" in md
    assert "## Rubric" in md


def test_write_drafts_to_queue(tmp_path):
    draft = find_promotion_candidates([
        make_obs("validate env", "sonnet", True),
        make_obs("validate env", "haiku", True),
        make_obs("validate env", "opus", True),
    ])[0]
    queue = tmp_path / "queue.jsonl"
    n = write_drafts_to_queue([draft], queue)
    assert n == 1
    lines = queue.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["based_on_pattern"] == "validate env"


def test_multiple_candidates_respect_max():
    """MAX_DRAFTS_PER_RUN=5 → nếu có 6 patterns đủ điều kiện, chỉ trả 5."""
    obs = []
    for i in range(6):
        for ex in ("sonnet", "haiku", "opus"):
            obs.append(make_obs(f"pattern-{i}", ex, True))
    candidates = find_promotion_candidates(obs)
    assert len(candidates) == 5
