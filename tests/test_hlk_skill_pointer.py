"""Tests cho HLK SKILL pointer files."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")


def test_hlk_skill_canonical_exists():
    """HLK/skills/verify-first/SKILL.md phải tồn tại (canonical)."""
    p = ROOT / "HLK" / "skills" / "verify-first" / "SKILL.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "name: verify-first" in content
    assert "HLK/chain/" in content


def test_cmdc_skill_is_pointer():
    """`.commandcode/skills/verify-first/SKILL.md` phải là pointer tới HLK."""
    p = ROOT / ".commandcode" / "skills" / "verify-first" / "SKILL.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "POINTER" in content or "Canonical source" in content
    assert "HLK" in content


def test_opencode_command_is_pointer():
    """`.opencode/command/verify-first.md` phải là pointer tới HLK."""
    p = ROOT / ".opencode" / "command" / "verify-first.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "POINTER" in content or "Canonical source" in content
    assert "HLK" in content


def test_cmdc_agent_is_pointer():
    """`.commandcode/agents/verify-first.md` phải là pointer tới HLK."""
    p = ROOT / ".commandcode" / "agents" / "verify-first.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "POINTER" in content or "Canonical source" in content
    assert "HLK" in content


def test_pointers_have_no_implementation():
    """Pointer files KHÔNG chứa implementation logic, chỉ reference."""
    for path in [
        ".commandcode/skills/verify-first/SKILL.md",
        ".opencode/command/verify-first.md",
        ".commandcode/agents/verify-first.md",
    ]:
        full = ROOT / path
        if full.exists():
            content = full.read_text(encoding="utf-8")
            # Pointer không nên có "def " (function definition) hoặc import chain modules
            assert "def " not in content or "Delegate" in content or "canonical" in content.lower()
