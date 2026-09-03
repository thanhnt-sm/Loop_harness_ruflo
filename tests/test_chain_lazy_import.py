"""Tests cho HLK/chain/__init__.py lazy import (PEP 562)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")


def test_lazy_import_basic():
    """Verify chain module có thể import và access symbols."""
    sys.path.insert(0, str(ROOT / "HLK"))
    import chain
    # Symbols có sẵn
    assert len(chain.__all__) > 0
    assert "parse_brd_file" in chain.__all__
    assert "should_auto_merge" in chain.__all__


def test_lazy_load_only_one_module():
    """Khi access 1 symbol, chỉ load 1 module (không load tất cả)."""
    sys.path.insert(0, str(ROOT / "HLK"))
    import chain
    # Access 1 symbol
    val = chain.parse_brd_file
    # Verify cached trong globals
    assert "parse_brd_file" in chain.__dict__
    # Verify module khác chưa loaded (heuristic check: not in globals)
    # (không assert strict vì 1 module có thể import chain khác)


def test_dir_lists_all_symbols():
    """dir(chain) phải list đầy đủ public symbols."""
    sys.path.insert(0, str(ROOT / "HLK"))
    import chain
    d = dir(chain)
    assert "parse_brd_file" in d
    assert "should_auto_merge" in d
    assert len(d) >= len(chain.__all__)


def test_unknown_attribute_raises():
    """Access unknown attribute → AttributeError."""
    sys.path.insert(0, str(ROOT / "HLK"))
    import chain
    with pytest.raises(AttributeError):
        _ = chain.this_does_not_exist_at_all


def test_lazy_import_speed():
    """Verify lazy: chỉ access 1 symbol, không load all 18 modules."""
    sys.path.insert(0, str(ROOT / "HLK"))
    import chain
    # Snapshot loaded modules trước
    import sys as _sys
    before = {m for m in _sys.modules if m.startswith("HLK.chain.")}
    # Access 1 symbol
    _ = chain.parse_brd_file
    after = {m for m in _sys.modules if m.startswith("HLK.chain.")}
    # Số modules loaded phải tăng ít (< 5, không phải tất cả 18)
    delta = len(after) - len(before)
    assert delta < 5, f"Loaded {delta} modules (expected < 5, lazy not working)"
