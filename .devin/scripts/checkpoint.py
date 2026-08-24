#!/usr/bin/env python3
"""checkpoint.py — Luu/phuc hoi trang thai (checkpointed backtracking).

Entry point that re-exports public API from sub-modules.
Works both as module (import checkpoint) and as script (python checkpoint.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure .devin/scripts is on sys.path for absolute imports
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Re-export public API from sub-modules (absolute imports)
from checkpoint_sanitize import (
    _reject_dotdot,
    _sanitize_workflow_id,
    _sanitize_step_id,
)
from checkpoint_redact import (
    _default_redact_patterns,
    _redact_snapshot,
    migrate,
)
from checkpoint_core import (
    save,
    load,
    _to_checkpoint_state,
    _checkpoints_root,
    _load_json,
    _save_json,
    _repo_root,
    CHECKPOINTS_DIR,
    REPAIR_MEMORY_FILE,
    _safe_ckpt_path,
)
from checkpoint_workflow import (
    _load_workflow,
    _build_downstream_map,
    _dependencies_for,
)
from checkpoint_cli import (
    cmd_save,
    cmd_restore,
    cmd_list,
    main,
    _find_latest_checkpoint,
    _find_safe_checkpoint_before,
    _sanitize_step_id,
)

# Backwards-compat: expose everything that old code might import
__all__ = [
    # Sanitize
    "_reject_dotdot",
    "_sanitize_workflow_id",
    "_sanitize_step_id",
    # Redact/migrate
    "_default_redact_patterns",
    "_redact_snapshot",
    "migrate",
    # Core
    "save",
    "load",
    "_to_checkpoint_state",
    "_checkpoints_root",
    "_load_json",
    "_save_json",
    "_repo_root",
    "CHECKPOINTS_DIR",
    "REPAIR_MEMORY_FILE",
    # Workflow
    "_load_workflow",
    "_build_downstream_map",
    "_dependencies_for",
    # CLI
    "cmd_save",
    "cmd_restore",
    "cmd_list",
    "main",
    "_find_latest_checkpoint",
    "_find_safe_checkpoint_before",
    "_safe_ckpt_path",
]


if __name__ == "__main__":
    sys.exit(main())