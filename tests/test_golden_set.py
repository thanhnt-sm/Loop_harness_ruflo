"""Tests for Golden Set Miner (V1)."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from golden_set_miner import (
    GoldenTask,
    mine_merged_prs,
    save_golden_task,
    load_golden_manifest,
    load_golden_task,
    list_golden_tasks,
    get_golden_stats,
    _estimate_difficulty,
    _extract_tags,
)


class TestGoldenTask:
    """Test GoldenTask dataclass."""

    def test_task_creation(self):
        task = GoldenTask(
            task_id="test-1",
            repo="test-repo",
            issue="#123",
            pr="#123",
            base_sha="abc123",
            head_sha="def456",
            description="Test task",
            golden_diff="diff --git a/file.py b/file.py\n+print('hello')",
            content_hash="abcdef123456",
            created_at="2026-01-15",
            difficulty="easy",
            tags=["python", "bugfix"],
        )
        assert task.task_id == "test-1"
        assert task.difficulty == "easy"


class TestDifficultyEstimation:
    """Test difficulty estimation from diff."""

    def test_easy_diff(self):
        diff = "diff --git a/file.py b/file.py\n+print('hello')"
        assert _estimate_difficulty(diff) == "easy"

    def test_medium_diff(self):
        diff = "diff --git a/file1.py b/file1.py\n+print('1')\n" \
               "diff --git a/file2.py b/file2.py\n+print('2')\n" \
               "diff --git a/file3.py b/file3.py\n+print('3')"
        assert _estimate_difficulty(diff) == "medium"

    def test_hard_diff(self):
        diff = "\n".join([f"diff --git a/file{i}.py b/file{i}.py\n+print('x')" for i in range(6)])
        assert _estimate_difficulty(diff) == "hard"


class TestTagExtraction:
    """Test tag extraction from diff."""

    def test_python_tag(self):
        diff = "diff --git a/main.py b/main.py\n+print('hello')"
        tags = _extract_tags(diff, "feat: add feature")
        assert "python" in tags

    def test_bugfix_tag(self):
        diff = "diff --git a/test.py b/test.py\n+assert True"
        tags = _extract_tags(diff, "fix: bug fix")
        assert "bugfix" in tags
        assert "test" in tags

    def test_feature_tag(self):
        diff = "diff --git a/feature.py b/feature.py\n+def new(): pass"
        tags = _extract_tags(diff, "feat: new feature")
        assert "feature" in tags


class TestGoldenSetMiner:
    """Test golden set mining (requires git repo)."""

    def test_mine_empty_repo(self, tmp_path):
        """Test mining on empty repo returns empty list."""
        # Create a minimal git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        tasks = mine_merged_prs(tmp_path, min_days=1, max_days=365)
        # No merge commits in fresh repo
        assert len(tasks) == 0

    def test_difficulty_estimation_accuracy(self):
        """Test difficulty estimation with known diffs."""
        # Easy: single file, small change
        easy_diff = "diff --git a/a.py b/a.py\n+print(1)\n"
        assert _estimate_difficulty(easy_diff) == "easy"

        # Medium: few files, moderate changes
        medium_diff = "diff --git a/a.py b/a.py\n+print(1)\n" \
                      "diff --git a/b.py b/b.py\n+print(2)\n"
        assert _estimate_difficulty(medium_diff) == "medium"

        # Hard: many files or large changes
        hard_diff = "\n".join([f"diff --git a/f{i}.py b/f{i}.py\n+print({i})" for i in range(10)])
        assert _estimate_difficulty(hard_diff) == "hard"


class TestGoldenTaskPersistence:
    """Test saving/loading golden tasks."""

    def test_save_and_load_task(self, tmp_path):
        task = GoldenTask(
            task_id="test-save-1",
            repo="test",
            issue="#1",
            pr="#1",
            base_sha="aaa",
            head_sha="bbb",
            description="Test",
            golden_diff="diff --git a/x.py b/x.py\n+1",
            content_hash="hash123",
            created_at="2026-01-01",
            difficulty="easy",
            tags=["test"],
        )

        # Save
        save_golden_task(task)

        # Load manifest
        manifest = load_golden_manifest()
        assert "test-save-1" in manifest["tasks"]

        # Load task
        loaded = load_golden_task("test-save-1")
        assert loaded is not None
        assert loaded.task_id == "test-save-1"
        assert loaded.description == "Test"

    def test_list_tasks(self, tmp_path):
        task1 = GoldenTask(
            task_id="list-1", repo="r", issue="#1", pr="#1",
            base_sha="a", head_sha="b", description="Easy task",
            golden_diff="diff", content_hash="h1", created_at="2026-01-01",
            difficulty="easy", tags=["easy", "python"]
        )
        task2 = GoldenTask(
            task_id="list-2", repo="r", issue="#2", pr="#2",
            base_sha="a", head_sha="b", description="Hard task",
            golden_diff="diff", content_hash="h2", created_at="2026-01-01",
            difficulty="hard", tags=["hard", "typescript"]
        )

        save_golden_task(task1)
        save_golden_task(task2)

        # List all
        tasks = list_golden_tasks()
        assert len(tasks) >= 2

        # Filter by difficulty
        easy_tasks = list_golden_tasks(difficulty="easy")
        assert any(t.task_id == "list-1" for t in easy_tasks)
        assert not any(t.task_id == "list-2" for t in easy_tasks)

        # Filter by tags
        py_tasks = list_golden_tasks(tags=["python"])
        assert any(t.task_id == "list-1" for t in py_tasks)


class TestGoldenStats:
    """Test golden set statistics."""

    def test_get_stats(self, tmp_path):
        stats = get_golden_stats()
        assert "total_tasks" in stats
        assert "difficulties" in stats
        assert "unique_tags" in stats
        assert stats["total_tasks"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])