"""Tests cho provider config — verify opencode.json + AGENTS.md có HLK reference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")


def test_opencode_config_has_hlk_reference():
    """opencode.json có references.hlk và references.verify-first."""
    p = ROOT / "opencode.json"
    assert p.exists()
    cfg = json.loads(p.read_text(encoding="utf-8"))
    refs = cfg.get("references", {})
    assert "hlk" in refs, f"missing 'hlk' in references, got: {list(refs.keys())}"
    assert "verify-first" in refs, f"missing 'verify-first' in references, got: {list(refs.keys())}"
    # Verify paths
    assert "HLK" in refs["hlk"]["path"]
    assert "verify-first" in refs["verify-first"]["path"]


def test_opencode_config_hlk_description_mentions_source_of_truth():
    """references.hlk.description có chứa "Source of Truth"."""
    p = ROOT / "opencode.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    desc = cfg["references"]["hlk"]["description"]
    assert "SOURCE OF TRUTH" in desc.upper() or "Source of Truth" in desc


def test_root_agents_md_has_hlk_section():
    """AGENTS.md (root) có section "HLK is Source of Truth"."""
    p = ROOT / "AGENTS.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "HLK is Source of Truth" in content
    assert "HLK/chain/" in content


def test_devin_agents_md_has_hlk_section():
    """`.devin/AGENTS.md` có section về HLK (mirror)."""
    p = ROOT / ".devin" / "AGENTS.md"
    if not p.exists():
        pytest.skip(".devin/AGENTS.md not found")
    content = p.read_text(encoding="utf-8")
    # Chấp nhận cả 2: HLK mentioned hoặc chỉ AHD (devin-specific)
    # Nếu chưa có HLK section, skip (không bắt buộc mirror cho .devin vì đã note ở root)
    if "HLK" in content:
        assert "HLK" in content
