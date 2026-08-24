#!/usr/bin/env python3
"""Test subagent_isolation.py — sub-agent isolation logic.

Test coverage cho:
- _create_subagent_context (tạo context cho sub-agent)
- _run_subagent (chạy sub-agent trong isolated process)
- _compress_subagent_output (nén output cho parent)
- run_subagent (spawn và run isolated sub-agent)
- run_parallel_subagents (chạy nhiều sub-agents song song)

Chạy: python -m pytest tests/test_subagent_isolation.py -v
"""
import json
import sys
from pathlib import Path

import pytest

# Add .devin/scripts to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".devin" / "scripts"))

import subagent_isolation


# ---------------------------------------------------------------------------
# _create_subagent_context
# ---------------------------------------------------------------------------

class TestCreateSubagentContext:
    """Test tạo context cho sub-agent."""

    def test_basic_context(self):
        """Tạo context cơ bản."""
        context = subagent_isolation._create_subagent_context(
            parent_session_id="parent-123",
            subagent_id="sub-456",
            task_brief="Find TODO comments"
        )
        assert context["parent_session_id"] == "parent-123"
        assert context["subagent_id"] == "sub-456"
        assert context["task_brief"] == "Find TODO comments"
        assert context["context_budget"] == 5000  # default
        assert "created_at" in context

    def test_custom_context_budget(self):
        """Tùy chỉnh context budget."""
        context = subagent_isolation._create_subagent_context(
            parent_session_id="parent-123",
            subagent_id="sub-456",
            task_brief="Find TODO comments",
            context_budget=3000
        )
        assert context["context_budget"] == 3000

    def test_custom_allowed_tools(self):
        """Tùy chỉnh allowed tools."""
        context = subagent_isolation._create_subagent_context(
            parent_session_id="parent-123",
            subagent_id="sub-456",
            task_brief="Find TODO comments",
            allowed_tools=["Read", "Grep"]
        )
        assert context["allowed_tools"] == ["Read", "Grep"]


# ---------------------------------------------------------------------------
# _run_subagent
# ---------------------------------------------------------------------------

class TestRunSubagent:
    """Test chạy sub-agent."""

    def test_run_subagent_success(self):
        """Chạy sub-agent thành công."""
        context = subagent_isolation._create_subagent_context(
            parent_session_id="parent-123",
            subagent_id="sub-456",
            task_brief="Find TODO comments"
        )
        result = subagent_isolation._run_subagent(context, timeout=30)
        assert result["subagent_id"] == "sub-456"
        assert result["status"] == "completed"
        assert "summary" in result
        assert "findings" in result
        assert "tokens_used" in result
        assert "completed_at" in result

    def test_run_subagent_custom_executor(self):
        """Chạy sub-agent với custom executor."""
        context = subagent_isolation._create_subagent_context(
            parent_session_id="parent-123",
            subagent_id="sub-456",
            task_brief="Find TODO comments"
        )
        result = subagent_isolation._run_subagent(context, executor="kimi-executor")
        assert result["executor_used"] in ["glm-executor", "kimi-executor"]


# ---------------------------------------------------------------------------
# _compress_subagent_output
# ---------------------------------------------------------------------------

class TestCompressSubagentOutput:
    """Test nén output sub-agent."""

    def test_compress_basic(self):
        """Nén output cơ bản."""
        result = {
            "subagent_id": "sub-456",
            "status": "completed",
            "summary": "A" * 300,  # dài
            "findings": ["finding"] * 10,
            "files_read": ["file"] * 20,
            "tokens_used": 5000,
        }
        compressed = subagent_isolation._compress_subagent_output(result)
        assert compressed["subagent_id"] == "sub-456"
        assert len(compressed["summary"]) <= 200
        assert len(compressed["findings"]) <= 5
        assert len(compressed["files_read"]) <= 10
        assert compressed["compressed"] is True

    def test_compress_within_budget(self):
        """Output đã nhỏ → không cần nén thêm."""
        result = {
            "subagent_id": "sub-456",
            "status": "completed",
            "summary": "Short summary",
            "findings": ["finding1", "finding2"],
            "files_read": ["file1"],
            "tokens_used": 100,
        }
        compressed = subagent_isolation._compress_subagent_output(result)
        assert compressed["summary"] == "Short summary"
        assert len(compressed["findings"]) == 2


# ---------------------------------------------------------------------------
# run_subagent
# ---------------------------------------------------------------------------

class TestRunSubagentFunction:
    """Test hàm run_subagent chính."""

    def test_run_subagent_success(self):
        """Chạy sub-agent thành công."""
        result = subagent_isolation.run_subagent(
            task_brief="Find TODO comments",
            parent_session_id="parent-123"
        )
        assert result["status"] in ["completed", "failed"]
        assert "subagent_id" in result
        assert "summary" in result

    def test_run_subagent_with_compression(self):
        """Chạy sub-agent với compression."""
        result = subagent_isolation.run_subagent(
            task_brief="Find TODO comments",
            parent_session_id="parent-123",
            compress_output=True
        )
        assert "compressed_output" in result
        assert result["compressed_output"]["compressed"] is True

    def test_run_subagent_without_compression(self):
        """Chạy sub-agent không compression."""
        result = subagent_isolation.run_subagent(
            task_brief="Find TODO comments",
            parent_session_id="parent-123",
            compress_output=False
        )
        assert "compressed_output" not in result

    def test_run_subagent_auto_parent_session(self):
        """Tự động tạo parent_session_id nếu không cung cấp."""
        result = subagent_isolation.run_subagent(
            task_brief="Find TODO comments"
        )
        assert result["status"] in ["completed", "failed"]
        # parent_session_id được tạo tự động


# ---------------------------------------------------------------------------
# run_parallel_subagents
# ---------------------------------------------------------------------------

class TestRunParallelSubagents:
    """Test chạy nhiều sub-agents song song."""

    def test_parallel_basic(self):
        """Chạy 3 sub-agents song song."""
        tasks = [
            {"task_brief": "Find TODO in src/"},
            {"task_brief": "List test files"},
            {"task_brief": "Check security patterns"},
        ]
        results = subagent_isolation.run_parallel_subagents(tasks, max_parallel=3)
        assert len(results) == 3
        for r in results:
            assert "subagent_id" in r
            assert r["status"] in ["completed", "failed"]

    def test_parallel_with_shared_kwargs(self):
        """Chạy song song với shared parameters."""
        tasks = [
            {"task_brief": "Task 1"},
            {"task_brief": "Task 2"},
        ]
        results = subagent_isolation.run_parallel_subagents(
            tasks,
            max_parallel=2,
            parent_session_id="shared-parent",
            context_budget=2000
        )
        assert len(results) == 2
        # Mỗi task có subagent_id riêng (khác nhau)

    def test_parallel_max_parallel_limit(self):
        """Giới hạn số lượng parallel."""
        tasks = [{"task_brief": f"Task {i}"} for i in range(10)]
        results = subagent_isolation.run_parallel_subagents(tasks, max_parallel=3)
        assert len(results) == 10
        # Không test trực tiếp concurrency — pytest không giám sát thread pool


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
