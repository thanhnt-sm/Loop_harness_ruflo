#!/usr/bin/env python3
"""
apply_ahd_patch.py — Entry point cho surgical cherry-pick AHD commits từ upstream.

AHD = Agent Harness Deploy — upstream engine từ masteryee-labs/Tool.Agent-Harness-Deploy.
Surgical cherry-pick = apply từng commit riêng lẻ, không bulk merge, để kiểm soát impact.

Cách dùng:
    python .devin/scripts/apply_ahd_patch.py --upstream <path-to-clone> --since YYYY-MM-DD --until YYYY-MM-DD [--dry-run] [--auto-commit] [--worktree DIR] [--max-commits N]

Ví dụ:
    python .devin/scripts/apply_ahd_patch.py --upstream /tmp/ahd-upstream --since 2026-07-15 --until 2026-08-10
    python .devin/scripts/apply_ahd_patch.py --upstream . --since 2026-07-15 --until 2026-08-10 --max-commits 5
"""
from __future__ import annotations

import sys

# Re-export all public APIs from submodules for backward compatibility
from apply_ahd_map import (
    PATH_MAP,
    PROTECTED_PATTERNS,
    SKIP_UPSTREAM_DIRS,
    RISKY_NEW_DIRS,
    REPO_ROOT,
    TRACKER_PATH,
    map_path,
    is_protected,
    is_upstream_skip,
    is_risky_new,
    get_protected_files,
    _glob_match,
)

from apply_ahd_normalize import (
    normalize_text_after_merge,
    _text_replacements,
    _normalize_json,
    _normalize_py,
)

from apply_ahd_merge import (
    merge_3way,
)

from apply_ahd_verify import (
    verify,
    run_cmd,
)

from apply_ahd_commit import (
    commit_changes,
    rollback_patched_files,
    snapshot_rollback,
    record_ahd_apply,
    _audit_log,
)

from apply_ahd_apply import (
    apply_commit,
    get_commits,
    get_changed_files,
    get_file_at_rev,
    validate_sha,
)

from apply_ahd_cli import (
    main,
    guard_main_branch,
    setup_feature_branch,
    setup_worktree,
    stash_local_changes,
    pop_stash,
    validate_worktree_path,
)

if __name__ == "__main__":
    sys.exit(main())