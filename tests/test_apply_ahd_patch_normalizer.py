#!/usr/bin/env python3
"""Kiểm thử normalize_text_after_merge (T3.5 / REQ-002)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import apply_ahd_patch  # noqa: E402
import update_common  # noqa: E402


def test_normalize_md_updates_distill_refs(tmp_path: Path):
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_path
    apply_ahd_patch.REPO_ROOT = tmp_path
    try:
        (tmp_path / ".devin" / "canon").mkdir(parents=True)
        target = tmp_path / ".devin" / "canon" / "TEST.md"
        target.write_text(
            "See distill/canon/VERIFICATION_PROTOCOL.md for detail.\n"
            "Code inline `distill/canon/VERIFICATION_PROTOCOL.md` stays.\n",
            encoding="utf-8",
        )

        apply_ahd_patch.normalize_text_after_merge([".devin/canon/TEST.md"])
        text = target.read_text(encoding="utf-8")
        # Plain text reference được thay
        assert ".devin/canon/VERIFICATION_PROTOCOL.md" in text
        assert text.count("distill/canon/VERIFICATION_PROTOCOL.md") == 1  # chỉ còn trong code inline
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old
