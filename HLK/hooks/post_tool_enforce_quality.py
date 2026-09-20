"""Enforcement hooks U57-U59: auto quality check, done-detection, skill router.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import ahd_session

from post_tool_config import (HOOK_TIMEOUT_SECONDS, MAX_ITERATIONS_WITHOUT_STATE_WRITE, MIN_COMPRESSION_THRESHOLD, MAX_OUTPUT_SIZE_COMPRESSION, DEFAULT_COMPRESSION_THRESHOLD, MAX_FAILURE_THRESHOLD, _CONTEXT_FLAGS_CACHE, _CONTEXT_FLAGS_LOADED, _STATE_WRITE_COUNTER, _STATE_WRITE_BATCH, CONTEXT_OVERSIZE_THRESHOLD, CANDIDATE_MEMORY_MAX, VALID_CORRECT_ACTIONS, CANDIDATE_MEMORY_PER_HOUR, CANDIDATE_MEMORY_WINDOW_SECONDS, _SECRET_PATTERNS)

def _u57_auto_quality_checks(data: dict, session_id: str, root: Path) -> None:
    """Auto-run quality checks on Write/Edit tools. Non-blocking warnings."""
    tool_name = data.get("tool_name", "").lower()
    if tool_name not in ("write", "edit", "notebook_edit"):
        return

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    content = tool_input.get("content", tool_input.get("new_string", ""))

    if not content:
        return

    # U57: Slop detection — check for common AI slop patterns
    slop_score = 0
    slop_patterns = [
        (r"\b(leveraging|utilizing|facilitating|comprehensive|seamless)\b", "AI slop word", 2),
        (r"\b(it['']s worth noting that|it should be noted that)\b", "filler phrase", 1),
        (r"\b(delve into|dive deep into|explore in detail)\b", "verbose phrase", 1),
        (r"\b(robust|scalable|enterprise-grade|production-ready)\b", "buzzword", 1),
    ]
    for pattern, label, weight in slop_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        slop_score += len(matches) * weight

    # U57: Comment quality — check for AI-generated comments
    comment_issues = 0
    comment_patterns = [
        (r"#\s*(TODO|FIXME|HACK|XXX)", "stale comment marker", 2),
        (r"//\s*(TODO|FIXME|HACK|XXX)", "stale comment marker", 2),
        (r"#\s*Step \d+:", "numbered step comment", 1),
        (r"//\s*Step \d+:", "numbered step comment", 1),
    ]
    for pattern, label, weight in comment_patterns:
        matches = re.findall(pattern, content)
        comment_issues += len(matches) * weight

    # Write scores to session_state
    if slop_score > 0 or comment_issues > 0:
        state_path = ahd_session.get_session_state_path(session_id, root)
        ahd_session._locked_json_update(
            state_path,
            lambda existing: {
                **(existing or {}),
                "quality_scores": {
                    **((existing or {}).get("quality_scores", {})),
                    str(file_path): {
                        "slop_score": slop_score,
                        "comment_issues": comment_issues,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
            },
            default={},
            session_id=session_id,
        )
        if slop_score >= DEFAULT_COMPRESSION_THRESHOLD:
            print(
                f"[U57] WARNING: High slop score ({slop_score}) in {file_path}. "
                f"Review for AI slop patterns.",
                file=sys.stderr,
            )
        if comment_issues >= 5:
            print(
                f"[U57] WARNING: Comment issues ({comment_issues}) in {file_path}. "
                f"Review comment quality.",
                file=sys.stderr,
            )

def _u58_done_detection(data: dict, session_id: str, root: Path) -> None:
    """Detect 'done' declarations in tool output, flag for fable-judge."""
    tool_response = data.get("tool_response", {})
    output = ""
    if isinstance(tool_response, dict):
        output = str(tool_response.get("output", tool_response.get("content", "")))
    elif isinstance(tool_response, str):
        output = tool_response

    done_patterns = [
        r"\b(done|complete|completed|finished|finalized|all (tests|checks) pass)\b",
    ]
    done_detected = False
    for pattern in done_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            done_detected = True
            break

    if done_detected:
        state_path = ahd_session.get_session_state_path(session_id, root)
        ahd_session._locked_json_update(
            state_path,
            lambda existing: {
                **(existing or {}),
                "done_declared": True,
                "done_declared_at": datetime.now(timezone.utc).isoformat(),
                "fable_judge_required": True,
            },
            default={},
            session_id=session_id,
        )
        print(
            "[U58] Done declaration detected. fable-judge verification required "
            "before task complete.",
            file=sys.stderr,
        )

def _u59_skill_auto_router(data: dict, session_id: str, root: Path) -> None:
    """Auto-suggest skills based on tool type and output."""
    tool_name = data.get("tool_name", "").lower()
    suggestions = []

    # Map tools to skills
    skill_map = {
        "write": ["harness-sensor", "slop-detector", "comment_checker"],
        "edit": ["harness-sensor", "slop-detector", "comment_checker"],
        "notebook_edit": ["harness-sensor"],
        "exec": ["harness-sensor"],
        "read": [],
        "grep": [],
        "glob": [],
    }

    suggestions = skill_map.get(tool_name, [])
    if not suggestions:
        return

    state_path = ahd_session.get_session_state_path(session_id, root)
    ahd_session._locked_json_update(
        state_path,
        lambda existing: {
            **(existing or {}),
            "skill_suggestions": suggestions,
            "skill_suggested_at": datetime.now(timezone.utc).isoformat(),
        },
        default={},
        session_id=session_id,
    )
