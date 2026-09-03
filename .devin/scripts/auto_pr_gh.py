"""DEPRECATED: moved to HLK/chain/auto_pr_gh — canonical source.
This file is a thin re-export shim for backward compat (explicit imports, no wildcard). Edit HLK/chain/auto_pr_gh.py instead."""
from HLK.chain.auto_pr_gh import DEFAULT_BASE, DEFAULT_GH_BIN, DEFAULT_TIMEOUT, GHResult, check_auth_status, check_ci, check_gh_installed, check_repo, create_pr, live_auto_merge, merge_pr, preflight, scan_diff_for_secrets, wait_for_ci  # noqa: F401
