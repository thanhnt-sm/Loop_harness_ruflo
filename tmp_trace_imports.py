#!/usr/bin/env python3
"""Trace which file has null bytes during import."""
import sys
from pathlib import Path

# Add the same paths as conftest.py - repo root is current dir
REPO_ROOT = Path('.').resolve()
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

modules_to_try = [
    "secret_scanner",
    "update_common",
    "hook_integrity",
    "junk_file_scanner",
    "gitignore_audit",
    "check_governance",
    "check_deps",
    "auto_pr_runner",
    "context_projection",
    "token_registry",
    "skill_loader",
]

for mod_name in modules_to_try:
    try:
        __import__(mod_name)
        print(f"OK: {mod_name}")
    except SyntaxError as e:
        print(f"SYNTAX ERROR in {mod_name}: {e}")
    except Exception as e:
        print(f"ERROR in {mod_name}: {type(e).__name__}: {e}")
