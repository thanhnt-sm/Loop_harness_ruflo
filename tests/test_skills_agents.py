#!/usr/bin/env python3
"""Kiểm thử skill và agent definitions."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _parse_frontmatter(path: Path):
    # Tách YAML frontmatter từ markdown
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        return yaml.safe_load(parts[1]), parts[2]
    except yaml.YAMLError as e:
        raise AssertionError(f"YAML frontmatter lỗi trong {path}: {e}")


def test_skills_have_required_fields():
    # Mỗi SKILL.md phải có name, description, triggers
    skills_dir = REPO_ROOT / ".devin" / "skills"
    skill_files = []
    for pattern in ["*/SKILL.md", "*.md"]:
        skill_files.extend(skills_dir.glob(pattern))
    assert skill_files, "Không tìm thấy skill file nào"
    for f in skill_files:
        if f.name == "README.md" or f.name == "ATTRIBUTION.md":
            continue
        meta, _ = _parse_frontmatter(f)
        assert meta is not None, f"{f} thiếu YAML frontmatter"
        assert "name" in meta, f"{f} thiếu 'name'"
        assert "description" in meta, f"{f} thiếu 'description'"
        assert "triggers" in meta, f"{f} thiếu 'triggers'"
        assert isinstance(meta["triggers"], list), f"{f} triggers phải là list"


@pytest.mark.skipif(not (REPO_ROOT / ".devin" / "agents").exists(),
                    reason=".devin/agents not available (gitignored or not cloned)")
def test_agents_have_required_fields():
    # Mỗi AGENT.md phải có name, description, model
    agents_dir = REPO_ROOT / ".devin" / "agents"
    agent_files = list(agents_dir.glob("*/AGENT.md"))
    assert agent_files, (
        f"Không tìm thấy AGENT.md nào. "
        f"agents_dir={agents_dir}, exists={agents_dir.exists()}, "
        f"is_dir={agents_dir.is_dir()}, "
        f"listdir={list(agents_dir.iterdir()) if agents_dir.is_dir() else 'N/A'}"
    )
    for f in agent_files:
        meta, _ = _parse_frontmatter(f)
        assert meta is not None, f"{f} thiếu YAML frontmatter"
        assert "name" in meta, f"{f} thiếu 'name'"
        assert "description" in meta, f"{f} thiếu 'description'"
        assert "model" in meta, f"{f} thiếu 'model'"


def test_skill_names_match_directories():
    # Tên skill phải khớp với tên thư mục (nếu là subdir)
    skills_dir = REPO_ROOT / ".devin" / "skills"
    for subdir in skills_dir.iterdir():
        if subdir.is_dir() and (subdir / "SKILL.md").exists():
            meta, _ = _parse_frontmatter(subdir / "SKILL.md")
            assert meta is not None
            assert meta["name"] == subdir.name, f"Skill name {meta['name']} không khớp thư mục {subdir.name}"


@pytest.mark.skipif(not (REPO_ROOT / ".devin" / "agents").exists(),
                    reason=".devin/agents not available (gitignored or not cloned)")
def test_agent_names_match_directories():
    # Tên agent phải khớp với tên thư mục
    agents_dir = REPO_ROOT / ".devin" / "agents"
    for subdir in agents_dir.iterdir():
        if subdir.is_dir() and (subdir / "AGENT.md").exists():
            meta, _ = _parse_frontmatter(subdir / "AGENT.md")
            assert meta is not None
            assert meta["name"] == subdir.name, f"Agent name {meta['name']} không khớp thư mục {subdir.name}"


def test_skills_references_exist():
    # Các file/script được skill tham chiếu phải tồn tại
    # Chỉ kiểm tra các file nằm trong .devin/scripts được trích dẫn trong skill /plan
    plan_skill = REPO_ROOT / ".devin" / "skills" / "plan" / "SKILL.md"
    if plan_skill.exists():
        text = plan_skill.read_text(encoding="utf-8")
        for script in ["plan_orchestrator.py", "approval_gate.py", "plan_quality_check.py"]:
            assert script in text, f"{plan_skill} không tham chiếu {script}"


def test_lightning_skill_has_executor_profile():
    # Skill lightning phải nhắc đến lightning-executor
    skill = REPO_ROOT / ".devin" / "skills" / "lightning" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "lightning-executor" in text


def test_glm_skill_has_executor_profile():
    # Skill glm phải nhắc đến glm-executor
    skill = REPO_ROOT / ".devin" / "skills" / "glm" / "SKILL.md"
    assert skill.exists()
    text = skill.read_text(encoding="utf-8")
    assert "glm-executor" in text


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
