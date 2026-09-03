"""Tests cho skill_bench.py — benchmark mọi skill theo thời gian."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skill_bench import (  # noqa: E402
    BenchResult,
    _generate_scenarios_from_skill,
    _parse_skill_frontmatter,
    bench_skills,
    render_bench_report,
)


SAMPLE_SKILL = """---
name: test-skill
description: Test skill cho unit test
auto_generated: false
---

# Test Skill
"""


def test_parse_skill_frontmatter_valid(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(SAMPLE_SKILL, encoding="utf-8")
    fm = _parse_skill_frontmatter(p.read_text(encoding="utf-8"))
    assert fm["name"] == "test-skill"
    assert "description" in fm


def test_parse_skill_frontmatter_no_frontmatter():
    fm = _parse_skill_frontmatter("# Just a title")
    assert fm == {}


def test_generate_scenarios(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(SAMPLE_SKILL, encoding="utf-8")
    scenarios = _generate_scenarios_from_skill(p, n=5)
    assert len(scenarios) == 5
    assert all("Test skill" in s for s in scenarios)


def test_bench_skills_empty():
    results = bench_skills([])
    assert results == []


def test_bench_skills_with_skills(tmp_path):
    # Tạo 2 skill files giả
    (tmp_path / "SKILL1.md").parent.mkdir(exist_ok=True)
    skill1 = tmp_path / "SKILL1.md"
    skill1.write_text(SAMPLE_SKILL, encoding="utf-8")
    skill2 = tmp_path / "SKILL2.md"
    skill2.write_text(SAMPLE_SKILL, encoding="utf-8")
    results = bench_skills([skill1, skill2], scenarios_per_skill=3)
    assert len(results) == 2
    for r in results:
        assert r.scenarios_run == 3
        assert 0.0 <= r.pass_rate <= 1.0


# --- Phase 5 hardening: parallel ---


def test_bench_skills_parallel_1_sequential(tmp_path):
    """parallel=1 → sequential, behavior cũ."""
    (tmp_path / "SKILL1.md").parent.mkdir(exist_ok=True)
    skill1 = tmp_path / "SKILL1.md"
    skill1.write_text(SAMPLE_SKILL, encoding="utf-8")
    skill2 = tmp_path / "SKILL2.md"
    skill2.write_text(SAMPLE_SKILL, encoding="utf-8")
    results = bench_skills([skill1, skill2], scenarios_per_skill=2, parallel=1)
    assert len(results) == 2


def test_bench_skills_parallel_2_runs(tmp_path):
    """parallel=2 → vẫn chạy đúng, trả về đủ skills."""
    (tmp_path / "SKILL1.md").parent.mkdir(exist_ok=True)
    skill1 = tmp_path / "SKILL1.md"
    skill1.write_text(SAMPLE_SKILL, encoding="utf-8")
    skill2 = tmp_path / "SKILL2.md"
    skill2.write_text(SAMPLE_SKILL, encoding="utf-8")
    skill3 = tmp_path / "SKILL3.md"
    skill3.write_text(SAMPLE_SKILL, encoding="utf-8")
    results = bench_skills([skill1, skill2, skill3], scenarios_per_skill=2, parallel=2)
    assert len(results) == 3
    # Sorted by skill_name
    names = sorted([r.skill_name for r in results])
    assert names == ["SKILL1", "SKILL2", "SKILL3"]


def test_bench_skills_parallel_2_uses_parallel_path(tmp_path):
    """Verify parallel=2 trả về đủ results (path parallel đã cover)."""
    (tmp_path / "SKILL1.md").parent.mkdir(exist_ok=True)
    skill1 = tmp_path / "SKILL1.md"
    skill1.write_text(SAMPLE_SKILL, encoding="utf-8")
    skill2 = tmp_path / "SKILL2.md"
    skill2.write_text(SAMPLE_SKILL, encoding="utf-8")
    # parallel=2 nhưng len=2 → dùng path parallel (parallel=2 > 1, len > 1)
    # Vẫn pass vì code không crash
    results = bench_skills([skill1, skill2], scenarios_per_skill=1, parallel=2)
    assert len(results) == 2


def test_bench_one_skill_helper(tmp_path):
    """Helper _bench_one_skill hoạt động standalone."""
    (tmp_path / "SKILL1.md").parent.mkdir(exist_ok=True)
    skill1 = tmp_path / "SKILL1.md"
    skill1.write_text(SAMPLE_SKILL, encoding="utf-8")
    from skill_bench import _bench_one_skill
    r = _bench_one_skill(skill1, scenarios_per_skill=3)
    assert r.skill_name == "SKILL1"
    assert r.scenarios_run == 3


def test_render_bench_report(tmp_path):
    results = [
        BenchResult(skill_name="s1", skill_path="p1", scenarios_run=5, scenarios_passed=4,
                    pass_rate=0.8, avg_confidence=0.7, avg_latency_ms=100.0),
        BenchResult(skill_name="s2", skill_path="p2", scenarios_run=3, scenarios_passed=2,
                    pass_rate=0.67, avg_confidence=0.6, avg_latency_ms=150.0),
    ]
    out = tmp_path / "report.md"
    p = render_bench_report(results, out)
    assert Path(p).exists()
    content = out.read_text(encoding="utf-8")
    assert "Skill Benchmark Report" in content
    assert "| s1 |" in content
    assert "Overall pass rate" in content
    # JSON sidecar
    assert (tmp_path / "report.json").exists()
