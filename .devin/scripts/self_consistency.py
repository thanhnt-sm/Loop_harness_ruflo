#!/usr/bin/env python3
"""Self-Consistency Voting Layer (C2/C3) — for discrete-answer tasks.

Implements:
- C2: Self-consistency / majority vote (Wang 2022: +5-15% over single CoT)
- C3: Ranked voting / self-certainty (RankedVotingSC 2505.10772: beats best-of-N, good for 3B-8B)

Usage: For tasks with discrete answers (test pass/fail, boolean, multiple choice),
run N chains (N>=10, T≈0.5-0.7), take majority vote.
For open-ended tasks (code, docs), use C1 + C5 instead.
"""
from __future__ import annotations

import json
import os
import sys
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Callable


def _repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        return Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else Path.cwd()
    except Exception:
        return Path.cwd()


def _run_chain(task_fn: Callable, *args, temperature: float = 0.7, **kwargs) -> Any:
    """Run a single chain with given temperature."""
    # Set temperature via environment for the executor
    old_temp = os.environ.get("AHD_TEMPERATURE")
    os.environ["AHD_TEMPERATURE"] = str(temperature)
    try:
        return task_fn(*args, **kwargs)
    finally:
        if old_temp is not None:
            os.environ["AHD_TEMPERATURE"] = old_temp
        else:
            os.environ.pop("AHD_TEMPERATURE", None)


def majority_vote(results: list[Any], key_fn: Callable[[Any], str] = str) -> tuple[Any, float]:
    """C2: Majority vote on discrete answers.
    
    Returns: (winning_result, confidence_pct)
    """
    if not results:
        return None, 0.0
    
    # Extract comparable keys
    keys = [key_fn(r) for r in results]
    counts = Counter(keys)
    winner_key, winner_count = counts.most_common(1)[0]
    confidence = winner_count / len(results) * 100
    
    # Return the first result with the winning key
    for r in results:
        if key_fn(r) == winner_key:
            return r, confidence
    
    return results[0], confidence


def ranked_voting(results: list[Any], rank_fn: Callable[[Any], float], key_fn: Callable[[Any], str] = str) -> tuple[Any, float]:
    """C3: Ranked voting / self-certainty.
    
    Each result gets a confidence score from rank_fn. Weight votes by confidence.
    Better for cases where model can self-assess certainty.
    
    Returns: (winning_result, weighted_confidence)
    """
    if not results:
        return None, 0.0
    
    # Group by answer key, sum confidence scores
    key_scores = {}
    key_results = {}
    for r in results:
        key = key_fn(r)
        score = rank_fn(r)
        key_scores[key] = key_scores.get(key, 0) + score
        if key not in key_results:
            key_results[key] = r
    
    # Winner is key with highest total confidence
    winner_key = max(key_scores, key=key_scores.get)
    total_score = sum(key_scores.values())
    winner_score = key_scores[winner_key]
    weighted_confidence = (winner_score / total_score * 100) if total_score > 0 else 0
    
    return key_results[winner_key], weighted_confidence


def self_consistency_task(
    task_fn: Callable,
    n_chains: int = 10,
    temperature: float = 0.7,
    voting_method: str = "majority",  # "majority" (C2) or "ranked" (C3)
    key_fn: Callable[[Any], str] = str,
    rank_fn: Callable[[Any], float] = lambda r: 1.0,
    *args, **kwargs
) -> dict:
    """Run self-consistency voting for a discrete-answer task.
    
    Args:
        task_fn: Function to run (should return discrete answer)
        n_chains: Number of chains to run (>=10 recommended)
        temperature: Sampling temperature (0.5-0.7)
        voting_method: "majority" (C2) or "ranked" (C3)
        key_fn: Extract comparable key from result
        rank_fn: Extract confidence score from result (for C3)
    
    Returns:
        {
            "winner": result,
            "confidence": float,
            "method": "majority|ranked",
            "chains": n_chains,
            "all_results": list,
            "vote_distribution": dict
        }
    """
    if n_chains < 3:
        raise ValueError("n_chains must be >= 3 for voting")
    
    results = []
    for i in range(n_chains):
        result = _run_chain(task_fn, *args, temperature=temperature, **kwargs)
        results.append(result)
    
    # Get vote distribution
    keys = [key_fn(r) for r in results]
    vote_dist = dict(Counter(keys))
    
    if voting_method == "ranked":
        winner, confidence = ranked_voting(results, rank_fn, key_fn)
    else:
        winner, confidence = majority_vote(results, key_fn)
    
    return {
        "winner": winner,
        "confidence": confidence,
        "method": voting_method,
        "chains": n_chains,
        "temperature": temperature,
        "all_results": results,
        "vote_distribution": vote_dist,
    }


# Example usage for discrete-answer tasks:
def example_usage():
    """Example: Test pass/fail verification via voting."""
    
    def run_test() -> dict:
        """Run test and return pass/fail."""
        result = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "tests/test_cli_entrypoints.py", "-q", "--tb=no"],
            capture_output=True, text=True, cwd="/workspace"
        )
        return {
            "passed": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout[-500:] if result.stdout else ""
        }
    
    # Run self-consistency
    result = self_consistency_task(
        run_test,
        n_chains=5,  # Reduced for demo
        temperature=0.3,
        voting_method="majority",
        key_fn=lambda r: "PASS" if r["passed"] else "FAIL"
    )
    
    print(f"Winner: {result['winner']}")
    print(f"Confidence: {result['confidence']:.1f}%")
    print(f"Distribution: {result['vote_distribution']}")
    return result


if __name__ == "__main__":
    import os
    example_usage()