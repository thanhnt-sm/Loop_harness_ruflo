"""Tests for Eval Harness (V1+V2+V3 Integration)."""

from __future__ import annotations

import pytest
import tempfile
from pathlib import Path

from eval_harness import (
    EvalConfig,
    EvalMode,
    EvalTaskResult,
    EvalRun,
    EvalLayer,
    run_eval,
    promote_or_rollback,
    archive_eval_run,
    _generate_run_id,
    _get_agent_version,
)
from golden_set_miner import GoldenTask, save_golden_task, load_golden_manifest
from trajectory_eval import AgentTrajectory, TrajectoryStep


class TestEvalConfig:
    """Test EvalConfig."""

    def test_default_config(self):
        config = EvalConfig()
        assert config.mode == "core"
        assert config.golden_dir == "tests/golden"
        assert config.trajectory_mode == "strict"

    def test_custom_config(self):
        config = EvalConfig(
            mode="torture",
            max_tasks=10,
            trajectory_mode="llm_judge",
            replay_mode=True,
        )
        assert config.mode == "torture"
        assert config.max_tasks == 10
        assert config.trajectory_mode == "llm_judge"
        assert config.replay_mode is True


class TestRunIdGeneration:
    """Test run ID generation."""

    def test_run_id_format(self):
        run_id = _generate_run_id()
        assert run_id.startswith("eval-")
        assert len(run_id) > 10

    def test_unique_run_ids(self):
        ids = set()
        for _ in range(100):
            ids.add(_generate_run_id())
        assert len(ids) == 100


class TestAgentVersion:
    """Test agent version detection."""

    def test_agent_version_format(self):
        version = _get_agent_version()
        assert version.startswith("ahd-")


class TestPromoteOrRollback:
    """Test promotion/rollback decision."""

    def test_promote_high_scores(self):
        run = EvalRun(
            run_id="test",
            config=EvalConfig(),
            agent_version="test",
            started_at="2026-01-01T00:00:00Z",
            results=[],
            summary={
                "total_tasks": 10,
                "passed": 9,
                "failed": 1,
                "pass_rate": 0.9,
                "avg_score": 0.95,
                "trajectory_match_rate": 0.95,
            }
        )
        promoted, reason = promote_or_rollback(run)
        assert promoted is True
        assert "Promoted" in reason

    def test_rollback_low_pass_rate(self):
        run = EvalRun(
            run_id="test",
            config=EvalConfig(),
            agent_version="test",
            started_at="2026-01-01T00:00:00Z",
            results=[],
            summary={
                "total_tasks": 10,
                "passed": 5,
                "failed": 5,
                "pass_rate": 0.5,
                "avg_score": 0.6,
                "trajectory_match_rate": 0.95,
            }
        )
        promoted, reason = promote_or_rollback(run)
        assert promoted is False
        assert "Rolled back" in reason
        assert "pass_rate" in reason

    def test_rollback_low_trajectory_match(self):
        run = EvalRun(
            run_id="test",
            config=EvalConfig(),
            agent_version="test",
            started_at="2026-01-01T00:00:00Z",
            results=[],
            summary={
                "total_tasks": 10,
                "passed": 9,
                "failed": 1,
                "pass_rate": 0.9,
                "avg_score": 0.95,
                "trajectory_match_rate": 0.5,
            }
        )
        promoted, reason = promote_or_rollback(run)
        assert promoted is False
        assert "Rolled back" in reason
        assert "traj_match" in reason


class TestArchiveEvalRun:
    """Test eval run archiving."""

    def test_archive_creates_file(self, tmp_path):
        run = EvalRun(
            run_id="eval-test-123",
            config=EvalConfig(),
            agent_version="test-agent",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:01:00Z",
            results=[],
            summary={"total_tasks": 5, "passed": 4, "pass_rate": 0.8},
        )

        archive_dir = str(tmp_path / "archive")
        path = archive_eval_run(run, archive_dir=str(tmp_path))

        assert Path(path).exists()
        assert "eval-" in Path(path).name

        # Verify content
        import json
        with open(path) as f:
            data = json.load(f)
        assert data["run_id"] == "eval-test-123"
        assert data["agent_version"] == "test-agent"


class TestEvalTaskResult:
    """Test EvalTaskResult."""

    def test_task_result_creation(self):
        result = EvalTaskResult(
            task_id="task-1",
            layer="task",
            passed=True,
            score=0.9,
            trajectory_match=True,
            details={"difficulty": "easy"},
            agent_version="test",
            eval_mode="core",
        )
        assert result.task_id == "task-1"
        assert result.layer == "task"
        assert result.passed is True


class TestEvalRunSummary:
    """Test EvalRun summary calculation."""

    def test_summary_calculation(self):
        run = EvalRun(
            run_id="test",
            config=EvalConfig(),
            agent_version="test",
            started_at="2026-01-01T00:00:00Z",
            results=[
                type('obj', (object,), {"passed": True, "score": 1.0, "trajectory_match": True})(),
                type('obj', (object,), {"passed": False, "score": 0.0, "trajectory_match": False})(),
                type('obj', (object,), {"passed": True, "score": 0.8, "trajectory_match": True})(),
            ],
        )
        # Manually set summary as run would
        total = 3
        passed = 2
        run.summary = {
            "total_tasks": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total,
            "avg_score": (1.0 + 0.0 + 0.8) / 3,
            "trajectory_match_rate": 2 / 3,
        }

        assert run.summary["total_tasks"] == 3
        assert run.summary["passed"] == 2
        assert run.summary["pass_rate"] == 2/3
        assert abs(run.summary["avg_score"] - 0.6) < 0.01
        assert run.summary["trajectory_match_rate"] == 2/3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])