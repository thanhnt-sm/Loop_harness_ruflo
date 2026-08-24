#!/usr/bin/env python3
"""plan_dispatch_nuwa.py — Nuwa cognitive angle suggestions.

Module for suggesting which Nuwa cognitive angles to apply to each subtask
based on the task goal and file scope.
"""

from __future__ import annotations

# Nuwa's 3 cognitive angles (from Docs/Agents/nuwa.md)
NUWA_ANGLES = {
    "edge-case": {
        "name": "Edge Case Breaker",
        "question": "What input, state, or condition would break this?",
        "mindset": "adversarial",
    },
    "dependency": {
        "name": "Dependency Inspector",
        "question": "What else depends on what I'm changing, and will it break?",
        "mindset": "structural",
    },
    "regression": {
        "name": "Regression Prophet",
        "question": "What previously-working behavior will this change break?",
        "mindset": "historical",
    },
}


def _suggest_nuwa_angles(st: dict) -> list[str]:
    """Suggest which Nuwa cognitive angles to apply to this subtask.

    Heuristics:
    - If the subtask touches >2 files -> dependency angle (check blast radius)
    - If the subtask goal mentions "fix", "bug", "error", "edge" -> edge-case angle
    - If the subtask goal mentions "refactor", "change", "update", "modify" -> regression angle
    - Default: all 3 angles (full Nuwa)
    """
    goal = st.get("goal", "").lower()
    files = st.get("_expanded_files", [])

    angles = []

    if any(kw in goal for kw in ["fix", "bug", "error", "edge", "crash", "fail"]):
        angles.append("edge-case")

    if len(files) > 2 or any(kw in goal for kw in ["refactor", "change", "update", "modify", "rename"]):
        angles.append("dependency")
        angles.append("regression")

    if not angles:
        angles = ["edge-case", "dependency", "regression"]

    return list(dict.fromkeys(angles))  # dedupe, preserve order