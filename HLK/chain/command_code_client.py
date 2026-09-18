"""DEPRECATED: moved to HLK/chain/command_code_client — canonical source.
This file is a thin re-export shim for backward compat (explicit imports, no wildcard). Edit HLK/chain/command_code_client.py instead."""
from HLK.chain.command_code_client import CCConfig, CCResponse, CIRCUIT_BREAKER_COOLDOWN_SECONDS, DEFAULT_CC_BIN, DEFAULT_CIRCUIT_BREAKER_THRESHOLD, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, chat, parallel_chat, pick_cross_model, reset_circuit_breaker  # noqa: F401
