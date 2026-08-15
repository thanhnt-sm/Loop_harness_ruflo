#!/usr/bin/env python3
"""State machine v2: Graph-based Plan Phase orchestrator using StateGraph.

Replaces the hardcoded FSM with a dynamic StateGraph-based orchestrator.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Union

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pydantic import BaseModel, ConfigDict

from graph_engine import (
    StateGraph,
    CompiledStateGraph,
    GraphRunner,
    NodeDefinition,
    EdgeDefinition,
    NodeResult,
    DirectEdge,
    ConditionalEdge,
    FanOutEdge,
    FanInEdge,
    InterruptEdge,
    EdgeBuilder,
    CommonConditions,
    MemoryCheckpointer,
    SQLiteCheckpointer,
)

from . import constants as C
from .classifier import classify_tier
from .missions import (
    brainstorm_missions,
    dynamic_scenarios,
    reviewer_personas,
    scout_missions,
    technical_writer_mission,
)
from .storage import append_history, plans_dir


class PlanState(BaseModel):
    """Plan phase state — pydantic schema cho StateGraph.

    extra='allow' để node có thể set thêm key tùy ý (task_description, tier,
    review_findings...). Node dùng dict API (state["x"] / state.get("x")), nên
    PlanState proxy qua __getitem__/get/__setitem__/__contains__ để vừa qua được
    pydantic validation vừa gọi được như dict.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    state: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def __iter__(self):
        return iter(self.model_dump().keys())

    def to_dict(self) -> dict:
        return self.model_dump()


def _repo_root() -> Path:
    """Find repo root (contains .devin directory)."""
    here = Path(__file__).resolve().parent.parent.parent
    return here


def _plans_dir(root: Path, task_slug: str) -> Path:
    """Get plans directory for task."""
    return root / ".devin" / "plans" / task_slug


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

class InitNode:
    """Initialize the orchestrator."""

    def __init__(self, task_description: str):
        self.task_description = task_description

    async def execute(self, state: dict, context: dict) -> dict:
        return {
            "state": C.STATE_CLASSIFY,
            "task_description": self.task_description,
            "task_slug": self._slugify(self.task_description),
        }

    def _slugify(self, text: str) -> str:
        import re
        if not text:
            return ""
        slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug[:60] if slug else ""


class ClassifyNode:
    """Classify task tier."""

    async def execute(self, state: dict, context: dict) -> dict:
        tier = classify_tier(state["task_description"])
        if tier == "S":
            return {
                "state": C.STATE_DONE,
                "tier": tier,
            }
        return {
            "state": C.STATE_BRAINSTORM,
            "tier": tier,
        }


class BrainstormNode:
    """Dispatch brainstorm subagents."""

    async def execute(self, state: dict, context: dict) -> dict:
        missions = brainstorm_missions(state["task_description"])
        return {
            "state": C.STATE_ANALYZE,
            "brainstorm_missions": missions,
            "num_scouts": C.NUM_SCOUTS,
        }


class AnalyzeNode:
    """Wait for SCOUT results and aggregate."""

    async def execute(self, state: dict, context: dict) -> dict:
        # In real implementation, this would wait for subagent results
        # For now, transition to DESIGN
        return {
            "state": C.STATE_DESIGN,
            "analysis_context": state.get("scout_results", []),
        }


class ArchitectNode:
    """Generate SDD from analysis."""

    async def execute(self, state: dict, context: dict) -> dict:
        root = Path(context.get("root", "."))
        sdd_path = str(plans_dir(Path(context.get("root", ".")), state["task_slug"]) / "SOLUTION_DESIGN.md")

        # In real implementation, dispatch ARCHITECT subagent
        # For now, create placeholder SDD
        sdd_content = f"""# Solution Design Document

## Task: {state['task_description']}

## Analysis Context
{state.get('analysis_context', 'N/A')}

## Design
TODO: Generate from ARCHITECT subagent
"""

        sdd_path = Path(context.get("root", ".")) / "docs" / "plans" / state["task_slug"] / "SOLUTION_DESIGN.md"
        sdd_path.parent.mkdir(parents=True, exist_ok=True)
        Path(sdd_path).write_text(sdd_content)

        return {
            "state": C.STATE_REVIEW,
            "sdd_path": str(sdd_path),
        }


class ReviewNode:
    """Dispatch adversarial reviewers."""

    async def execute(self, state: dict, context: dict) -> dict:
        reviewers = reviewer_personas()
        dynamic = dynamic_scenarios(state["task_description"])
        return {
            "state": C.STATE_REVISION,
            "reviewers": reviewers,
            "dynamic_scenarios": dynamic,
            "revision_round": 1,
        }


