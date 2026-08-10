#!/usr/bin/env python3
"""Shared Pydantic data models cho toàn bộ AHD harness.

Tập trung 21 model dùng chung, có resource constraints (max_length, ge/le,
field validators cho dict) theo SOLUTION_DESIGN §5.5.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---- Helpers ----

def _validate_dict(v: Any, max_keys: int = 64, str_max_len: int = 10000) -> Any:
    """Kiểm tra dict: ≤max_keys key, key là str độ dài ≤64, str values ≤str_max_len."""
    if not isinstance(v, dict):
        return v
    if len(v) > max_keys:
        raise ValueError(f"dict vượt quá {max_keys} keys")
    for k, val in v.items():
        if not isinstance(k, str):
            raise ValueError("dict key phải là str")
        if len(k) > 64:
            raise ValueError("dict key quá dài (max 64)")
        if isinstance(val, str) and len(val) > str_max_len:
            raise ValueError(f"dict string value quá dài (max {str_max_len})")
    return v


# ---- Context & Token Efficiency ----

class Chunk(BaseModel):
    id: str = Field(max_length=128)
    content: str = Field(max_length=10000)
    source: str = Field(max_length=256)
    tokens: int = Field(ge=0, le=100000)
    hash: str = Field(max_length=128)
    embedding: Optional[list[float]] = Field(default=None, max_length=3072)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _check_metadata(cls, v: Any) -> Any:
        return _validate_dict(v)


class Viewport(BaseModel):
    chunks: list[Chunk] = Field(max_length=100)
    tokens: int = Field(ge=0, le=200000)
    source_hashes: list[str] = Field(max_length=100)
    budget_tokens: int = Field(ge=1, le=200000)
    query: str = Field(max_length=2000)


class Turn(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str = Field(max_length=20000)
    tokens: int = Field(ge=0, le=100000)
    timestamp: datetime
    tool_call_id: Optional[str] = Field(default=None, max_length=128)


class ToolDef(BaseModel):
    name: str = Field(max_length=128)
    description: str = Field(max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list, max_length=64)
    profile: Literal["full", "conservative"] = "full"

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("parameters")
    @classmethod
    def _check_parameters(cls, v: Any) -> Any:
        return _validate_dict(v)


# ---- Hierarchical Swarm ----

class Order(BaseModel):
    id: str = Field(max_length=128)
    worker_id: str = Field(max_length=128)
    task: str = Field(max_length=4000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list, max_length=50)
    write_set: list[str] = Field(default_factory=list, max_length=50)
    idempotency_key: str = Field(pattern=r"^[a-z0-9_-]{1,64}$", max_length=64)
    depends_on: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("inputs")
    @classmethod
    def _check_inputs(cls, v: Any) -> Any:
        return _validate_dict(v)


class SwarmSpec(BaseModel):
    run_id: str = Field(max_length=128)
    orders: list[Order] = Field(max_length=50)
    max_parallel: int = Field(default=5, ge=1, le=16)
    created_at: datetime


class WorkerResult(BaseModel):
    order_id: str = Field(max_length=128)
    worker_id: str = Field(max_length=128)
    status: Literal["success", "failed", "retry"] = "success"
    artifacts: list[str] = Field(default_factory=list, max_length=50)
    error: Optional[str] = Field(default=None, max_length=2000)
    duration_ms: int = Field(default=0, ge=0, le=86400000)
    cost_usd: float = Field(default=0.0, ge=0.0, le=100.0)


class StepVerdict(BaseModel):
    step_id: str = Field(max_length=128)
    ok: bool
    reason: str = Field(max_length=2000)
    severity: Literal["info", "warn", "error"] = "info"


class Verdict(BaseModel):
    pass_: bool = Field(alias="pass")
    per_step: list[StepVerdict] = Field(default_factory=list, max_length=200)
    feedback: str = Field(default="", max_length=4000)
    retry_orders: list[Order] = Field(default_factory=list, max_length=50)
    judge_seed: int = Field(default=0, ge=0, le=2147483647)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# ---- Durable Execution ----

class SideEffect(BaseModel):
    key: str = Field(default="", max_length=128)
    kind: Literal["file_write", "git_op", "external_call"] = "file_write"
    target: str = Field(default="", max_length=512)
    hash: str = Field(default="", max_length=128)
    timestamp: Optional[datetime] = Field(default=None)
    result_status: Literal["success", "failed", "skipped"] = "success"


class ExternalHandle(BaseModel):
    handle_id: str = Field(default="", max_length=128)
    kind: Literal["url", "api", "mcp"] = "url"
    url: str = Field(default="", max_length=2048)
    method: Optional[str] = Field(default=None, max_length=16)
    allowlisted: bool = False
    ssrf_checked: bool = False
    last_status: Optional[int] = Field(default=None, ge=100, le=599)


class CheckpointState(BaseModel):
    version: int = Field(default=2, ge=2, le=100)
    run_id: str = Field(max_length=128)
    conversation: list[Turn] = Field(default_factory=list, max_length=200)
    side_effects_ledger: list[SideEffect] = Field(default_factory=list, max_length=500)
    run_metadata: dict[str, Any] = Field(default_factory=dict)
    external_handles: list[ExternalHandle] = Field(default_factory=list, max_length=64)
    timestamp: datetime
    step_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$", max_length=64)

    @field_validator("run_metadata")
    @classmethod
    def _check_run_metadata(cls, v: Any) -> Any:
        return _validate_dict(v)


class IdempotencyEntry(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_-]{1,64}$", max_length=64)
    run_id: str = Field(max_length=128)
    result_hash: str = Field(max_length=128)
    result_status: Literal["success", "failed", "skipped"]
    timestamp: datetime


# ---- Evaluation & Standards ----

class ABCReport(BaseModel):
    task_valid: bool = False
    outcome_valid: bool = False
    process_score: float = Field(default=0.0, ge=0.0, le=1.0)
    judge_verdict: str = Field(default="", max_length=4000)
    pass_: bool = Field(default=False, alias="pass")
    judge_seed: int = Field(default=0, ge=0, le=2147483647)
    run_id: str = Field(default="", max_length=128)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class RewardScore(BaseModel):
    base_score: float = Field(default=0.0, ge=-100.0, le=100.0)
    shaped_score: float = Field(default=0.0, ge=-100.0, le=100.0)
    cost_penalty: float = Field(default=0.0, ge=-100.0, le=100.0)
    security_penalty: float = Field(default=0.0, ge=-100.0, le=100.0)
    quality_bonus: float = Field(default=0.0, ge=-100.0, le=100.0)
    final: float = Field(default=0.0, ge=-100.0, le=100.0)


class Exploit(BaseModel):
    exploit_type: Literal["padding", "metric_gaming", "shortcut", "reward_hack"] = "padding"
    description: str = Field(default="", max_length=2000)
    detected: bool = False
    penalty: float = Field(default=0.0, ge=-100.0, le=100.0)
    evidence: str = Field(default="", max_length=4000)


# ---- Cognitive Scaffolding ----

class ModelProfile(BaseModel):
    name: str = Field(max_length=64)
    context_budget: int = Field(ge=1024, le=1000000)
    role_split: dict[Literal["summarizer", "main", "corrector"], float] = Field(default_factory=dict)
    tool_profile: Literal["full", "conservative"] = "full"
    k_chunks: int = Field(default=8, ge=1, le=100)

    @field_validator("role_split")
    @classmethod
    def _check_role_split(cls, v: Any) -> Any:
        return _validate_dict(v, max_keys=3)


class CoT(BaseModel):
    problem: str = Field(default="", max_length=4000)
    steps: list[str] = Field(default_factory=list, max_length=50)
    tokens: int = Field(default=0, ge=0, le=200000)
    model_profile: str = Field(default="default", max_length=64)


class CRVScore(BaseModel):
    reasoning_load: float = Field(default=0.0, ge=0.0, le=1.0)
    coherence: float = Field(default=0.0, ge=0.0, le=1.0)
    critique: str = Field(default="", max_length=4000)
    pass_: bool = Field(default=False, alias="pass")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ReflectVerdict(BaseModel):
    action_id: str = Field(default="", max_length=128)
    level: Literal["intra", "inter", "foresight"] = "intra"
    block: bool = False
    reason: str = Field(default="", max_length=2000)
    human_confirm_required: bool = False


class Action(BaseModel):
    id: str = Field(max_length=128)
    category: Literal["read", "write", "delete", "force_push", "drop", "reset_hard", "external_call"]
    target: str = Field(max_length=512)
    args: dict[str, Any] = Field(default_factory=dict)
    destructive: bool = False

    @field_validator("args")
    @classmethod
    def _check_args(cls, v: Any) -> Any:
        return _validate_dict(v)


__all__ = [
    "Chunk",
    "Viewport",
    "Turn",
    "ToolDef",
    "Order",
    "SwarmSpec",
    "WorkerResult",
    "StepVerdict",
    "Verdict",
    "SideEffect",
    "ExternalHandle",
    "CheckpointState",
    "IdempotencyEntry",
    "ABCReport",
    "RewardScore",
    "Exploit",
    "ModelProfile",
    "CoT",
    "CRVScore",
    "ReflectVerdict",
    "Action",
]
