"""Tests for Trajectory Evaluation (V3)."""

from __future__ import annotations

import pytest

from trajectory_eval import (
    TrajectoryStep,
    AgentTrajectory,
    trajectory_strict_match,
    trajectory_llm_judge,
    trajectory_semantic_similarity,
    compare_trajectories,
    trajectory_to_dict,
    trajectory_from_dict,
    _sequence_similarity,
)


class TestTrajectoryStep:
    """Test TrajectoryStep dataclass."""

    def test_step_creation(self):
        step = TrajectoryStep(
            step_index=0,
            tool="Read",
            args={"path": "file.txt"},
            result_summary="Content of file.txt",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert step.tool == "Read"
        assert step.args == {"path": "file.txt"}


class TestAgentTrajectory:
    """Test AgentTrajectory dataclass."""

    def test_trajectory_creation(self):
        steps = [
            TrajectoryStep(0, "Read", {"path": "a.py"}, "content of a.py", "ts1"),
            TrajectoryStep(1, "Write", {"path": "b.py", "content": "x"}, "ok", "ts2"),
        ]
        traj = AgentTrajectory(
            task_id="test-1",
            agent_version="test-agent",
            steps=steps,
            final_answer="Done",
            success=True,
        )
        assert len(traj.steps) == 2
        assert traj.success is True


class TestStrictMatch:
    """Test strict trajectory matching."""

    def _make_traj(self, steps_data):
        steps = [TrajectoryStep(i, s["tool"], s["args"], s["result"], f"ts{i}") for i, s in enumerate(steps_data)]
        return AgentTrajectory("task", "agent", steps, "answer", True)

    def test_exact_match(self):
        steps = [
            {"tool": "Read", "args": {"path": "a.py"}, "result": "content"},
            {"tool": "Write", "args": {"path": "b.py", "content": "x"}, "result": "ok"},
        ]
        traj1 = self._make_traj(steps)
        traj2 = self._make_traj(steps)

        match, reason = trajectory_strict_match(traj1, traj2)
        assert match is True
        assert reason == "Exact match"

    def test_step_count_mismatch(self):
        traj1 = self._make_traj([{"tool": "Read", "args": {}, "result": ""}])
        traj2 = self._make_traj([
            {"tool": "Read", "args": {}, "result": ""},
            {"tool": "Write", "args": {}, "result": ""},
        ])
        match, reason = trajectory_strict_match(traj1, traj2)
        assert match is False
        assert "Step count mismatch" in reason

    def test_tool_mismatch(self):
        traj1 = self._make_traj([{"tool": "Read", "args": {}, "result": ""}])
        traj2 = self._make_traj([{"tool": "Write", "args": {}, "result": ""}])
        match, reason = trajectory_strict_match(traj1, traj2)
        assert match is False
        assert "tool mismatch" in reason

    def test_args_mismatch(self):
        traj1 = self._make_traj([{"tool": "Read", "args": {"path": "a.py"}, "result": ""}])
        traj2 = self._make_traj([{"tool": "Read", "args": {"path": "b.py"}, "result": ""}])
        match, reason = trajectory_strict_match(traj1, traj2)
        assert match is False
        assert "args mismatch" in reason

    def test_result_mismatch(self):
        traj1 = self._make_traj([{"tool": "Read", "args": {}, "result": "content A"}])
        traj2 = self._make_traj([{"tool": "Read", "args": {}, "result": "content B"}])
        match, reason = trajectory_strict_match(traj1, traj2)
        assert match is False
        assert "result mismatch" in reason

    def test_final_answer_mismatch(self):
        traj1 = AgentTrajectory("t", "a", [], "answer 1", True)
        traj2 = AgentTrajectory("t", "a", [], "answer 2", True)
        match, reason = trajectory_strict_match(traj1, traj2)
        assert match is False
        assert "Final answer mismatch" in reason


class TestLLMJudge:
    """Test LLM-as-judge trajectory comparison."""

    def test_exact_match_returns_tie(self):
        traj = AgentTrajectory(
            task_id="t", agent_version="a",
            steps=[TrajectoryStep(0, "Read", {"p": "x"}, "content", "ts")],
            final_answer="done", success=True,
        )
        result = trajectory_llm_judge(traj, traj)
        assert result["preference"] == "tie"
        assert result["confidence"] == 1.0

    def test_structural_similarity(self):
        traj1 = AgentTrajectory(
            task_id="t", agent_version="a",
            steps=[
                TrajectoryStep(0, "Read", {"p": "a.py"}, "content A", "ts1"),
                TrajectoryStep(1, "Write", {"p": "b.py", "c": "x"}, "ok", "ts2"),
            ],
            final_answer="done", success=True,
        )
        traj2 = AgentTrajectory(
            task_id="t", agent_version="b",
            steps=[
                TrajectoryStep(0, "Read", {"p": "a.py"}, "content A", "ts1"),
                TrajectoryStep(1, "Write", {"p": "b.py", "c": "y"}, "ok", "ts2"),
            ],
            final_answer="done", success=True,
        )
        result = trajectory_llm_judge(traj1, traj2)
        assert "preference" in result
        assert "confidence" in result
        assert "position_swap_consistent" in result


class TestSemanticSimilarity:
    """Test semantic trajectory similarity."""

    def test_identical_paths(self):
        traj = AgentTrajectory("t", "a", [], "ans", True)
        sim = trajectory_semantic_similarity(traj, traj)
        assert sim == 1.0

    def test_no_overlap(self):
        traj1 = AgentTrajectory("t", "a", [
            TrajectoryStep(0, "Read", {"p": "a.py"}, "content", "ts"),
        ], "ans", True)
        traj2 = AgentTrajectory("t", "a", [
            TrajectoryStep(0, "Write", {"p": "b.py", "c": "x"}, "ok", "ts"),
        ], "ans", True)
        sim = trajectory_semantic_similarity(traj1, traj2)
        # No word overlap in tools
        assert sim >= 0.0


class TestSequenceSimilarity:
    """Test sequence similarity computation."""

    def test_identical_sequences(self):
        seq = ["Read", "Write", "Read"]
        sim = _sequence_similarity(seq, seq)
        assert sim == 1.0

    def test_no_common(self):
        sim = _sequence_similarity(["Read", "Write"], ["Delete", "Edit"])
        assert sim == 0.0

    def test_partial_overlap(self):
        sim = _sequence_similarity(["Read", "Write", "Edit"], ["Read", "Edit", "Write"])
        # LCS is "Read", "Write" or "Read", "Edit" = 2, max len = 3
        assert sim == 2 / 3

    def test_empty_sequences(self):
        assert _sequence_similarity([], []) == 1.0
        assert _sequence_similarity([], ["Read"]) == 0.0


class TestSerialization:
    """Test trajectory serialization."""

    def test_roundtrip(self):
        traj = AgentTrajectory(
            task_id="test",
            agent_version="v1",
            steps=[
                TrajectoryStep(0, "Read", {"path": "x.py"}, "content", "ts"),
                TrajectoryStep(1, "Write", {"path": "y.py", "content": "x"}, "ok", "ts"),
            ],
            final_answer="Done",
            success=True,
            metadata={"tokens": 100, "cost": 0.001},
        )

        data = trajectory_to_dict(traj)
        restored = trajectory_from_dict(data)

        assert restored.task_id == traj.task_id
        assert restored.agent_version == traj.agent_version
        assert len(restored.steps) == 2
        assert restored.final_answer == traj.final_answer
        assert restored.success == traj.success
        assert restored.metadata == traj.metadata


class TestCompareTrajectories:
    """Test compare_trajectories function."""

    def test_strict_mode(self):
        traj1 = AgentTrajectory("t", "a", [
            TrajectoryStep(0, "Read", {"p": "x"}, "c", "ts"),
        ], "ans", True)
        traj2 = AgentTrajectory("t", "a", [
            TrajectoryStep(0, "Read", {"p": "x"}, "c", "ts"),
        ], "ans", True)

        result = compare_trajectories(traj1, traj2, "strict")
        assert result["match"] is True
        assert result["mode"] == "strict"

    def test_semantic_mode(self):
        traj1 = AgentTrajectory("t", "a", [], "ans", True)
        traj2 = AgentTrajectory("t", "a", [], "ans", True)

        result = compare_trajectories(traj1, traj2, "semantic")
        assert "similarity" in result
        assert result["mode"] == "semantic"

    def test_invalid_mode(self):
        traj1 = AgentTrajectory("t", "a", [], "ans", True)
        traj2 = AgentTrajectory("t", "a", [], "ans", True)

        with pytest.raises(ValueError, match="Unknown mode"):
            compare_trajectories(traj1, traj2, "invalid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])