class RevisionNode:
    """Revise SDD based on reviewer feedback."""

    async def execute(self, state: dict, context: dict) -> dict:
        # In real implementation, would fix SDD based on blocking issues
        blocking = [f for f in state.get("review_findings", []) if f.get("severity") == "BLOCKING"]

        if blocking and state.get("revision_round", 1) < C.MAX_REVISION_ROUNDS:
            return {
                "state": C.STATE_DESIGN,
                "revision_round": state.get("revision_round", 1) + 1,
                "blocking_issues": blocking,
            }
        elif blocking:
            return {
                "state": C.STATE_ESCALATE,
                "escalate_reason": f"Max {C.MAX_REVISION_ROUNDS} revision rounds exceeded, {len(blocking)} blocking issues remain",
            }
        else:
            return {"state": C.STATE_SDD_APPROVAL}


class SDDApprovalNode:
    """Present SDD for human approval."""

    async def execute(self, state: dict, context: dict) -> dict:
        # In real implementation, would call approval_gate.py --interactive
        # For now, simulate approval
        return {
            "state": C.STATE_PLAN,
            "sdd_approved": True,
        }


class PlanNode:
    """Decompose SDD into atomic tasks."""

    async def execute(self, state: dict, context: dict) -> dict:
        # In real implementation, decompose SDD into tasks
        return {
            "state": C.STATE_GAP_SCAN,
            "plan_path": str(plans_dir(Path("."), state["task_slug"]) / "IMPLEMENTATION_PLAN.md"),
        }


class GapScanNode:
    """Scan plan for gaps."""

    async def execute(self, state: dict, context: dict) -> dict:
        return {"state": C.STATE_QC}


class QCNode:
    """Run quality checks on plan."""

    async def execute(self, state: dict, context: dict) -> dict:
        return {
            "state": C.STATE_PLAN_ENHANCE,
            "qc_passed": True,
            "enhance_round": 1,
        }


class PlanEnhanceNode:
    """Enhance plan with additional checks."""

    async def execute(self, state: dict, context: dict) -> dict:
        return {"state": C.STATE_PLAN_APPROVAL}


class PlanApprovalNode:
    """Present plan for final human approval."""

    async def execute(self, state: dict, context: dict) -> dict:
        return {
            "state": C.STATE_WRITE_STATE,
            "plan_approved": True,
        }


class WriteStateNode:
    """Write plan state to activate enforcement."""

    async def execute(self, state: dict, context: dict) -> dict:
        return {"state": C.STATE_DONE}


