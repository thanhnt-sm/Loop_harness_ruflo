#!/usr/bin/env python3
"""Mission/persona generators cho SCOUTs, reviewers, và writer."""
from __future__ import annotations

from .constants import NUM_REVIEWERS, NUM_SCOUTS


def scout_missions(task_description: str) -> list[dict]:
    """Tạo work orders cho 5 SCOUT subagents.

    Mỗi scout độc lập, chạy song song, tập trung vào một khía cạnh của task.
    """
    return [
        {
            "id": "SCOUT-1",
            "mission": (
                f"Scan codebase structure for task: '{task_description}'. "
                "Map directory tree, module boundaries, entry points, build system. "
                "Output: structure map + dependency graph."
            ),
            "tools": ["grep", "glob", "read"],
        },
        {
            "id": "SCOUT-2",
            "mission": (
                f"Find relevant files + dependencies for: '{task_description}'. "
                "Trace call paths, locate interfaces, identify blast radius. "
                "Output: file list with relevance rationale."
            ),
            "tools": ["grep", "glob", "read"],
        },
        {
            "id": "SCOUT-3",
            "mission": (
                f"Research cutting-edge solutions for: '{task_description}'. "
                "Use web_search for patterns, libraries, prior art, pitfalls. "
                "Output: external research brief with citations."
            ),
            "tools": ["web_search", "webfetch"],
        },
        {
            "id": "SCOUT-4",
            "mission": (
                f"Analyze test coverage gaps for: '{task_description}'. "
                "Find existing tests, untested paths, test infrastructure. "
                "Output: coverage gap report."
            ),
            "tools": ["grep", "glob", "read", "exec"],
        },
        {
            "id": "SCOUT-5",
            "mission": (
                f"Check constraints for: '{task_description}'. "
                "Security policies, performance budgets, compatibility matrix, compliance. "
                "Output: constraint ledger."
            ),
            "tools": ["grep", "read", "exec"],
        },
    ]


def reviewer_personas() -> list[dict]:
    """Tạo work orders cho 3 adversarial reviewers.

    C3 pattern: Saboteur + New Hire + Security Auditor.
    """
    return [
        {
            "id": "SABOTEUR",
            "persona": "Hostile attacker",
            "question": "How do I break this design? What inputs crash it? What edge cases fail?",
        },
        {
            "id": "NEW_HIRE",
            "persona": "Junior engineer, first day",
            "question": "Can I understand this design without asking anyone? Where is it ambiguous?",
        },
        {
            "id": "SECURITY_AUDITOR",
            "persona": "OWASP-aligned auditor",
            "question": "Scan for OWASP Top 10 risks. What attack surfaces does this design open?",
        },
    ]


def technical_writer_mission(task_description: str, sdd_path: str) -> dict:
    """Mission cho Technical Writer: polish SDD và plan thành tài liệu rõ ràng."""
    return {
        "id": "TECHNICAL_WRITER",
        "mission": (
            f"Polish the Solution Design Document for '{task_description}'. "
            f"Input: draft at {sdd_path}. "
            "Output: improved clarity, consistent terminology, readable diagrams, "
            "well-structured sections. Do NOT change technical decisions."
        ),
        "tools": ["read", "edit"],
    }


def requirement_analyst_mission(task_description: str, sdd_path: str, plan_path: str) -> dict:
    """Mission cho Requirement Analyst: đảm bảo traceability REQ -> task -> file."""
    return {
        "id": "REQUIREMENT_ANALYST",
        "mission": (
            f"Verify requirement traceability for '{task_description}'. "
            f"Inputs: {sdd_path} and {plan_path}. "
            "Output: mapping REQ ID -> Task ID -> File Path -> Function, "
            "flag any missing or ambiguous trace."
        ),
        "tools": ["read", "grep"],
    }


def missions_summary() -> dict:
    """Trả về config tổng quát về số lượng agent."""
    return {
        "num_scouts": NUM_SCOUTS,
        "num_reviewers": NUM_REVIEWERS,
        "has_technical_writer": True,
        "has_requirement_analyst": True,
    }
