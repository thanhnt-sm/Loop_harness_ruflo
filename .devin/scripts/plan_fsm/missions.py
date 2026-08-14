#!/usr/bin/env python3
"""Mission/persona generators cho SCOUTs, reviewers, và writer.

Bước 1: Tạo work orders cho 8 SCOUT subagents — mỗi scout độc lập, chạy song song,
        tập trung vào một khía cạnh của task. Mọi scout phải search online.
Bước 2: Tạo work orders cho 6 adversarial reviewers — 3 cố định + 3 persona mở rộng.
Bước 3: Tạo dynamic attack scenarios dựa trên task context.
Bước 4: Tạo brainstorm missions — 5+ góc nhìn khác nhau cho task.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .constants import NUM_REVIEWERS, NUM_SCOUTS

# Task 3.8: mọi prompt chứa task_description (input user) phải qua template
# engine strict + auto-escape + injection check (prompt_template.py).
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from prompt_template import PromptInjectionError, PromptTemplate  # noqa: E402

_MISSION_TEMPLATE = PromptTemplate(
    "{{mission}}",  # placeholder — các mission cụ thể render qua _render_mission
)


def _render_mission(template: str, task_description: str) -> str:
    """Render mission prompt: task_description auto-escaped + injection-check."""
    tpl = PromptTemplate(template)
    try:
        return tpl.render_check({"task_description": task_description})[0]
    except PromptInjectionError as e:
        raise ValueError(
            f"Task description chứa prompt injection, từ chối tạo mission: {e}"
        ) from e


def scout_missions(task_description: str) -> list[dict]:
    """Tạo work orders cho 8 SCOUT subagents.

    Mỗi scout độc lập, chạy song song, tập trung vào một khía cạnh của task.
    Mọi scout phải chạy ít nhất 1 web_search query liên quan đến mission.
    """
    return [
        {
            "id": "SCOUT-1",
            "mission": _render_mission(
                "Scan codebase structure for task: '{{task_description | escape}}'. "
                "Map directory tree, module boundaries, entry points, build system. "
                "Output: structure map + dependency graph. "
                "MUST run at least 1 web_search query for best practices on similar codebase structures.",
                task_description,
            ),
            "tools": ["grep", "glob", "read", "web_search"],
        },
        {
            "id": "SCOUT-2",
            "mission": (
                _render_mission("Find relevant files + dependencies for: '{{task_description | escape}}'. ", task_description) +
                "Trace call paths, locate interfaces, identify blast radius. "
                "Output: file list with relevance rationale. "
                "MUST run at least 1 web_search query for dependency analysis patterns."
            ),
            "tools": ["grep", "glob", "read", "web_search"],
        },
        {
            "id": "SCOUT-3",
            "mission": (
                _render_mission("Research cutting-edge solutions for: '{{task_description | escape}}'. ", task_description) +
                "Use web_search for patterns, libraries, prior art, pitfalls. "
                "Output: external research brief with citations."
            ),
            "tools": ["web_search", "webfetch"],
        },
        {
            "id": "SCOUT-4",
            "mission": (
                _render_mission("Analyze test coverage gaps for: '{{task_description | escape}}'. ", task_description) +
                "Find existing tests, untested paths, test infrastructure. "
                "Output: coverage gap report. "
                "MUST run at least 1 web_search query for testing best practices relevant to this task."
            ),
            "tools": ["grep", "glob", "read", "exec", "web_search"],
        },
        {
            "id": "SCOUT-5",
            "mission": (
                _render_mission("Check constraints for: '{{task_description | escape}}'. ", task_description) +
                "Security policies, performance budgets, compatibility matrix, compliance. "
                "Output: constraint ledger. "
                "MUST run at least 1 web_search query for compliance/security standards relevant to this task."
            ),
            "tools": ["grep", "read", "exec", "web_search"],
        },
        {
            "id": "SCOUT-6",
            "mission": (
                _render_mission("Competitive analysis online for: '{{task_description | escape}}'. ", task_description) +
                "Search for how other projects/teams solve similar problems. "
                "Compare approaches, tools, architectures. "
                "Output: competitive analysis brief with pros/cons."
            ),
            "tools": ["web_search", "webfetch", "read"],
        },
        {
            "id": "SCOUT-7",
            "mission": (
                _render_mission("Known pitfalls + anti-patterns online for: '{{task_description | escape}}'. ", task_description) +
                "Search for common mistakes, failure modes, gotchas when doing similar work. "
                "Output: anti-pattern catalog with avoidance strategies."
            ),
            "tools": ["web_search", "webfetch", "read"],
        },
        {
            "id": "SCOUT-8",
            "mission": (
                _render_mission("DeepWiki MCP — GitHub repo docs for: '{{task_description | escape}}'. ", task_description) +
                "Query DeepWiki MCP for relevant GitHub repos. "
                "Search for documentation, architecture guides, API references. "
                "Output: external documentation brief with key findings."
            ),
            "tools": ["web_search", "read"],
        },
    ]


def reviewer_personas() -> list[dict]:
    """Tạo work orders cho 6 adversarial reviewers.

    C3 pattern mở rộng: 3 persona gốc + 3 persona mới.
    Reviewer mới: Architect (design review), Code Reviewer (maintainability),
    Git Workflow Master (merge impact).
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
        {
            "id": "ARCHITECT",
            "persona": "Senior system architect",
            "question": "Is this design scalable, maintainable, and aligned with system architecture? Any design smells?",
        },
        {
            "id": "CODE_REVIEWER",
            "persona": "Experienced code reviewer",
            "question": "Will this code be maintainable? Are there complexity issues? Naming? Abstraction leaks?",
        },
        {
            "id": "GIT_WORKFLOW_MASTER",
            "persona": "Git workflow expert",
            "question": "What merge conflicts will this cause? Branch strategy impact? History cleanliness?",
        },
    ]


