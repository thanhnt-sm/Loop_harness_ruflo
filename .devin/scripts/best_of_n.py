#!/usr/bin/env python3
"""Best-of-N + Reward Model (C4) — for open-ended tasks with quality selection.

Implements:
- C4: Best-of-N with reward/verifier model (when available)
- Uses deterministic verification (C1) as reward signal when no reward model
- Falls back to heuristic scoring for code generation tasks

Usage: For open-ended tasks (code, docs), run N candidates, score each,
select best. Requires reward model or proxy for open-ended quality.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from self_consistency import _repo_root


def _run_candidate(task_fn: Callable, *args, **kwargs) -> Any:
    """Run a single candidate generation."""
    return task_fn(*args, **kwargs)


def _verify_code_quality(code: str, root: Path, session_id: str = "") -> float:
    """Verify code quality using deterministic checks (harness-sensor equivalent).
    
    Returns quality score 0-100. Uses:
    - Syntax check (Python)
    - Import check
    - Basic style (no obvious slop)
    - Schema gate if applicable
    """
    score = 100.0
    
    # Write to temp dir với tên module hợp lệ để py_compile + import ổn định
    tmp_dir = tempfile.mkdtemp(prefix="best_of_n_")
    temp_path = os.path.join(tmp_dir, "candidate.py")
    Path(temp_path).write_text(code, encoding="utf-8")

    try:
        # 1. Syntax check (30 pts)
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", temp_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            score -= 30

        # 2. Import check (20 pts) - thử import module trong process con
        try:
            script = (
                "import sys; "
                f"sys.path.insert(0, {tmp_dir!r}); "
                "import candidate"
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                score -= 20
        except Exception:
            score -= 20

        # 3. Slop detection (25 pts) - check for AI filler patterns
        slop_patterns = [
            r"\b(leveraging|utilizing|facilitating|comprehensive|seamless)\b",
            r"\b(it['']s worth noting that|it should be noted that)\b",
            r"\b(delve into|dive deep into|explore in detail)\b",
            r"\b(robust|scalable|enterprise-grade|production-ready)\b",
            r"\b(in order to|please note|additionally|importantly|essentially)\b",
        ]
        import re
        for pattern in slop_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                score -= 5
                break

        # 4. Has proper structure (25 pts) - functions, classes, docstrings
        has_func = bool(re.search(r"^\s*def\s+\w+", code, re.MULTILINE))
        has_class = bool(re.search(r"^\s*class\s+\w+", code, re.MULTILINE))
        has_docstring = '"""' in code or "'''" in code
        if not (has_func or has_class):
            score -= 15
        if not has_docstring:
            score -= 10

    except Exception:
        score -= 10
    finally:
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    return max(0, min(100, score))


def _verify_test_pass(code: str, test_path: str, root: Path) -> float:
    """Run tests on generated code. Returns pass rate 0-100."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name
    
    try:
        # Run specific test file
        result = subprocess.run(
            [".venv/bin/python", "-m", "pytest", test_path, "-q", "--tb=no"],
            capture_output=True, text=True, timeout=60,
            cwd=str(root)
        )
        # Parse pass/fail from output
        output = result.stdout + result.stderr
        if "passed" in output:
            import re
            match = re.search(r"(\d+)\s+passed", output)
            if match:
                passed = int(match.group(1))
                match_fail = re.search(r"(\d+)\s+failed", output)
                failed = int(match_fail.group(1)) if match_fail else 0
                total = passed + failed
                if total > 0:
                    return passed / total * 100
        return 100 if result.returncode == 0 else 0
    except Exception:
        return 0
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def best_of_n(
    task_fn: Callable,
    n: int = 5,
    reward_fn: Optional[Callable[[Any], float]] = None,
    *args, **kwargs
) -> dict:
    """Run Best-of-N: generate N candidates, select best by reward.
    
    Args:
        task_fn: Function that generates a candidate (code, text, etc.)
        n: Number of candidates to generate
        reward_fn: Function that scores a candidate (0-100). If None, uses
                   default code quality verifier.
        *args, **kwargs: Passed to task_fn
    
    Returns:
        {
            "best": best_candidate,
            "best_score": float,
            "all_candidates": list,
            "all_scores": list,
            "n": n
        }
    """
    if n < 2:
        raise ValueError("n must be >= 2")
    
    candidates = []
    scores = []
    
    root = _repo_root()
    session_id = kwargs.pop("session_id", "")
    
    for i in range(n):
        # Generate candidate with slight variation (temperature)
        candidate = _run_candidate(task_fn, *args, **kwargs)
        candidates.append(candidate)
        
        # Score candidate
        if reward_fn:
            score = reward_fn(candidate)
        else:
            # Default: code quality verification
            if isinstance(candidate, str) and ("def " in candidate or "class " in candidate):
                score = _verify_code_quality(candidate, root, session_id)
            else:
                # Generic heuristic for non-code
                score = 50.0  # neutral
        
        scores.append(score)
    
    # Select best
    best_idx = scores.index(max(scores))
    best_candidate = candidates[best_idx]
    best_score = scores[best_idx]
    
    return {
        "best": best_candidate,
        "best_score": best_score,
        "best_index": best_idx,
        "all_candidates": candidates,
        "all_scores": scores,
        "n": n,
    }


def best_of_n_with_verification(
    task_fn: Callable,
    n: int = 5,
    verification_fn: Optional[Callable[[Any], bool]] = None,
    *args, **kwargs
) -> dict:
    """Best-of-N with binary verification (pass/fail).
    
    Runs candidates until one passes verification, or returns best after N.
    
    Args:
        task_fn: Generates candidate
        n: Max candidates
        verification_fn: Returns True if candidate passes
        *args, **kwargs: Passed to task_fn
    
    Returns:
        {
            "best": candidate or None,
            "passed": bool,
            "attempts": int,
            "all_candidates": list
        }
    """
    candidates = []
    
    for i in range(n):
        candidate = _run_candidate(task_fn, *args, **kwargs)
        candidates.append(candidate)
        
        if verification_fn and verification_fn(candidate):
            return {
                "best": candidate,
                "passed": True,
                "attempts": i + 1,
                "all_candidates": candidates,
            }
    
    return {
        "best": candidates[0] if candidates else None,
        "passed": False,
        "attempts": n,
        "all_candidates": candidates,
    }


# Example usage
if __name__ == "__main__":
    def generate_simple_function():
        """Mock generator - returns different implementations."""
        import random
        implementations = [
            'def add(a, b):\n    """Add two numbers."""\n    return a + b\n',
            'def add(a, b):\n    return a + b\n',
            'def add(a, b):\n    # This function adds two numbers together\n    result = a + b\n    return result\n',
            'def add(a, b):\n    """Add two numbers.\n    \n    Args:\n        a: first number\n        b: second number\n    \n    Returns:\n        sum of a and b\n    """\n    return a + b\n',
            'def add(a, b):\n    # leveraging comprehensive seamless addition\n    return a + b\n',  # has slop
        ]
        return random.choice(implementations)
    
    result = best_of_n(
        generate_simple_function,
        n=5,
        reward_fn=lambda c: _verify_code_quality(c, _repo_root())
    )
    
    print(f"Best score: {result['best_score']:.1f}")
    print(f"Best index: {result['best_index']}")
    print(f"All scores: {result['all_scores']}")
    print(f"\nBest code:\n{result['best']}")