#!/usr/bin/env python3
"""Kiểm thử BOOT lazy-load contract (R-07): canon chỉ nạp on-demand."""
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("rel,limit", [
    (".devin/AGENTS.md", 8 * 1024),
    (".devin/canon/CORE_CANON.md", 8 * 1024),
    (".devin/canon/REDLINES.md", 8 * 1024),
])
def test_boot_files_stay_small(rel, limit):
    p = REPO_ROOT / rel
    assert p.exists(), f"thiếu {rel}"
    assert p.stat().st_size < limit, (
        f"{rel} đã lớn ({p.stat().st_size}B) — phải giữ nhỏ để nạp ở BOOT"
    )


def test_boot_entry_does_not_inline_full_canon():
    # Entry file phải THAM CHIẾU canon, không nhúng nội dung canon vào.
    entry = (REPO_ROOT / ".devin" / "AGENTS.md").read_text(encoding="utf-8")
    for canon in ("CORE_CANON.md", "BOOT_PROTOCOL.md", "REDLINES.md"):
        assert canon in entry, f"entry không tham chiếu {canon}"
    # Không được nhúng trọn nội dung VERIFICATION_PROTOCOL (44KB) vào entry.
    verify = (REPO_ROOT / ".devin" / "canon" / "VERIFICATION_PROTOCOL.md").read_text(encoding="utf-8")
    sample_line = next((l for l in verify.splitlines() if len(l.strip()) > 40), "")
    if sample_line:
        assert sample_line not in entry, "entry nhúng nội dung canon (không lazy-load)"


def test_full_reference_never_auto_loaded():
    # AGENTS_full.md (186KB) chỉ được reference, không auto-load ở BOOT.
    full = REPO_ROOT / ".devin" / "AGENTS_full.md"
    assert full.exists()
    assert full.stat().st_size > 100 * 1024
    boot = (REPO_ROOT / ".devin" / "canon" / "BOOT_PROTOCOL.md").read_text(encoding="utf-8")
    entry = (REPO_ROOT / ".devin" / "AGENTS.md").read_text(encoding="utf-8")
    assert "ON-DEMAND" in boot.upper() or "on-demand" in boot or "lazy-load" in boot.lower(), (
        "BOOT_PROTOCOL phải xác nhận canon on-demand"
    )
    assert "AGENTS_full" in entry, "entry phải reference AGENTS_full.md (không nhúng)"


def test_canon_reference_blocks_are_valid_paths():
    # Mọi canon được tham chiếu trong AGENTS.md đều tồn tại.
    entry = (REPO_ROOT / ".devin" / "AGENTS.md").read_text(encoding="utf-8")
    canon_dir = REPO_ROOT / ".devin" / "canon"
    for m in re.findall(r"([A-Z_]+\.md)", entry):
        # Chỉ bỏ qua entry/docs refs (không nằm trong thư mục canon)
        if m in ("AGENTS.md", "AGENTS_full.md", "CLAUDE.md", "USAGE_GUIDE.md", "CONTINUOUS_LOOP_GUIDE.md", "WORKSPACE_GOVERNANCE.md"):
            continue
        assert (canon_dir / m).exists(), f"canon thiếu: {m}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
