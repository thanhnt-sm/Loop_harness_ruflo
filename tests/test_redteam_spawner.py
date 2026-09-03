"""Tests cho redteam_spawner.py — auto-spawn expert agents + aggregate."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from redteam_spawner import (  # noqa: E402
    aggregate_verdicts,
    build_redteam_round,
)


def test_build_redteam_low_confidence_triggers():
    """Confidence thấp → trả về RedteamRound, không phải None."""
    round_spec = build_redteam_round(
        primary_verdict="PASS",
        primary_confidence=0.4,
        task="Validate FR-001",
    )
    assert round_spec is not None
    assert round_spec.primary_confidence == 0.4
    assert len(round_spec.calls) == 3  # personas_per_round=3


def test_build_redteam_high_confidence_no_trigger():
    """Confidence cao → trả về None."""
    round_spec = build_redteam_round(
        primary_verdict="PASS",
        primary_confidence=0.9,
        task="Validate FR-001",
    )
    assert round_spec is None


def test_build_redteam_call_spec():
    """Mỗi AgentCall có persona, model, task_prompt."""
    round_spec = build_redteam_round(
        primary_verdict="FAIL",
        primary_confidence=0.3,
        task="Check security",
        context="NFR-002 password storage",
    )
    assert round_spec is not None
    for call in round_spec.calls:
        assert call.persona.startswith("persona-")
        assert call.model in ("haiku", "sonnet", "opus", None)
        assert "Check security" in call.task_prompt
        assert "NFR-002" in call.task_prompt
        assert call.rationale_required is True


def test_aggregate_unanimous_override():
    """3/3 agree → unanimous_override → final = majority, không escalate."""
    result = aggregate_verdicts(["PASS", "PASS", "PASS"], primary_verdict="FAIL")
    assert result.final_verdict == "PASS"
    assert result.agreement_score == 1.0
    assert result.escalate_human is False
    assert result.block is False
    assert result.aggregation_method == "unanimous_override"


def test_aggregate_majority_escalate():
    """2/3 agree → majority_escalate → escalate_human=True, block=False."""
    result = aggregate_verdicts(["PASS", "PASS", "FAIL"], primary_verdict="FAIL")
    assert result.final_verdict == "PASS"
    assert result.agreement_score == 2 / 3
    assert result.escalate_human is True
    assert result.block is False
    assert result.aggregation_method == "majority_escalate"


def test_aggregate_no_consensus_block():
    """3 verdicts khác nhau → no_consensus_block → REVIEW, block=True."""
    result = aggregate_verdicts(["PASS", "FAIL", "REVIEW"], primary_verdict="PASS")
    assert result.final_verdict == "REVIEW"
    assert result.escalate_human is True
    assert result.block is True
    assert result.aggregation_method == "no_consensus_block"


def test_aggregate_empty_verdicts():
    """Không có verdict nào → escalate + block."""
    result = aggregate_verdicts([], primary_verdict="PASS")
    assert result.escalate_human is True
    assert result.block is True
    assert result.aggregation_method == "no_data"