def dynamic_scenarios(task_description: str) -> list[dict]:
    """Generate dynamic attack scenarios dựa trên task context.

    Bước 1: Phân tích keywords trong task description.
    Bước 2: Map keywords sang attack scenarios cụ thể.
    Bước 3: Trả list scenarios — mỗi scenario có id, question, focus.
    """
    desc = task_description.lower()
    scenarios: list[dict] = []

    # Bước 1: Detect domain keywords và generate scenarios tương ứng
    if any(kw in desc for kw in ["database", "db", "sql", "migration", "schema"]):
        scenarios.append({
            "id": "DATA_CORRUPTION_ATTACKER",
            "persona": "Data integrity attacker",
            "question": "How can I corrupt data? What transactions fail silently? What constraints are missing?",
        })
        scenarios.append({
            "id": "SQL_INJECTION_TESTER",
            "persona": "SQL injection specialist",
            "question": "Where can I inject SQL? What queries are unsafe? Are all inputs parameterized?",
        })

    if any(kw in desc for kw in ["api", "endpoint", "rest", "graphql", "route"]):
        scenarios.append({
            "id": "RATE_LIMIT_BREAKER",
            "persona": "Rate limit breaker",
            "question": "Can I overwhelm this API? What endpoints have no rate limiting? DoS vectors?",
        })
        scenarios.append({
            "id": "INPUT_FUZZER",
            "persona": "Input fuzzing specialist",
            "question": "What malformed inputs crash the API? Missing validation? Unexpected types?",
        })

    if any(kw in desc for kw in ["auth", "login", "token", "jwt", "session", "password"]):
        scenarios.append({
            "id": "PRIVILEGE_ESCALATION_TESTER",
            "persona": "Privilege escalation tester",
            "question": "Can I escalate privileges? Missing authorization checks? Token forgery?",
        })
        scenarios.append({
            "id": "TOKEN_FORGER",
            "persona": "Token forgery expert",
            "question": "Can I forge tokens? Weak signing? Missing expiry? Replay attacks?",
        })

    if any(kw in desc for kw in ["file", "upload", "download", "storage", "s3"]):
        scenarios.append({
            "id": "PATH_TRAVERSAL_ATTACKER",
            "persona": "Path traversal attacker",
            "question": "Can I access files outside intended directories? Path traversal? Symlink attacks?",
        })

    if any(kw in desc for kw in ["performance", "speed", "latency", "cache", "optimize"]):
        scenarios.append({
            "id": "RESOURCE_EXHAUSTER",
            "persona": "Resource exhaustion attacker",
            "question": "How can I exhaust memory/CPU/connections? What operations are unbounded?",
        })

    if any(kw in desc for kw in ["concurrent", "async", "parallel", "thread", "race"]):
        scenarios.append({
            "id": "RACE_CONDITION_EXPLOITER",
            "persona": "Race condition exploiter",
            "question": "What race conditions exist? TOCTOU bugs? Deadlock scenarios?",
        })

    # Bước 2: Nếu không detect domain cụ thể, thêm generic scenarios
    if not scenarios:
        scenarios.append({
            "id": "EDGE_CASE_HUNTER",
            "persona": "Edge case hunter",
            "question": "What extreme inputs break this? Empty? Max size? Unicode? Null?",
        })
        scenarios.append({
            "id": "FAILURE_CASCADE_ANALYST",
            "persona": "Failure cascade analyst",
            "question": "What happens when dependencies fail? Error cascade? Graceful degradation?",
        })

    return scenarios


