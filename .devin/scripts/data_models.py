#!/usr/bin/env python3
"""data_models.py — shared Pydantic models cho toàn bộ AHD harness.

Mục đích: định nghĩa một lần toàn bộ schema dùng chung giữa các component
(.devin/scripts/ và .devin/hooks/) để tránh trùng lặp và đảm bảo resource
constraints theo §5.5 của SOLUTION_DESIGN.md.

Quy tắc ràng buộc tài nguyên:
- String field dùng Field(max_length=...)
- List field dùng Field(max_length=...) (giới hạn số phần tử trong Pydantic v2)
- Numeric dùng Field(ge=..., le=...)
- dict[str, Any] không dùng Field mà validate qua @field_validator (≤64 keys,
  string values ≤10000 chars).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Cấu hình cho phép alias (vd pass_ alias "pass") và từ chối field thừa
model_config = ConfigDict(populate_by_name=True, extra="forbid")

_MAX_DICT_KEYS = 64
_MAX_STRING_VALUE = 10000


def _validate_dict_size(value: Any) -> Any:
    """Validator dùng chung: dict ≤64 keys, string values ≤10000 chars."""
    if not isinstance(value, dict):
        return value
    if len(value) > _MAX_DICT_KEYS:
        raise ValueError(f"dict vượt quá {_MAX_DICT_KEYS} keys")

    def _check_string_values(obj: Any) -> None:
        if isinstance(obj, str) and len(obj) > _MAX_STRING_VALUE:
            raise ValueError(f"string value vượt quá {_MAX_STRING_VALUE} chars")
        if isinstance(obj, dict):
            for v in obj.values():
                _check_string_values(v)
        if isinstance(obj, list):
            for item in obj:
                _check_string_values(item)

    _check_string_values(value)
    return value


# --- Context & Token Efficiency ---
class Chunk(BaseModel):
    """Một đoạn (chunk) trong substrate để lắp ráp viewport."""
    model_config = model_config

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
        return _validate_dict_size(v)


class Viewport(BaseModel):
    """Viewport: tập hợp top-K chunk relevant với query, fit trong budget tokens."""
    model_config = model_config

    chunks: list[Chunk] = Field(max_length=100)
    tokens: int = Field(ge=0, le=200000)
    source_hashes: list[str] = Field(max_length=100)
    budget_tokens: int = Field(ge=1, le=200000)
    query: str = Field(max_length=2000)


class Turn(BaseModel):
    """Một lượt trong conversation/history."""
    model_config = model_config

    role: Literal["user", "assistant", "system", "tool"]
    content: str = Field(max_length=20000)
    tokens: int = Field(ge=0, le=100000)
    timestamp: datetime
    tool_call_id: Optional[str] = Field(default=None, max_length=128)


class ToolDef(BaseModel):
    """Định nghĩa tool (function schema) cho model."""
    model_config = model_config

    name: str = Field(max_length=128)
    description: str = Field(max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list, max_length=64)
    profile: Literal["full", "conservative"] = "full"

    @field_validator("parameters")
    @classmethod
    def _check_parameters(cls, v: Any) -> Any:
        return _validate_dict_size(v)


# --- Hierarchical Swarm ---
class Order(BaseModel):
    """Một lệnh (order) trong SwarmSpec gửi cho worker."""
    model_config = model_config

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
        return _validate_dict_size(v)


class SwarmSpec(BaseModel):
    """Spec điều phối nhiều worker song song theo DAG."""
    model_config = model_config

    run_id: str = Field(max_length=128)
    orders: list[Order] = Field(max_length=50)
    max_parallel: int = Field(default=5, ge=1, le=16)
    created_at: datetime


class WorkerResult(BaseModel):
    """Kết quả trả về từ một worker."""
    model_config = model_config

    order_id: str = Field(max_length=128)
    worker_id: str = Field(max_length=128)
    status: Literal["success", "failed", "retry"]
    artifacts: list[str] = Field(default_factory=list, max_length=50)
    error: Optional[str] = Field(default=None, max_length=2000)
    duration_ms: int = Field(ge=0, le=86400000)
    cost_usd: float = Field(ge=0.0, le=100.0)


class StepVerdict(BaseModel):
    """Đánh giá từng bước trong Verdict."""
    model_config = model_config

    step_id: str = Field(max_length=128)
    ok: bool
    reason: str = Field(max_length=2000)
    severity: Literal["info", "warn", "error"] = "info"


class Verdict(BaseModel):
    """Phán quyết tổng hợp của agent-as-judge."""
    model_config = model_config

    pass_: bool = Field(alias="pass")
    per_step: list[StepVerdict] = Field(default_factory=list, max_length=200)
    feedback: str = Field(max_length=4000)
    retry_orders: list[Order] = Field(default_factory=list, max_length=50)
    judge_seed: int = Field(ge=0, le=2147483647)


# --- Durable Execution ---
class SideEffect(BaseModel):
    """Ghi nhận một side-effect trong ledger."""
    model_config = model_config

    key: str = Field(max_length=128)
    kind: Literal["file_write", "git_op", "external_call"]
    target: str = Field(max_length=512)
    hash: str = Field(max_length=128)
    timestamp: datetime
    result_status: Literal["success", "failed", "skipped"]


class ExternalHandle(BaseModel):
    """Tham chiếu đến tài nguyên bên ngoài (URL, API, MCP)."""
    model_config = model_config

    handle_id: str = Field(max_length=128)
    kind: Literal["url", "api", "mcp"]
    url: str = Field(max_length=2048)
    method: Optional[str] = Field(default=None, max_length=16)
    allowlisted: bool
    ssrf_checked: bool
    last_status: Optional[int] = Field(default=None, ge=100, le=599)


class CheckpointState(BaseModel):
    """Trạng thái checkpoint versioned, bao gồm conversation, side-effect ledger,
    metadata và external handles."""
    model_config = model_config

    version: int = Field(ge=2, le=100)
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
        return _validate_dict_size(v)


class IdempotencyEntry(BaseModel):
    """Một bản ghi idempotency ledger."""
    model_config = model_config

    key: str = Field(pattern=r"^[a-z0-9_-]{1,64}$", max_length=64)
    run_id: str = Field(max_length=128)
    result_hash: str = Field(max_length=128)
    result_status: Literal["success", "failed", "skipped"]
    timestamp: datetime


# --- Evaluation & Standards ---
class ABCReport(BaseModel):
    """Kết quả Agentic Benchmark Checklist."""
    model_config = model_config

    task_valid: bool
    outcome_valid: bool
    process_score: float = Field(ge=0.0, le=1.0)
    judge_verdict: str = Field(max_length=4000)
    pass_: bool = Field(alias="pass")
    judge_seed: int = Field(ge=0, le=2147483647)
    run_id: str = Field(max_length=128)


class RewardScore(BaseModel):
    """Điểm sau khi áp dụng reward shaping."""
    model_config = model_config

    base_score: float = Field(ge=-100.0, le=100.0)
    shaped_score: float = Field(ge=-100.0, le=100.0)
    cost_penalty: float = Field(ge=-100.0, le=100.0)
    security_penalty: float = Field(ge=-100.0, le=100.0)
    quality_bonus: float = Field(ge=-100.0, le=100.0)
    final: float = Field(ge=-100.0, le=100.0)


class Exploit(BaseModel):
    """Khai thác từ BenchJack red-team feed."""
    model_config = model_config

    exploit_type: Literal["padding", "metric_gaming", "shortcut", "reward_hack"]
    description: str = Field(max_length=2000)
    detected: bool
    penalty: float = Field(ge=-100.0, le=100.0)
    evidence: str = Field(max_length=4000)


# --- Cognitive Scaffolding ---
class ModelProfile(BaseModel):
    """Profile năng lực và ngân sách của một model."""
    model_config = model_config

    name: str = Field(max_length=64)
    context_budget: int = Field(ge=1024, le=1000000)
    role_split: dict[Literal["summarizer", "main", "corrector"], float] = Field(
        default_factory=dict
    )
    tool_profile: Literal["full", "conservative"] = "full"
    k_chunks: int = Field(default=8, ge=1, le=100)

    @field_validator("role_split")
    @classmethod
    def _check_role_split(cls, v: Any) -> Any:
        return _validate_dict_size(v)


class CoT(BaseModel):
    """Chain-of-Thought được tổng hợp cho model nhỏ."""
    model_config = model_config

    problem: str = Field(max_length=4000)
    steps: list[str] = Field(default_factory=list, max_length=50)
    tokens: int = Field(ge=0, le=200000)
    model_profile: str = Field(max_length=64)


class CRVScore(BaseModel):
    """Cognitive Load / Reasoning Validation score."""
    model_config = model_config

    reasoning_load: float = Field(ge=0.0, le=1.0)
    coherence: float = Field(ge=0.0, le=1.0)
    critique: str = Field(max_length=4000)
    pass_: bool = Field(alias="pass")


class ReflectVerdict(BaseModel):
    """Kết quả reflection trước khi thực hiện action."""
    model_config = model_config

    action_id: str = Field(max_length=128)
    level: Literal["intra", "inter", "foresight"]
    block: bool
    reason: str = Field(max_length=2000)
    human_confirm_required: bool = False


class Action(BaseModel):
    """Một hành động cần được reflection gate đánh giá."""
    model_config = model_config

    id: str = Field(max_length=128)
    category: Literal[
        "read", "write", "delete", "force_push", "drop", "reset_hard", "external_call"
    ]
    target: str = Field(max_length=512)
    args: dict[str, Any] = Field(default_factory=dict)
    destructive: bool = False

    @field_validator("args")
    @classmethod
    def _check_args(cls, v: Any) -> Any:
        return _validate_dict_size(v)
