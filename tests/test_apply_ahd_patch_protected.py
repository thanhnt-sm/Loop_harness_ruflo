#!/usr/bin/env python3
"""Kiểm thử is_protected và protected file guard (T3.3 / REQ-012)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import apply_ahd_patch  # noqa: E402


@pytest.mark.parametrize("path", [
    ".env",
    "HLK/file.md",
    ".devin/hooks/post_tool_use.py",
    "secrets/key.pem",
    "config.pem",
])
def test_is_protected_blocks_risky_files(path: str):
    protected = apply_ahd_patch.get_protected_files()
    assert apply_ahd_patch.is_protected(path, protected) is True


@pytest.mark.parametrize("path", [
    ".devin/scripts/apply_ahd_patch.py",
    ".devin/skills/lightning/SKILL.md",
    "docs/USAGE_GUIDE.md",
    "README.md",
])
def test_is_protected_allows_safe_files(path: str):
    protected = apply_ahd_patch.get_protected_files()
    assert apply_ahd_patch.is_protected(path, protected) is False
