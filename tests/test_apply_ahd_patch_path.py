#!/usr/bin/env python3
"""Kiểm thử map_path và path traversal guard (T3.2 / REQ-009)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import apply_ahd_patch  # noqa: E402


def test_map_path_distill_layout_to_devin():
    repo = Path("/tmp/repo")  # repo_root not used if rel starts with upstream prefix
    assert apply_ahd_patch.map_path("distill/canon/VERIFICATION_PROTOCOL.md", repo) == ".devin/canon/VERIFICATION_PROTOCOL.md"


def test_map_path_devin_passthrough():
    repo = Path("/tmp/repo")
    assert apply_ahd_patch.map_path(".devin/skills/lightning/SKILL.md", repo) == ".devin/skills/lightning/SKILL.md"


def test_map_path_rejects_traversal(tmp_path: Path, capsys):
    repo = tmp_path
    result = apply_ahd_patch.map_path("distill/canon/../../../.env", repo)
    assert result is None
    out = capsys.readouterr().out
    assert "path-traversal" in out.lower() or "blocked" in out.lower()


def test_map_path_rejects_unmapped():
    repo = Path("/tmp/repo")
    assert apply_ahd_patch.map_path("unknown/path/file.txt", repo) is None
