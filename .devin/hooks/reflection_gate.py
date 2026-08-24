#!/usr/bin/env python3
"""reflection_gate.py — Runtime hook wrapper (deprecated standalone copy).

CANONICAL implementation lives at `.devin/scripts/reflection_gate.py`.
This wrapper re-exports it via importlib to guarantee identical behavior
whether imported from `.devin/hooks` or `.devin/scripts` (fixes test
sys.path pollution where tests resolved the wrong module).

Safe zone: .devin/hooks/ — only re-exports, no logic duplication.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_FILE = str(Path(__file__).resolve().parent.parent / "scripts" / "reflection_gate.py")

# Load canonical scripts implementation directly (avoid circular import)
_spec = importlib.util.spec_from_file_location("_reflection_gate_canonical", _SCRIPT_FILE)
_canonical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_canonical)

# Re-export all symbols (including underscore helpers like _cli) from canonical module
for _name in dir(_canonical):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_canonical, _name)

# Backward-compat alias: hooks historically exposed ReflectionVerdict
ReflectionVerdict = globals().get("ReflectVerdict")
