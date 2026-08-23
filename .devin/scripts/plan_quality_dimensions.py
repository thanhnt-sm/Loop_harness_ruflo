#!/usr/bin/env python3
"""plan_quality_dimensions.py — các check theo 10(+1) dimension cho plan_quality_check.

Tách từ plan_quality_check.py (789 dòng) theo plan section 2.9.
Phụ thuộc lớp parse (plan_quality_parse) — import VAGUE_WORDS, _parse_req_ids,
_parse_mermaid_edges, _is_acyclic. Không có chu trình phụ thuộc.

Các symbol public đều được re-export bởi plan_quality_check.py:
`from plan_quality_check import _check_d1` ...
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from plan_quality_parse import (
    VAGUE_WORDS,
    _extract_section,
    _is_acyclic,
    _parse_mermaid_edges,
    _parse_req_ids,
)


# ---------------------------------------------------------------------------
# CVE-2026-AHD-009: REQ ID cross-reference với SDD đã approved
# ---------------------------------------------------------------------------
def _repo_root(plan_path: Path) -> Path:
    """Tìm repo root: walk lên cha cho tới khi có .devin hoặc .git."""
    for parent in [plan_path.parent, *plan_path.parents]:
        if (parent / ".devin").exists() or (parent / ".git").exists():
            return parent
    return plan_path.parent


def _task_slug(plan_path: Path) -> str:
    """Slug từ path docs/plans/<task_slug>/... — khớp quy ước approval_gate."""
    parts = plan_path.resolve().parts
    if "plans" in parts:
        idx = parts.index("plans")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return plan_path.stem


def _approved_sdd_state(plan_path: Path) -> dict | None:
    """Load SDD approval state (.devin/plan_state/<slug>_sd_approved.json).

    Trả None nếu chưa có SDD approval (legacy flow — D11 bỏ qua).
    """
    try:
        root = _repo_root(plan_path)
        state_path = root / ".devin" / "plan_state" / f"{_task_slug(plan_path)}_sd_approved.json"
        if not state_path.exists():
            return None
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _sdd_trace_info(plan_path: Path) -> dict:
    """CVE-2026-AHD-009: verify SDD đã approved + hash còn khớp, trích REQ IDs.

    Trả về:
      {"ok": True, "sdd_req_ids": [...], "sdd_path": "..."} — SDD approved,
        chưa bị sửa sau approval, REQ IDs trích được.
      {"ok": False, "reason": "..."} — không có SDD approved / hash mismatch
        / SDD file thiếu. FAIL CLOSED: plan không được pass D11.
    """
    state = _approved_sdd_state(plan_path)
    if state is None:
        return {"ok": False, "reason": "no_approved_sdd"}
    if state.get("status") != "approved":
        return {"ok": False, "reason": f"sdd_not_approved:{state.get('status')}"}
    signed_hash = state.get("plan_hash", "")
    sdd_rel = state.get("plan_file", "")
    sdd_path = (_repo_root(plan_path) / sdd_rel) if sdd_rel else None
    if sdd_path is None or not sdd_path.exists():
        return {"ok": False, "reason": "sdd_file_missing"}
    if signed_hash:
        current = hashlib.sha256(sdd_path.read_bytes()).hexdigest()
        if current != signed_hash:
            return {"ok": False, "reason": "sdd_hash_mismatch"}
    try:
        sdd_text = sdd_path.read_text(encoding="utf-8")
    except OSError:
        return {"ok": False, "reason": "sdd_file_unreadable"}
    return {"ok": True, "sdd_req_ids": _parse_req_ids(sdd_text), "sdd_path": sdd_rel}


def _check_d11(req_ids: list[str], sdd_info: dict) -> dict:
    """D11: REQ Traceability — mọi plan REQ ID phải có trong approved SDD.

    CVE-2026-AHD-009: plan giới thiệu REQ ID không có trong SDD đã approved
    (hoặc SDD bị sửa sau approval) -> FAIL.
    """
    if not sdd_info["ok"]:
        return {
            "id": "D11",
            "name": "REQ Traceability to SDD",
            "pass": False,
            "detail": f"D11 FAIL: {sdd_info['reason']} — plan REQ IDs không thể trace về SDD approved",
        }
    sdd_ids = set(sdd_info["sdd_req_ids"])
    extra = [rid for rid in req_ids if rid not in sdd_ids]
    if extra:
        return {
            "id": "D11",
            "name": "REQ Traceability to SDD",
            "pass": False,
            "detail": f"D11 FAIL: REQ IDs không có trong approved SDD: {', '.join(sorted(extra))}",
        }
    return {
        "id": "D11",
        "name": "REQ Traceability to SDD",
        "pass": True,
        "detail": "Mọi plan REQ ID trace về approved SDD",
    }


def _is_falsifiable(ac: str) -> bool:
    """Kiểm tra acceptance criteria có falsifiable không (có thể kiểm chứng true/false).

    Tiêu chí: không rỗng, không chứa từ mơ hồ, có dấu hiệu đo lường được
    (số, từ khóa: should/must/shall/will, hoặc test).
    """
    if not ac or len(ac.strip()) < 5:
        return False
    low = ac.lower()
    # Bước 1: Có từ khóa xác nhận/khẳng định (tiếng Anh + tiếng Việt thường gặp trong AC)
    has_assertion = any(k in low for k in [
        "should", "must", "shall", "will", "phải", "tại", "trả về", "return",
        "pass", "exit", "thành công", "đạt", "block", "chặn", "no corrupt",
        "no interleave", "no duplicate", "no lost",
    ])
    # Bước 2: Có chỉ số đo lường (số, %, giây, ms) hoặc từ "test"
    has_measure = bool(re.search(r"\d|test|verify|assert|giây|ms|%", low))
    # Bước 3: Không chứa quá nhiều từ mơ hồ
    vague_count = sum(1 for w in VAGUE_WORDS if w in low)
    return has_assertion and has_measure and vague_count <= 1


def _check_d1(req_ids: list[str], tasks: list[dict]) -> dict:
    """D1: Requirement Coverage — mọi REQ có ít nhất một task tham chiếu."""
    if not req_ids:
        return {"id": "D1", "name": "Requirement Coverage", "pass": False,
                "detail": "Không tìm thấy REQ ID nào trong plan"}
    covered = set()
    for t in tasks:
        covered.update(t["req_ids"])
    missing = [r for r in req_ids if r not in covered]
    return {"id": "D1", "name": "Requirement Coverage",
            "pass": len(missing) == 0,
            "detail": f"{len(req_ids)} REQ, {len(covered)} có task, thiếu: {missing}"}


def _check_d2(tasks: list[dict]) -> dict:
    """D2: Task Completeness — mỗi task có file path + function + acceptance criteria."""
    incomplete = []
    for t in tasks:
        missing = []
        if not t["file_path"]:
            missing.append("file_path")
        if not t["function"]:
            missing.append("function")
        if not t["ac"]:
            missing.append("acceptance_criteria")
        if missing:
            incomplete.append({"task": t["id"], "missing": missing})
    return {"id": "D2", "name": "Task Completeness",
            "pass": len(incomplete) == 0,
            "detail": f"{len(tasks)} task, {len(incomplete)} thiếu thông tin: {incomplete}"}


def _check_d3(text: str) -> dict:
    """D3: Dependency Correctness — Mermaid DAG acyclic."""
    edges = _parse_mermaid_edges(text)
    if not edges:
        return {"id": "D3", "name": "Dependency Correctness", "pass": True,
                "detail": "Không có Mermaid graph hoặc không có edge (bỏ qua)"}
    acyclic = _is_acyclic(edges)
    return {"id": "D3", "name": "Dependency Correctness",
            "pass": acyclic,
            "detail": f"{len(edges)} edge, acyclic={acyclic}"}


def _check_d4(text: str, tasks: list[dict]) -> dict:
    """D4: Key Links Planned — mọi integration point từ SDD có task."""
    sdd_section = _extract_section(text, "SDD") or _extract_section(text, "Integration")
    # Trích các integration point dạng LINK-### hoặc IP-###
    links = re.findall(r"\b(?:LINK|IP)[-_]?(\d+)\b", sdd_section, re.IGNORECASE)
    link_ids = {f"LINK-{int(n):03d}" for n in links}
    if not link_ids:
        return {"id": "D4", "name": "Key Links Planned", "pass": True,
                "detail": "Không có integration point nào trong SDD section"}
    # Kiểm tra mỗi link có task nhắc đến không
    covered = set()
    for t in tasks:
        for lid in link_ids:
            if lid in t["raw"]:
                covered.add(lid)
    missing = link_ids - covered
    return {"id": "D4", "name": "Key Links Planned",
            "pass": len(missing) == 0,
            "detail": f"{len(link_ids)} integration point, thiếu task cho: {sorted(missing)}"}


def _check_d5(req_ids: list[str], tasks: list[dict]) -> dict:
    """D5: Scope Sanity — không có orphan task (task không tham chiếu REQ nào)."""
    if not req_ids:
        return {"id": "D5", "name": "Scope Sanity", "pass": True,
                "detail": "Không có REQ ID để đối chiếu orphan"}
    orphans = [t["id"] for t in tasks if not t["req_ids"]]
    return {"id": "D5", "name": "Scope Sanity",
            "pass": len(orphans) == 0,
            "detail": f"{len(orphans)} orphan task: {orphans}"}


def _check_d6(tasks: list[dict]) -> dict:
    """D6: Must-Haves Derivation — acceptance criteria falsifiable."""
    vague = []
    for t in tasks:
        if not _is_falsifiable(t["ac"]):
            vague.append(t["id"])
    return {"id": "D6", "name": "Must-Haves Derivation",
            "pass": len(vague) == 0,
            "detail": f"{len(vague)} task có AC mơ hồ/không falsifiable: {vague}"}


def _check_d7(text: str) -> dict:
    """D7: Context Compliance — plan tuân theo AGENTS.md/CLAUDE.md.

    Kiểm tra plan có nhắc đến AGENTS.md hoặc CLAUDE.md, hoặc có section context/compliance.
    """
    low = text.lower()
    mentions = ("agents.md" in low) or ("claude.md" in low)
    has_section = bool(re.search(r"^#{2,3}\s+.*(context|compliance|convention)", text, re.IGNORECASE | re.MULTILINE))
    ok = mentions or has_section
    return {"id": "D7", "name": "Context Compliance",
            "pass": ok,
            "detail": f"mentions_agents/claude={mentions}, has_context_section={has_section}"}


def _check_d8(tasks: list[dict]) -> dict:
    """D8: Risk Assessment — mọi task R3+ có mitigation."""
    missing = []
    for t in tasks:
        if t["risk"] >= 3 and not t["mitigation"]:
            missing.append(t["id"])
    return {"id": "D8", "name": "Risk Assessment",
            "pass": len(missing) == 0,
            "detail": f"{len(missing)} task R3+ thiếu mitigation: {missing}"}


def _check_d9(text: str, req_ids: list[str]) -> dict:
    """D9: Test Coverage — mọi requirement có test case."""
    # Ưu tiên section Test-Requirement Mapping (ánh xạ REQ → test file rõ ràng),
    # sau đó fallback sang section Test / Acceptance Test tổng quát.
    test_section = (
        _extract_section(text, "Test-Requirement Mapping")
        or _extract_section(text, "Test Requirement")
        or _extract_section(text, "Acceptance Test")
        or _extract_section(text, "Test")
    )
    if not test_section:
        return {"id": "D9", "name": "Test Coverage", "pass": False,
                "detail": "Không có section Test / Acceptance Test"}
    covered = set()
    for n in re.findall(r"\bREQ[-_]?(\d+)\b", test_section, re.IGNORECASE):
        covered.add(f"REQ-{int(n):03d}")
    missing = [r for r in req_ids if r not in covered] if req_ids else []
    return {"id": "D9", "name": "Test Coverage",
            "pass": len(missing) == 0,
            "detail": f"{len(req_ids)} REQ, {len(covered)} có test case, thiếu: {missing}"}


def _check_d10(tasks: list[dict]) -> dict:
    """D10: Rollback Plan — mọi task R2+ có rollback."""
    missing = []
    for t in tasks:
        if t["risk"] >= 2 and not t["rollback"]:
            missing.append(t["id"])
    return {"id": "D10", "name": "Rollback Plan",
            "pass": len(missing) == 0,
            "detail": f"{len(missing)} task R2+ thiếu rollback: {missing}"}
