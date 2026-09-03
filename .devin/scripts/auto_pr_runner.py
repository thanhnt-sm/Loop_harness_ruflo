"""DEPRECATED: moved to HLK/chain/auto_pr_runner — canonical source.
This file is a thin re-export shim for backward compat (explicit imports, no wildcard). Edit HLK/chain/auto_pr_runner.py instead."""
from HLK.chain.auto_pr_runner import AUDIT_LOG_PATH, DEFAULT_CONFIG_PATH, GateCheck, GateResult, GateVerdict, KILL_SWITCH_PATH, check_adversarial_consensus, check_coverage_matrix, check_fable_judge, check_llm_judge_rubric, check_rate_limit, is_kill_switch_active, load_config, rotate_audit_log, run_gates, should_auto_merge, write_audit_log  # noqa: F401
