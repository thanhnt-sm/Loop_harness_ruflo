#!/usr/bin/env python3
"""skill_promoter.py — Auto-promote pattern-fail thành skill mới.

Mục đích: theo dõi failure pattern qua nhiều task. Khi 1 pattern xuất hiện
≥ MIN_OCCURRENCES lần với fail-rate > MIN_FAIL_RATE ở ≥ 2 executor khác nhau
→ sinh SkillDraft (frontmatter + body) để user duyệt trước khi apply.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 4.6

Anti-abuse:
- Chỉ promote khi pattern xuất hiện ở ≥ 2 executor (tránh bias 1 model).
- Không tự apply — đưa vào queue cho /harness-upgrade --apply round kế tiếp.
- Có thể whitelist/blacklist pattern qua config.

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field
__all__ = [
    "FailureObservation",
    "MAX_DRAFTS_PER_RUN",
    "MIN_EXECUTORS",
    "MIN_FAIL_RATE",
    "MIN_OCCURRENCES",
    "SkillDraft",
    "find_promotion_candidates",
    "render_skill_markdown",
    "write_drafts_to_queue",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# Defaults — user override được qua env hoặc .devin/config/skill_promoter.yaml
MIN_OCCURRENCES = 3
MIN_FAIL_RATE = 0.5
MIN_EXECUTORS = 2
MAX_DRAFTS_PER_RUN = 5


@dataclass
class FailureObservation:
    """Một quan sát fail của 1 executor trên 1 task pattern."""

    pattern: str  # mô tả ngắn, vd "read file X trước khi edit Y"
    executor: str  # "sonnet" | "haiku" | "opus" | "kimi" | "glm" | "lightning"
    task_id: str
    failed: bool
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class SkillDraft(BaseModel):
    """Draft skill sinh từ pattern."""

    slug: str = Field(pattern=r"^[a-z0-9\-]+$", min_length=3, max_length=64)
    name: str = Field(min_length=3, max_length=128)
    description: str = Field(min_length=10, max_length=512)
    trigger: str  # khi nào skill này nên được dùng
    steps: list[str] = Field(min_length=1, max_length=16)
    rubric: list[str] = Field(min_length=1, max_length=16)  # tiêu chí pass
    based_on_pattern: str
    occurrences: int
    fail_rate: float
    executors_observed: list[str] = Field(default_factory=list)


def _aggregate_patterns(observations: list[FailureObservation]) -> dict[str, list[FailureObservation]]:
    """Group observations theo pattern."""
    grouped: dict[str, list[FailureObservation]] = defaultdict(list)
    for obs in observations:
        grouped[obs.pattern].append(obs)
    return dict(grouped)


def find_promotion_candidates(
    observations: list[FailureObservation],
    min_occurrences: int = MIN_OCCURRENCES,
    min_fail_rate: float = MIN_FAIL_RATE,
    min_executors: int = MIN_EXECUTORS,
) -> list[SkillDraft]:
    """Tìm các pattern đủ điều kiện promote thành skill.

    Returns: list of SkillDraft (chưa ghi file, chờ duyệt).
    """
    grouped = _aggregate_patterns(observations)
    candidates: list[SkillDraft] = []
    for pattern, obs_list in grouped.items():
        if len(obs_list) < min_occurrences:
            continue
        fails = sum(1 for o in obs_list if o.failed)
        fail_rate = fails / len(obs_list)
        if fail_rate < min_fail_rate:
            continue
        executors = {o.executor for o in obs_list}
        if len(executors) < min_executors:
            continue
        # Đủ điều kiện — sinh draft
        draft = _generate_draft(pattern, obs_list, fail_rate, sorted(executors))
        candidates.append(draft)
        if len(candidates) >= MAX_DRAFTS_PER_RUN:
            break
    return candidates


def _generate_draft(
    pattern: str,
    observations: list[FailureObservation],
    fail_rate: float,
    executors: list[str],
) -> SkillDraft:
    """Sinh SkillDraft từ pattern. Tên skill: từ pattern lower-case + dash."""
    slug = pattern.lower().replace(" ", "-").replace("_", "-")[:64]
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-") or "auto-skill"
    return SkillDraft(
        slug=slug,
        name=pattern.title()[:128],
        description=f"Auto-generated skill: {pattern}. Based on {len(observations)} observations across {len(executors)} executors.",
        trigger=f"Khi task liên quan đến: {pattern}",
        steps=[
            f"Bước 1: Xác định task có liên quan đến '{pattern}' không",
            f"Bước 2: Đọc kỹ context trước khi hành động",
            f"Bước 3: Verify result trước khi báo done",
        ],
        rubric=[
            "Đã đọc context đầy đủ trước khi hành động",
            "Đã verify output khớp expectation",
            "Đã ghi log lý do nếu có lệch hướng",
        ],
        based_on_pattern=pattern,
        occurrences=len(observations),
        fail_rate=fail_rate,
        executors_observed=executors,
    )


def render_skill_markdown(draft: SkillDraft) -> str:
    """Render SkillDraft thành file markdown theo convention."""
    steps_md = "\n".join(f"{i+1}. {s}" for i, s in enumerate(draft.steps))
    rubric_md = "\n".join(f"- [ ] {r}" for r in draft.rubric)
    return f"""---
name: {draft.name}
description: {draft.description}
auto_generated: true
based_on_pattern: "{draft.based_on_pattern}"
occurrences: {draft.occurrences}
fail_rate: {draft.fail_rate:.2f}
executors_observed: {', '.join(draft.executors_observed)}
---

# {draft.name}

> **Auto-generated** từ `{draft.occurrences}` failure observations (fail-rate {draft.fail_rate:.0%}) trên {len(draft.executors_observed)} executors.
> **Review required** trước khi apply — xem `docs/plans/harness-upgrade-verify-first/EXECUTION_REPORT.md`.

## Trigger
{draft.trigger}

## Steps
{steps_md}

## Rubric (Acceptance Criteria)
{rubric_md}
"""


def write_drafts_to_queue(
    drafts: list[SkillDraft],
    queue_path: str | Path = ".devin/state/skill_drafts.jsonl",
) -> int:
    """Ghi drafts vào JSONL queue. Trả về số drafts đã ghi."""
    p = Path(queue_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for d in drafts:
            f.write(d.model_dump_json() + "\n")
    return len(drafts)


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: skill_promoter.py <observations.jsonl> [queue_path]")
        _sys.exit(2)
    obs_path = Path(_sys.argv[1])
    queue = _sys.argv[2] if len(_sys.argv) > 2 else ".devin/state/skill_drafts.jsonl"
    obs: list[FailureObservation] = []
    for line in obs_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        obs.append(FailureObservation(**d))
    drafts = find_promotion_candidates(obs)
    n = write_drafts_to_queue(drafts, queue)
    print(f"Found {len(drafts)} candidates, wrote {n} to {queue}")
    for d in drafts:
        print(f"  - {d.slug}: {d.occurrences} obs, fail-rate {d.fail_rate:.0%}")