def brainstorm_missions(task_description: str) -> list[dict]:
    """Tạo 5+ góc nhìn brainstorm khác nhau cho task.

    Mỗi góc nhìn đại diện một chiến lược giải pháp khác nhau.
    Output feed vào ARCHITECT để thiết kế SDD đa chiều.
    """
    return [
        {
            "id": "BRAINSTORM-FASTEST",
            "angle": "Fastest to implement",
            "question": _render_mission("What is the fastest way to implement '{{task_description | escape}}'? Minimal viable, fewest steps.", task_description),
        },
        {
            "id": "BRAINSTORM-SAFEST",
            "angle": "Safest / most secure",
            "question": _render_mission("What is the safest way to implement '{{task_description | escape}}'? Defense in depth, fail-safe defaults.", task_description),
        },
        {
            "id": "BRAINSTORM-SIMPLEST",
            "angle": "Simplest to understand",
            "question": _render_mission("What is the simplest way to implement '{{task_description | escape}}'? Minimal cognitive load, easy to explain.", task_description),
        },
        {
            "id": "BRAINSTORM-SCALE",
            "angle": "Most scalable",
            "question": _render_mission("What is the most scalable way to implement '{{task_description | escape}}'? Handles 10x growth, horizontal scale.", task_description),
        },
        {
            "id": "BRAINSTORM-CHEAPEST",
            "angle": "Cheapest to run",
            "question": _render_mission("What is the cheapest way to implement '{{task_description | escape}}'? Minimal resources, cost optimization.", task_description),
        },
        {
            "id": "BRAINSTORM-ROBUST",
            "angle": "Most robust against black swans",
            "question": _render_mission("What is the most robust way to implement '{{task_description | escape}}'? Survives unexpected failures, tail risks.", task_description),
        },
    ]


def technical_writer_mission(task_description: str, sdd_path: str) -> dict:
    """Mission cho Technical Writer: polish SDD và plan thành tài liệu rõ ràng."""
    return {
        "id": "TECHNICAL_WRITER",
        "mission": (
            _render_mission("Polish the Solution Design Document for '{{task_description | escape}}'. ", task_description) + 
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
            _render_mission("Verify requirement traceability for '{{task_description | escape}}'. ", task_description) + 
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
        "has_dynamic_scenarios": True,
        "has_brainstorm": True,
    }
