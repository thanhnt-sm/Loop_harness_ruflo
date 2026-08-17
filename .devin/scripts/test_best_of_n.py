#!/usr/bin/env python3
"""Test best-of-n functionality."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, "/workspace/.devin/scripts")

from best_of_n import best_of_n, best_of_n_with_verification, _verify_code_quality

# Test 1: Code quality scoring
print("=== Test 1: Code Quality Scoring ===")
good_code = '''def add(a, b):
    """Add two numbers."""
    return a + b
'''
bad_code = '''def add(a, b):
    # leveraging comprehensive seamless addition
    return a + b
'''
good_score = _verify_code_quality(good_code, Path("/workspace"))
bad_score = _verify_code_quality(bad_code, Path("/workspace"))
print(f"Good code score: {good_score}")
print(f"Bad code score: {bad_score}")
assert good_score > bad_score, "Good code should score higher"

# Test 2: Best-of-N selection
print("\n=== Test 2: Best-of-N Selection ===")
import random

def mock_generator():
    implementations = [
        'def add(a, b):\n    """Add two numbers."""\n    return a + b\n',
        'def add(a, b):\n    return a + b\n',
        'def add(a, b):\n    # This function adds two numbers together\n    result = a + b\n    return result\n',
        'def add(a, b):\n    """Add two numbers.\\n\\n    Args:\\n        a: first number\\n        b: second number\\n\\n    Returns:\\n        sum of a and b\\n    """\\n    return a + b\n',
        'def add(a, b):\n    # leveraging comprehensive seamless addition\\n    return a + b\n',
    ]
    return random.choice(implementations)

result = best_of_n(
    mock_generator,
    n=10,
    reward_fn=lambda c: _verify_code_quality(c, Path("/workspace"))
)
print(f"Best score: {result['best_score']:.1f}")
print(f"Best index: {result['best_index']}")
print(f"All scores: {result['all_scores']}")
assert result['best_score'] >= 90, "Should find high-quality code"

# Test 3: Best-of-N with verification
print("\n=== Test 3: Best-of-N with Verification ===")
def mock_generator_with_bug():
    implementations = [
        'def add(a, b):\n    return a - b\n',  # bug
        'def add(a, b):\n    return a + b\n',  # correct
        'def add(a, b):\n    return a * b\n',  # bug
    ]
    return random.choice(implementations)

def verify_correct(code: str) -> bool:
    """Check if code correctly implements addition."""
    return "return a + b" in code and "return a - b" not in code and "return a * b" not in code

result = best_of_n_with_verification(
    mock_generator_with_bug,
    n=10,
    verification_fn=verify_correct
)
print(f"Passed: {result['passed']}")
print(f"Attempts: {result['attempts']}")
print(f"Best code: {result['best'][:50]}...")

print("\n=== All Tests Passed ===")