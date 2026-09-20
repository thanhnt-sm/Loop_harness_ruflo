#!/usr/bin/env python3
"""rubric_generator.py — Sinh rubric cụ thể từ BRD/FR/NFR.

Mục đích: tự động tạo BinaryRubric (cho FR) + ScoreRubric (cho NFR) từ
BRD object. User có thể sửa file JSON trước khi execute.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 4.3

Generation strategy:
- FR priority="must" → BinaryRubric strict (ALL pass)
- FR priority="should" → BinaryRubric lenient (≥80% pass)
- FR priority="could" → BinaryRubric lenient (≥50% pass)
- FR priority="wont" → không sinh rubric
- NFR → ScoreRubric theo type (perf/security/ux/scalability/reliability)
- User override được bằng cách sửa file JSON trước execute

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from brd_schema import BRD, FunctionalRequirement, NonFunctionalRequirement  # noqa: E402
__all__ = [
    "BinaryCheck",
    "BinaryRubric",
    "ScoreRubric",
    "generate_rubric_file",
    "generate_rubrics",
]




# --- Rubric models ---


class BinaryCheck(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    assertion: str = Field(min_length=1, max_length=512)
    evidence: Literal["screenshot", "log", "json", "http"] = "log"


class BinaryRubric(BaseModel):
    rubric_id: str = Field(pattern=r"^RB-\d{3,}$")
    linked_fr: str = Field(pattern=r"^FR-\d{3,}$")
    type: Literal["binary"] = "binary"
    checks: list[BinaryCheck] = Field(min_length=1, max_length=32)
    pass_criteria: Literal["ALL", "AT_LEAST_80_PCT"] = "ALL"


class ScoreRubric(BaseModel):
    rubric_id: str = Field(pattern=r"^RB-\d{3,}$")
    linked_nfr: str = Field(pattern=r"^NFR-\d{3,}$")
    type: Literal["score"] = "score"
    metric: str = Field(min_length=1, max_length=256)
    scoring: dict[str, str] = Field(min_length=1, max_length=8)
    threshold: int = Field(ge=0, le=3)
    evidence: str = Field(min_length=1, max_length=512)


# --- Generation ---


_PRIORITY_TO_CRITERIA = {
    "must": "ALL",
    "should": "AT_LEAST_80_PCT",
    "could": "AT_LEAST_80_PCT",
}


_NFR_TYPE_SCORING = {
    "perf": {
        "0": "Fails metric by >2x threshold",
        "1": "Fails metric by 1.5-2x threshold",
        "2": "Within 1.5x of threshold",
        "3": "Meets or beats threshold",
    },
    "security": {
        "0": "Critical vulnerability detected",
        "1": "High-risk issue detected",
        "2": "Medium-risk, mitigated",
        "3": "No issues, follows best practice",
    },
    "ux": {
        "0": "Broken / unusable",
        "1": "Usable with confusion",
        "2": "Usable, minor friction",
        "3": "Clear, intuitive, delightful",
    },
    "scalability": {
        "0": "Cannot handle target load",
        "1": "Handles <50% target",
        "2": "Handles target with margin",
        "3": "Handles 2x target with margin",
    },
    "reliability": {
        "0": "Fails under normal load",
        "1": "Intermittent failures",
        "2": "Stable, rare edge failures",
        "3": "Stable under stress, graceful degradation",
    },
}


def _fr_idx(brd: BRD, fr_id: str) -> str:
    """Trả về index 3-chars số cho FR (FR-001 → '001')."""
    nums = [fr.id for fr in brd.functional_requirements]
    try:
        return f"{nums.index(fr_id) + 1:03d}"
    except ValueError:
        return "999"


def _nfr_idx(brd: BRD, nfr_id: str) -> str:
    nums = [n.id for n in brd.non_functional_requirements]
    try:
        return f"{nums.index(nfr_id) + 1:03d}"
    except ValueError:
        return "999"


def _generate_binary_for_fr(brd: BRD, fr: FunctionalRequirement) -> Optional[BinaryRubric]:
    if fr.priority == "wont":
        return None
    # Binary rubric dùng range 001-499
    rb_idx = f"{int(_fr_idx(brd, fr.id)):03d}"
    checks = [
        BinaryCheck(
            name=f"AC-{i+1}",
            assertion=ac,
            evidence="log",
        )
        for i, ac in enumerate(fr.acceptance_criteria)
    ]
    return BinaryRubric(
        rubric_id=f"RB-{rb_idx}",
        linked_fr=fr.id,
        type="binary",
        checks=checks,
        pass_criteria=_PRIORITY_TO_CRITERIA[fr.priority],  # type: ignore[arg-type]
    )


def _generate_score_for_nfr(brd: BRD, nfr: NonFunctionalRequirement) -> ScoreRubric:
    # Score rubric dùng range 500-999 để tránh collision với binary
    raw = int(_nfr_idx(brd, nfr.id))
    rb_idx = f"{raw + 500:03d}"
    scoring = _NFR_TYPE_SCORING.get(nfr.type, _NFR_TYPE_SCORING["ux"])
    return ScoreRubric(
        rubric_id=f"RB-{rb_idx}",
        linked_nfr=nfr.id,
        type="score",
        metric=nfr.metric,
        scoring=scoring,
        threshold=2,  # default: cần ≥2 (medium) để pass
        evidence=f"Đo {nfr.metric}, đối chiếu threshold: {nfr.threshold}",
    )


def generate_rubrics(brd: BRD) -> tuple[list[BinaryRubric], list[ScoreRubric]]:
    """Sinh tất cả rubrics từ BRD. Trả về (binary_rubrics, score_rubrics)."""
    binary = []
    for fr in brd.functional_requirements:
        rb = _generate_binary_for_fr(brd, fr)
        if rb is not None:
            binary.append(rb)
    score = [_generate_score_for_nfr(brd, nfr) for nfr in brd.non_functional_requirements]
    return binary, score


def generate_rubric_file(brd: BRD, out_path: str | Path) -> Path:
    """Sinh rubrics và ghi ra file JSON. Trả về path."""
    binary, score = generate_rubrics(brd)
    payload = {
        "brd_id": brd.title,
        "version": brd.version,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "binary_rubrics": [rb.model_dump() for rb in binary],
        "score_rubrics": [rb.model_dump() for rb in score],
    }
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 3:
        print("Usage: rubric_generator.py <BRD.json> <output.json>")
        _sys.exit(2)
    brd_path = Path(_sys.argv[1])
    out_path = Path(_sys.argv[2])
    brd = BRD.model_validate_json(brd_path.read_text(encoding="utf-8"))
    p = generate_rubric_file(brd, out_path)
    print(f"Generated: {p}")
