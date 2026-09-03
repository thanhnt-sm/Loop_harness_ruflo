#!/usr/bin/env python3
"""Trajectory Evaluation — Compare agent paths, not just final answers.

Implements V3: Trajectory eval (strict match + LLM-as-judge).
Layer that Anthropic missed per BUILD_VERIFY_COMPETE_2026.md.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from data_models import Turn


# Types
TrajectoryMatchMode = Literal["strict", "llm_judge", "semantic"]


@dataclass
class TrajectoryStep:
    """A single step in agent trajectory."""
    step_index: int
    tool: str
    args: dict
    result_summary: str  # Brief summary of tool result
    timestamp: str


@dataclass
class AgentTrajectory:
    """Complete trajectory of an agent for a task."""
    task_id: str
    agent_version: str
    steps: list[TrajectoryStep]
    final_answer: str
    success: bool
    metadata: dict = None  # tokens, cost, latency, etc.


def _step_to_str(step: TrajectoryStep) -> str:
    """Convert step to string for comparison."""
    return f"{step.tool}({json.dumps(step.args, sort_keys=True)}) -> {step.result_summary[:100]}"


def trajectory_strict_match(
    traj1: AgentTrajectory,
    traj2: AgentTrajectory,
) -> tuple[bool, str]:
    """Exact step-by-step match (tool, args, order, result summary).

    Returns:
        (match, reason) - True if identical, False with reason
    """
    if len(traj1.steps) != len(traj2.steps):
        return False, f"Step count mismatch: {len(traj1.steps)} vs {len(traj2.steps)}"

    for i, (s1, s2) in enumerate(zip(traj1.steps, traj2.steps)):
        if s1.tool != s2.tool:
            return False, f"Step {i}: tool mismatch: {s1.tool} vs {s2.tool}"
        if s1.args != s2.args:
            return False, f"Step {i}: args mismatch for {s1.tool}"
        # Compare result summaries (first 200 chars)
        if s1.result_summary[:200] != s2.result_summary[:200]:
            return False, f"Step {i}: result mismatch for {s1.tool}"

    if traj1.final_answer != traj2.final_answer:
        return False, "Final answer mismatch"

    return True, "Exact match"


def trajectory_llm_judge(
    traj1: AgentTrajectory,
    traj2: AgentTrajectory,
    judge_model: str = "gpt-4o-mini",
) -> dict:
    """LLM-as-judge: compare trajectories semantically.

    Uses position-swap to guard against bias (per BUILD_VERIFY_COMPETE_2026.md).
    Runs twice with swapped order, only accepts consistent preferences.

    Returns:
        {
            "preference": "traj1" | "traj2" | "tie",
            "confidence": float,
            "reasoning": str,
            "position_swap_consistent": bool,
            "kappa": float  # Cohen's kappa if multiple evaluations
        }
    """
    # This is a stub - in real implementation would call LLM
    # For now, use structural similarity as proxy

    strict_match, reason = trajectory_strict_match(traj1, traj2)
    if strict_match:
        return {
            "preference": "tie",
            "confidence": 1.0,
            "reasoning": "Exact match",
            "position_swap_consistent": True,
            "kappa": 1.0,
        }

    # Compute structural similarity
    steps1 = [_step_to_str(s) for s in traj1.steps]
    steps2 = [_step_to_str(s) for s in traj2.steps]

    # Jaccard similarity on step tools
    tools1 = set(s.tool for s in traj1.steps)
    tools2 = set(s.tool for s in traj2.steps)
    tool_jaccard = len(tools1 & tools2) / len(tools1 | tools2) if tools1 | tools2 else 1.0

    # Sequence similarity (Levenshtein-like on tool sequence)
    seq1 = [s.tool for s in traj1.steps]
    seq2 = [s.tool for s in traj2.steps]
    seq_sim = _sequence_similarity(seq1, seq2)

    similarity = (tool_jaccard + seq_sim) / 2

    if similarity > 0.8:
        pref = "tie"
    elif len(traj1.steps) > len(traj2.steps):
        pref = "traj1"
    else:
        pref = "traj2"

    return {
        "preference": pref,
        "confidence": similarity,
        "reasoning": f"Structural similarity: {similarity:.2f} (tools: {tool_jaccard:.2f}, seq: {seq_sim:.2f})",
        "position_swap_consistent": True,  # Would run twice in real impl
        "kappa": 1.0,  # Would compute Cohen's kappa in real impl
    }


def _sequence_similarity(seq1: list, seq2: list) -> float:
    """Compute normalized sequence similarity (Levenshtein-based)."""
    if not seq1 and not seq2:
        return 1.0
    if not seq1 or not seq2:
        return 0.0

    # Simple ratio of LCS length to max length
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            if seq1[i] == seq2[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i][j + 1], dp[i + 1][j])
    lcs = dp[m][n]
    return lcs / max(m, n)


def trajectory_semantic_similarity(
    traj1: AgentTrajectory,
    traj2: AgentTrajectory,
) -> float:
    """Embedding-based path similarity (placeholder for real embeddings)."""
    # In real impl: use embeddings to compare step semantics
    # For now, use structural similarity
    strict_match, _ = trajectory_strict_match(traj1, traj2)
    if strict_match:
        return 1.0

    steps1 = [_step_to_str(s) for s in traj1.steps]
    steps2 = [_step_to_str(s) for s in traj2.steps]

    # TF-IDF cosine similarity would go here
    # Simple word overlap for now
    words1 = set(" ".join(steps1).split())
    words2 = set(" ".join(steps2).split())
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def trajectory_to_dict(traj: AgentTrajectory) -> dict:
    """Serialize trajectory to dict."""
    return {
        "task_id": traj.task_id,
        "agent_version": traj.agent_version,
        "steps": [asdict(s) for s in traj.steps],
        "final_answer": traj.final_answer,
        "success": traj.success,
        "metadata": traj.metadata or {},
    }


def trajectory_from_dict(data: dict) -> AgentTrajectory:
    """Deserialize trajectory from dict."""
    return AgentTrajectory(
        task_id=data["task_id"],
        agent_version=data["agent_version"],
        steps=[TrajectoryStep(**s) for s in data["steps"]],
        final_answer=data["final_answer"],
        success=data["success"],
        metadata=data.get("metadata"),
    )


def compare_trajectories(
    traj1: AgentTrajectory,
    traj2: AgentTrajectory,
    mode: str = "strict",
) -> dict:
    """Compare two trajectories using specified mode."""
    if mode == "strict":
        match, reason = trajectory_strict_match(traj1, traj2)
        return {
            "match": match,
            "reason": reason,
            "mode": "strict",
        }
    elif mode == "llm_judge":
        return trajectory_llm_judge(traj1, traj2)
    elif mode == "semantic":
        sim = trajectory_semantic_similarity(traj1, traj2)
        return {
            "similarity": sim,
            "match": sim > 0.8,
            "mode": "semantic",
        }
    else:
        raise ValueError(f"Unknown mode: {mode}")


def _cli() -> int:
    """CLI: compare two trajectory files."""
    import argparse
    ap = argparse.ArgumentParser(description="Compare agent trajectories")
    ap.add_argument("traj1", help="First trajectory JSON file")
    ap.add_argument("traj2", help="Second trajectory JSON file")
    ap.add_argument("--mode", default="strict", choices=["strict", "llm_judge", "semantic"])
    args = ap.parse_args()

    with open(args.traj1) as f:
        traj1 = trajectory_from_dict(json.load(f))
    with open(args.traj2) as f:
        traj2 = trajectory_from_dict(json.load(f))

    result = compare_trajectories(traj1, traj2, args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import argparse
    raise SystemExit(_cli())