class DoneNode:
    """Terminal node."""

    async def execute(self, state: dict, context: dict) -> dict:
        return {"state": C.STATE_DONE}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_plan_graph() -> StateGraph:
    """Build the Plan Phase StateGraph."""
    graph = StateGraph(state_schema=PlanState)

    # Add all nodes
    graph.add_node("INIT", InitNode("").execute)
    graph.add_node("CLASSIFY", ClassifyNode().execute)
    graph.add_node("BRAINSTORM", BrainstormNode().execute)
    graph.add_node("ANALYZE", AnalyzeNode().execute)
    graph.add_node("DESIGN", ArchitectNode().execute)
    graph.add_node("REVIEW", ReviewNode().execute)
    graph.add_node("REVISION", RevisionNode().execute)
    graph.add_node("SDD_APPROVAL", SDDApprovalNode().execute)
    graph.add_node("PLAN", PlanNode().execute)
    graph.add_node("GAP_SCAN", GapScanNode().execute)
    graph.add_node("QC", QCNode().execute)
    graph.add_node("PLAN_ENHANCE", PlanEnhanceNode().execute)
    graph.add_node("PLAN_APPROVAL", PlanApprovalNode().execute)
    graph.add_node("WRITE_STATE", WriteStateNode().execute)
    graph.add_node("DONE", DoneNode().execute)
    graph.add_node("REJECTED", lambda s, c: {"state": C.STATE_REJECTED})
    graph.add_node("ESCALATE", lambda s, c: {"state": C.STATE_ESCALATE})

    # Add edges
    graph.add_edge("INIT", "CLASSIFY")
    
    # CLASSIFY -> BRAINSTORM (M/L/XL) or DONE (S-tier)
    graph.add_conditional_edge(
        "CLASSIFY",
        lambda s: "DONE" if s.get("tier") == "S" else "BRAINSTORM",
        {"DONE": "DONE", "BRAINSTORM": "BRAINSTORM"},
    )

    graph.add_edge("BRAINSTORM", "ANALYZE")
    graph.add_edge("ANALYZE", "DESIGN")
    graph.add_edge("DESIGN", "REVIEW")
    
    # REVIEW -> REVISION (if blocking) or SDD_APPROVAL
    graph.add_conditional_edge(
        "REVIEW",
        lambda s: "REVISION" if any(f.get("severity") == "BLOCKING" for f in s.get("review_findings", [])) else "SDD_APPROVAL",
        {"REVISION": "REVISION", "SDD_APPROVAL": "SDD_APPROVAL"},
    )

    graph.add_edge("REVISION", "REVIEW")
    
    # SDD_APPROVAL -> PLAN or back to DESIGN
    graph.add_conditional_edge(
        "SDD_APPROVAL",
        lambda s: "PLAN" if s.get("sdd_approved") else "DESIGN",
        {"PLAN": "PLAN", "DESIGN": "DESIGN"},
    )

    graph.add_edge("PLAN", "GAP_SCAN")
    graph.add_edge("GAP_SCAN", "QC")
    
    # QC -> PLAN_ENHANCE (pass) or back to PLAN (fail)
    graph.add_conditional_edge(
        "QC",
        lambda s: "PLAN_ENHANCE" if s.get("qc_passed") else "PLAN",
        {"PLAN_ENHANCE": "PLAN_ENHANCE", "PLAN": "PLAN"},
    )

    # PLAN_ENHANCE -> PLAN_APPROVAL (clean) or back to PLAN (blocking)
    graph.add_conditional_edge(
        "PLAN_ENHANCE",
        lambda s: "PLAN_APPROVAL" if not any(f.get("severity") == "BLOCKING" for f in s.get("enhance_findings", [])) else "PLAN",
        {"PLAN_APPROVAL": "PLAN_APPROVAL", "PLAN": "PLAN"},
    )

    # PLAN_APPROVAL -> WRITE_STATE (approved) or back to DESIGN/PLAN
    graph.add_conditional_edge(
        "PLAN_APPROVAL",
        lambda s: "WRITE_STATE" if s.get("plan_approved") else "DESIGN",
        {"WRITE_STATE": "WRITE_STATE", "DESIGN": "DESIGN"},
    )

    graph.add_edge("WRITE_STATE", "DONE")

    # Terminal nodes: KHÔNG có outgoing edge → _get_next_node trả None → runner
    # kết thúc. Trước đây self-loop (DONE→DONE) khiến vòng lặp không bao giờ dừng.
    graph.set_entry_point("INIT")
    return graph


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class PlanOrchestratorV2:
    """Graph-based Plan Phase orchestrator."""

    def __init__(self, root: Path | None = None):
        self.root = root or Path(".").resolve()
        self.graph = build_plan_graph()
        self.compiled = None
        self.checkpointer = MemoryCheckpointer()

    def compile(self):
        """Compile the graph."""
        self.compiled = self.graph.compile()
        return self.compiled

    async def run(self, task_description: str, thread_id: str = "default") -> dict:
        """Run the Plan Phase for a task."""
        if not self.compiled:
            self.compile()

        initial_state = {
            "task_description": task_description,
            "task_slug": self._slugify(task_description),
        }

        config = {"configurable": {"thread_id": thread_id}}
        result = await self.compiled.ainvoke(initial_state, config)
        return result

    def _slugify(self, text: str) -> str:
        import re
        if not text:
            return ""
        slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug[:60] if slug else ""


# ---------------------------------------------------------------------------
# CLI compatibility
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for backward compatibility."""
    import argparse

    parser = argparse.ArgumentParser(description="Plan Phase Orchestrator v2 (Graph-based)")
    parser.add_argument("--init", action="store_true", help="Initialize new task")
    parser.add_argument("--task", type=str, help="Task description")
    parser.add_argument("--step", action="store_true", help="Process step")
    parser.add_argument("--state", type=str, help="State file path")
    parser.add_argument("--results", type=str, help="Results file path")
    parser.add_argument("--status", action="store_true", help="Show status")

    args = parser.parse_args(argv)

    if args.init and args.task:
        orchestrator = PlanOrchestratorV2()
        result = asyncio.run(orchestrator.run(args.task))
        print(json.dumps(result.to_dict() if hasattr(result, "to_dict") else result, ensure_ascii=False, indent=2))
        return 0

    parser.error("cần --init + --task")


if __name__ == "__main__":
    import json
    sys.exit(main(sys.argv[1:]))