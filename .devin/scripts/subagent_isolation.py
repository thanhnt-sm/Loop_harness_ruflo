#!/usr/bin/env python3
"""Sub-Agent Isolation (C6) — spawn isolated sub-tasks in fresh context windows.

Implements:
- C6: Sub-agent isolation for parallelizable, compressible, noisy exploration tasks
- Parent gives brief, child returns summary → saves parent tokens
- Uses when: task parallelizable, result compressible, exploration noisy
- Avoids when: parent already has context, task tightly coupled

Reference: Anthropic Effective Harnesses, OpenDev sub-agent patterns.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from self_consistency import _repo_root


class SubAgentError(Exception):
    """Raised when sub-agent execution fails."""
    pass


def _create_subagent_context(
    parent_session_id: str,
    subagent_id: str,
    task_brief: str,
    context_budget: int = 5000,
    allowed_tools: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Create isolated context for sub-agent."""
    return {
        "subagent_id": subagent_id,
        "parent_session_id": parent_session_id,
        "task_brief": task_brief,
        "context_budget": context_budget,
        "allowed_tools": allowed_tools or ["Read", "Grep", "Glob", "Bash"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "context_used": 0,
        "outputs": [],
    }


def _run_subagent(
    subagent_context: Dict[str, Any],
    executor: str = "glm-executor",
    timeout: int = 120
) -> Dict[str, Any]:
    """Run sub-agent in isolated process.
    
    In practice, this would spawn a fresh model context.
    Here we simulate by running a focused task with limited context.
    """
    subagent_id = subagent_context["subagent_id"]
    task_brief = subagent_context["task_brief"]
    allowed_tools = subagent_context["allowed_tools"]
    
    # Build prompt for sub-agent
    system_prompt = f"""You are a sub-agent with ID {subagent_id}.
Task: {task_brief}

Constraints:
- Context budget: {subagent_context['context_budget']} tokens
- Allowed tools: {', '.join(allowed_tools)}
- Return ONLY a concise summary + key findings
- Do NOT include full file contents unless critical
- Compress observations using caveman protocol

Output format:
SUMMARY: <one-line summary>
FINDINGS: <bullet points>
FILES_READ: <list of paths>
TOKENS_USED: <estimate>
"""
    
    # Simulate sub-agent execution via focused subprocess
    # In real implementation, this would call the model API with isolated context
    result = subprocess.run(
        [".venv/bin/python", "-c", f"""
import sys
sys.path.insert(0, '/workspace/.devin/scripts')
from auto_model_router import select_executor
selection = select_executor('{task_brief[:200]}')
print(selection['executor'])
"""],
        capture_output=True, text=True, timeout=10
    )
    
    selected_executor = result.stdout.strip() if result.returncode == 0 else executor
    
    # Return simulated result (in real implementation, this would be model output)
    return {
        "subagent_id": subagent_id,
        "status": "completed",
        "summary": f"Completed: {task_brief[:100]}",
        "findings": ["Simulated finding 1", "Simulated finding 2"],
        "files_read": [],
        "tokens_used": 500,
        "executor_used": selected_executor,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def _compress_subagent_output(result: Dict[str, Any], max_tokens: int = 1000) -> Dict[str, Any]:
    """Compress sub-agent output for parent consumption."""
    compressed = {
        "subagent_id": result["subagent_id"],
        "status": result["status"],
        "summary": result["summary"][:200],
        "findings": result["findings"][:5],  # Top 5 findings
        "files_read": result["files_read"][:10],
        "tokens_used": result["tokens_used"],
        "compressed": True,
    }
    
    # Estimate tokens
    estimated = len(json.dumps(compressed)) // 4
    if estimated > max_tokens:
        # Further compress
        compressed["findings"] = compressed["findings"][:3]
        compressed["summary"] = compressed["summary"][:100]
    
    return compressed


def run_subagent(
    task_brief: str,
    parent_session_id: str = "",
    context_budget: int = 5000,
    allowed_tools: Optional[List[str]] = None,
    executor: str = "glm-executor",
    compress_output: bool = True
) -> Dict[str, Any]:
    """Spawn and run an isolated sub-agent.
    
    Args:
        task_brief: Brief description of the sub-task
        parent_session_id: Parent session ID for tracking
        context_budget: Token budget for sub-agent
        allowed_tools: Tools the sub-agent can use
        executor: Model executor to use
        compress_output: Whether to compress output for parent
    
    Returns:
        {
            "subagent_id": str,
            "status": "completed|failed",
            "summary": str,
            "findings": List[str],
            "files_read": List[str],
            "tokens_used": int,
            "compressed_output": Dict (if compress_output=True)
        }
    """
    if not parent_session_id:
        parent_session_id = str(uuid.uuid4())[:8]
    
    subagent_id = f"sub-{uuid.uuid4().hex[:8]}"
    
    # Create sub-agent context
    context = _create_subagent_context(
        parent_session_id=parent_session_id,
        subagent_id=subagent_id,
        task_brief=task_brief,
        context_budget=context_budget,
        allowed_tools=allowed_tools
    )
    
    try:
        # Run sub-agent
        result = _run_subagent(context, executor=executor)
        
        if compress_output:
            result["compressed_output"] = _compress_subagent_output(result)
        
        return result
        
    except Exception as e:
        return {
            "subagent_id": subagent_id,
            "status": "failed",
            "error": str(e),
            "summary": f"Failed: {task_brief[:100]}",
            "findings": [],
            "files_read": [],
            "tokens_used": 0,
        }


def run_parallel_subagents(
    tasks: List[Dict[str, Any]],
    max_parallel: int = 3,
    **shared_kwargs
) -> List[Dict[str, Any]]:
    """Run multiple sub-agents in parallel (simulated).
    
    Args:
        tasks: List of task briefs with optional overrides
        max_parallel: Maximum concurrent sub-agents
        **shared_kwargs: Shared parameters (parent_session_id, etc.)
    
    Returns:
        List of sub-agent results
    """
    import concurrent.futures
    
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = []
        for i, task in enumerate(tasks):
            task_kwargs = {**shared_kwargs}
            task_kwargs.update(task)
            # Each sub-agent gets unique ID
            task_kwargs["parent_session_id"] = task_kwargs.get("parent_session_id", f"parent-{uuid.uuid4().hex[:8]}")
            futures.append(executor.submit(run_subagent, **task_kwargs))
        
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    return results


# Example usage
if __name__ == "__main__":
    # Single sub-agent
    print("=== Single Sub-Agent ===")
    result = run_subagent(
        task_brief="Find all TODO comments in src/ directory",
        parent_session_id="main-session-123",
        context_budget=3000,
        allowed_tools=["Read", "Grep", "Glob"],
        executor="glm-executor"
    )
    print(f"Status: {result['status']}")
    print(f"Summary: {result['summary']}")
    print(f"Tokens: {result['tokens_used']}")
    
    # Parallel sub-agents
    print("\n=== Parallel Sub-Agents ===")
    tasks = [
        {"task_brief": "Find all TODO comments in src/", "context_budget": 2000},
        {"task_brief": "List all test files in tests/", "context_budget": 2000},
        {"task_brief": "Check for security patterns in .devin/hooks/", "context_budget": 2000},
    ]
    results = run_parallel_subagents(tasks, max_parallel=3)
    for r in results:
        print(f"  {r['subagent_id']}: {r['status']} - {r['summary'][:60]}")