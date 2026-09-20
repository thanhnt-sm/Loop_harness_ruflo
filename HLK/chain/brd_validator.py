#!/usr/bin/env python3
"""brd_validator.py — Parse BRD.md (markdown) thành BRD object + validate.

Mục đích: cho phép user viết BRD theo template `docs/templates/BRD.md` rồi
auto-parse sang structured BRD object. Nếu parse fail → in lỗi rõ ràng
(actor missing, FR không có acceptance criteria, v.v.) để user sửa ngay.

Usage:
    from brd_validator import parse_brd_file, parse_brd_text
    brd = parse_brd_file("docs/plans/foo/BRD.md")
    print(brd.functional_requirements)

Parsing strategy: regex-based, đủ cho template format. Không phụ thuộc AST
markdown parser (giữ dependency nhỏ).

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from brd_schema import (  # noqa: E402
    Actor,
    BRD,
    FunctionalRequirement,
    NonFunctionalRequirement,
)

__all__ = [
    "parse_brd_file",
    "parse_brd_text",
]


_FR_RE = re.compile(r"^###\s+(FR-\d+):\s*(.+)$", re.MULTILINE)
_NFR_RE = re.compile(r"^###\s+(NFR-\d+):\s*(.+)$", re.MULTILINE)
_ACTOR_ROW_RE = re.compile(
    r"^\|\s*`?([^|`]+)`?\s*\|\s*`?([^|`]+)`?\s*\|\s*`?([^|`]+)`?\s*\|",
    re.MULTILINE,
)
_CHECKBOX_RE = re.compile(r"^\s*-\s*\[\s*[xX ]\s*\]\s*(.+)$", re.MULTILINE)


def _parse_actors(text: str) -> list[Actor]:
    """Parse bảng actors từ section '## 2. Actors'."""
    actors: list[Actor] = []
    for m in _ACTOR_ROW_RE.finditer(text):
        name, role, perm = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if name.startswith("---") or name.lower() == "actor":
            continue
        if perm not in ("read", "write", "admin"):
            perm = "read"  # graceful fallback
        actors.append(Actor(name=name, role=role, permissions=[perm]))  # type: ignore[list-item]
    return actors


def _parse_functional_requirements(text: str) -> list[FunctionalRequirement]:
    """Parse từng ### FR-XXX section. Mỗi section có:
    - **Actor**: <name>
    - **Use case**: <name>
    - **Description**: <text>
    - **Priority**: <must|should|could|wont>
    - **Acceptance criteria**: <list>
    """
    frs: list[FunctionalRequirement] = []
    matches = list(_FR_RE.finditer(text))
    for i, m in enumerate(matches):
        fr_id = m.group(1)
        section = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        actor_m = re.search(r"\*\*Actor\*\*:\s*(.+)", section)
        uc_m = re.search(r"\*\*Use case\*\*:\s*(.+)", section)
        desc_m = re.search(r"\*\*Description\*\*:\s*(.+)", section)
        prio_m = re.search(r"\*\*Priority\*\*:\s*(must|should|could|wont)", section, re.IGNORECASE)
        ac_section = re.search(
            r"\*\*Acceptance criteria\*\*:\s*(.+?)(?=\n###|\Z)", section, re.DOTALL
        )
        if not (actor_m and uc_m and desc_m and prio_m and ac_section):
            raise ValueError(
                f"{fr_id} thiếu một trong các trường: Actor/Use case/Description/Priority/Acceptance criteria"
            )
        criteria = [c.strip() for c in _CHECKBOX_RE.findall(ac_section.group(1))]
        if not criteria:
            raise ValueError(f"{fr_id} chưa có acceptance criteria nào (cần ≥1)")
        frs.append(
            FunctionalRequirement(
                id=fr_id,
                actor=actor_m.group(1).strip(),
                use_case=uc_m.group(1).strip(),
                description=desc_m.group(1).strip(),
                priority=prio_m.group(1).lower(),  # type: ignore[arg-type]
                acceptance_criteria=criteria,
            )
        )
    return frs


def _parse_nfrs(text: str) -> list[NonFunctionalRequirement]:
    nfrs: list[NonFunctionalRequirement] = []
    matches = list(_NFR_RE.finditer(text))
    for i, m in enumerate(matches):
        nfr_id = m.group(1)
        section = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        type_m = re.search(r"\*\*Type\*\*:\s*(perf|security|ux|scalability|reliability)", section, re.IGNORECASE)
        metric_m = re.search(r"\*\*Metric\*\*:\s*(.+)", section)
        threshold_m = re.search(r"\*\*Threshold\*\*:\s*(.+)", section)
        if not (type_m and metric_m and threshold_m):
            raise ValueError(f"{nfr_id} thiếu Type/Metric/Threshold")
        nfrs.append(
            NonFunctionalRequirement(
                id=nfr_id,
                type=type_m.group(1).lower(),  # type: ignore[arg-type]
                metric=metric_m.group(1).strip(),
                threshold=threshold_m.group(1).strip(),
            )
        )
    return nfrs


def parse_brd_text(text: str) -> BRD:
    """Parse markdown text thành BRD. Raise ValueError nếu thiếu trường bắt buộc."""
    title_m = re.search(r"^#\s+BRD\s*[—-]\s*(.+)$", text, re.MULTILINE)
    if not title_m:
        raise ValueError("Thiếu tiêu đề '# BRD — <title>'")
    title = title_m.group(1).strip()
    # Bỏ slug prefix nếu có dạng "(<slug>)"
    title = re.sub(r"^\([^)]+\)\s*", "", title)

    bg_m = re.search(r"^##\s+1\.\s+Business Goal\s*\n+(.+?)(?=\n##|\Z)", text, re.MULTILINE | re.DOTALL)
    version_m = re.search(r"\*\*Version\*\*:\s*`?(\d+\.\d+\.\d+)`?", text)
    owner_m = re.search(r"\*\*Owner\*\*:\s*`?([^`\n]+)`?", text)
    status_m = re.search(r"\*\*Status\*\*:\s*`?(draft|review|approved)`?", text, re.IGNORECASE)

    if not (bg_m and version_m and owner_m):
        raise ValueError("Thiếu Business Goal / Version / Owner ở frontmatter")
    business_goal = bg_m.group(1).strip()
    if business_goal.startswith("<!--") and business_goal.endswith("-->"):
        business_goal = "TODO: business_goal chưa điền"

    actors = _parse_actors(text)
    frs = _parse_functional_requirements(text)
    nfrs = _parse_nfrs(text)

    return BRD(
        title=title,
        business_goal=business_goal,
        version=version_m.group(1),
        owner=owner_m.group(1).strip(),
        status=status_m.group(1).lower() if status_m else "draft",  # type: ignore[arg-type]
        actors=actors,
        functional_requirements=frs,
        non_functional_requirements=nfrs,
    )


def parse_brd_file(path: str | Path) -> BRD:
    """Đọc file BRD.md và parse."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"BRD file không tồn tại: {p}")
    return parse_brd_text(p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import json
    import sys as _sys

    if len(_sys.argv) < 2:
        print("Usage: brd_validator.py <path-to-BRD.md>")
        _sys.exit(2)
    try:
        brd = parse_brd_file(_sys.argv[1])
    except (ValidationError, ValueError) as e:
        print(f"BRD INVALID:\n{e}")
        _sys.exit(1)
    out: dict[str, Any] = brd.model_dump()
    out["_summary"] = {
        "actors": len(brd.actors),
        "fr": len(brd.functional_requirements),
        "nfr": len(brd.non_functional_requirements),
        "must_fr": sum(1 for f in brd.functional_requirements if f.priority == "must"),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
