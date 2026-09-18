"""DEPRECATED: moved to HLK/chain/judge_config — canonical source.
This file is a thin re-export shim for backward compat (explicit imports, no wildcard). Edit HLK/chain/judge_config.py instead."""
from HLK.chain.judge_config import AgreementPolicy, AuditConfig, DEFAULT_CONFIG_PATH, JudgeConfig, RedteamConfig, get_judge_model, load_judge_config, pick_judge_for_audit_path, should_spawn_redteam  # noqa: F401
