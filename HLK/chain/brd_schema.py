#!/usr/bin/env python3
"""brd_schema.py — Pydantic models cho BRD (Business Requirements Document).

Mục đích: schema cứng cho BRD/FR/NFR, ép convention trước khi vào Scenario
Designer. Đảm bảo mọi FR có actor + acceptance criteria, mọi NFR có metric
+ threshold đo được.

Usage:
    from brd_schema import BRD, FunctionalRequirement, validate_brd_dict
    brd = BRD.model_validate(brd_dict)

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
__all__ = [
    "Actor",
    "BRD",
    "FunctionalRequirement",
    "NonFunctionalRequirement",
    "validate_brd_dict",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

Priority = Literal["must", "should", "could", "wont"]
NFRType = Literal["perf", "security", "ux", "scalability", "reliability"]
Permission = Literal["read", "write", "admin"]


class Actor(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=256)
    permissions: list[Permission] = Field(default_factory=lambda: ["read"])

    @field_validator("name")
    @classmethod
    def _no_whitespace(cls, v: str) -> str:
        if any(c.isspace() for c in v):
            raise ValueError("Actor.name không được chứa whitespace")
        return v


class FunctionalRequirement(BaseModel):
    id: str = Field(pattern=r"^FR-[0-9]{3,}$")
    actor: str = Field(min_length=1, max_length=64)
    use_case: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=10, max_length=2000)
    priority: Priority
    acceptance_criteria: list[str] = Field(min_length=1, max_length=32)

    @field_validator("acceptance_criteria")
    @classmethod
    def _criteria_non_empty(cls, v: list[str]) -> list[str]:
        for c in v:
            if len(c.strip()) < 5:
                raise ValueError(f"Acceptance criterion quá ngắn: {c!r}")
        return v


class NonFunctionalRequirement(BaseModel):
    id: str = Field(pattern=r"^NFR-[0-9]{3,}$")
    type: NFRType
    metric: str = Field(min_length=3, max_length=256)
    threshold: str = Field(min_length=1, max_length=128)

    @field_validator("metric")
    @classmethod
    def _metric_measurable(cls, v: str) -> str:
        low = v.lower()
        measurable = [
            "ms", "p95", "p99", "rps", "qps", "mb", "gb", "%", "count", "score", "rate",
            "algorithm", "time", "throughput", "latency", "memory", "cpu",
        ]
        if not any(m in low for m in measurable):
            raise ValueError(
                f"NFR.metric phải chứa đơn vị đo được (vd ms, p95, %, count, score, algorithm). Got: {v!r}"
            )
        return v


class BRD(BaseModel):
    """Business Requirements Document — đầu vào cho verify-first chain."""

    title: str = Field(min_length=3, max_length=256)
    business_goal: str = Field(min_length=10, max_length=2000)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    owner: str = Field(min_length=1, max_length=128)
    status: Literal["draft", "review", "approved"] = "draft"
    actors: list[Actor] = Field(min_length=1, max_length=32)
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list, max_length=256)
    non_functional_requirements: list[NonFunctionalRequirement] = Field(default_factory=list, max_length=64)
    constraints: list[str] = Field(default_factory=list, max_length=32)
    out_of_scope: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _validate_cross_refs(self) -> "BRD":
        actor_names = {a.name for a in self.actors}
        for fr in self.functional_requirements:
            if fr.actor not in actor_names:
                raise ValueError(
                    f"{fr.id} reference actor {fr.actor!r} không tồn tại. "
                    f"Actors: {sorted(actor_names)}"
                )
        # FR ID uniqueness
        fr_ids = [fr.id for fr in self.functional_requirements]
        if len(fr_ids) != len(set(fr_ids)):
            dup = [i for i in fr_ids if fr_ids.count(i) > 1]
            raise ValueError(f"FR IDs trùng lặp: {sorted(set(dup))}")
        nfr_ids = [nfr.id for nfr in self.non_functional_requirements]
        if len(nfr_ids) != len(set(nfr_ids)):
            dup = [i for i in nfr_ids if nfr_ids.count(i) > 1]
            raise ValueError(f"NFR IDs trùng lặp: {sorted(set(dup))}")
        return self


def validate_brd_dict(data: dict[str, Any]) -> BRD:
    """Helper: validate dict thô thành BRD, raise ValueError nếu thiếu field."""
    return BRD.model_validate(data)
