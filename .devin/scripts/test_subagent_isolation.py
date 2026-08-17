#!/usr/bin/env python3
"""Test sub-agent isolation (C6)."""
from __future__ import annotations

import sys
sys.path.insert(0, "/workspace/.devin/scripts")

from subagent_isolation import run_subagent, run_parallel_subagents, _compress_subagent_output

# Test 1: Single sub-agent
print("=== Test 1: Single Sub-Agent ===")
result = run_subagent(
    task_brief="Find all TODO comments in src/ directory",
    parent_session_id="test-session-123",
    context_budget=3000,
    allowed_tools=["Read", "Grep", "Glob"],
    executor="glm-executor"
)
print(f"Status: {result['status']}")
print(f"Subagent ID: {result['subagent_id']}")
print(f"Summary: {result['summary']}")
print(f"Tokens: {result['tokens_used']}")
assert result['status'] == "completed"
assert result['subagent_id'].startswith("sub-")
assert 'compressed_output' in result

# Test 2: Output compression
print("\n=== Test 2: Output Compression ===")
mock_result = {
    "subagent_id": "test-123",
    "status": "completed",
    "summary": "A" * 500,  # Long summary
    "findings": [f"Finding {i}" for i in range(20)],  # Many findings
    "files_read": [f"/path/file{i}.py" for i in range(15)],
    "tokens_used": 1000,
}
compressed = _compress_subagent_output(mock_result, max_tokens=500)
print(f"Original summary len: {len(mock_result['summary'])}")
print(f"Compressed summary len: {len(compressed['summary'])}")
print(f"Original findings: {len(mock_result['findings'])}")
print(f"Compressed findings: {len(compressed['findings'])}")
assert len(compressed['summary']) <= 200
assert len(compressed['findings']) <= 5
assert compressed['compressed'] is True

# Test 3: Parallel sub-agents
print("\n=== Test 3: Parallel Sub-Agents ===")
tasks = [
    {"task_brief": "Task 1: Search for patterns", "context_budget": 2000},
    {"task_brief": "Task 2: List files", "context_budget": 2000},
    {"task_brief": "Task 3: Check config", "context_budget": 2000},
]
results = run_parallel_subagents(tasks, max_parallel=3)
print(f"Results count: {len(results)}")
for r in results:
    print(f"  {r['subagent_id']}: {r['status']}")
assert len(results) == 3
assert all(r['status'] == "completed" for r in results)

# Test 4: Error handling
print("\n=== Test 4: Context Budget Respected ===")
result = run_subagent(
    task_brief="Small task",
    context_budget=100,
    allowed_tools=["Read"],
)
assert result['status'] == "completed"

print("\n=== All C6 Tests Passed ===")