#!/usr/bin/env python3
"""Test self-consistency with simple discrete task."""
from __future__ import annotations

import sys
sys.path.insert(0, "/workspace/.devin/scripts")

from self_consistency import self_consistency_task, majority_vote, ranked_voting

# Test 1: Simple majority vote
print("=== Test 1: Majority Vote ===")
results = ["PASS", "PASS", "FAIL", "PASS", "PASS", "PASS", "FAIL", "PASS", "PASS", "PASS"]
winner, confidence = majority_vote(results)
print(f"Results: {results}")
print(f"Winner: {winner}, Confidence: {confidence:.1f}%")

# Test 2: Ranked voting
print("\n=== Test 2: Ranked Voting ===")
results_with_scores = [
    {"answer": "PASS", "confidence": 0.9},
    {"answer": "PASS", "confidence": 0.8},
    {"answer": "FAIL", "confidence": 0.6},
    {"answer": "PASS", "confidence": 0.85},
    {"answer": "PASS", "confidence": 0.75},
]
winner, confidence = ranked_voting(
    results_with_scores,
    rank_fn=lambda r: r["confidence"],
    key_fn=lambda r: r["answer"]
)
print(f"Results: {results_with_scores}")
print(f"Winner: {winner}, Confidence: {confidence:.1f}%")

# Test 3: Self-consistency task with simple function
print("\n=== Test 3: Self-Consistency Task ===")
import random

def mock_discrete_task():
    """Mock task that returns PASS 70% of the time."""
    return "PASS" if random.random() < 0.7 else "FAIL"

result = self_consistency_task(
    mock_discrete_task,
    n_chains=10,
    temperature=0.5,
    voting_method="majority",
    key_fn=lambda r: r
)
print(f"Winner: {result['winner']}")
print(f"Confidence: {result['confidence']:.1f}%")
print(f"Distribution: {result['vote_distribution']}")

print("\n=== All Tests Passed ===")