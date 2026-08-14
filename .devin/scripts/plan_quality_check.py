#!/usr/bin/env python3
"""plan_quality_check.py — kiểm tra chất lượng implementation plan theo 10 chiều (DeepEval + Plan-Build-Run).

Script này validate một file plan Markdown dựa trên 10 dimension:
  D1  Requirement Coverage       — mọi requirement có task tương ứng?
  D2  Task Completeness          — mỗi task có file path + function + acceptance criteria?
  D3  Dependency Correctness     — DAG trong Mermaid có acyclic?
  D4  Key Links Planned          — mọi integration point từ SDD có task?
  D5  Scope Sanity               — không có orphan task (task ngoài requirement)?
  D6  Must-Haves Derivation      — acceptance criteria có falsifiable (không mơ hồ)?
  D7  Context Compliance         — plan tuân theo AGENTS.md/CLAUDE.md?
  D8  Risk Assessment            — mọi task R3+ có mitigation?
  D9  Test Coverage              — mọi requirement có test case?
  D10 Rollback Plan              — mọi task R2+ có rollback?
  D11 REQ Traceability to SDD    — mọi plan REQ ID có trong SDD đã approved?
                                  (CVE-2026-AHD-009; active khi có SDD approval)

Usage:
    python .devin/scripts/plan_quality_check.py <plan_file.md>

Exit codes:
    0 = mọi dimension PASS
    1 = có ít nhất một dimension FAIL
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone


# Bước 0: Ép stdout/stderr dùng UTF-8 khi chạy CLI (tránh lỗi cp1258 trên Windows console)
def _ensure_utf8() -> None:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


# Danh sách 10 dimension với mô tả ngắn gọn
DIMENSIONS = [
    ("D1", "Requirement Coverage", "Mọi requirement có task tương ứng"),
    ("D2", "Task Completeness", "Mỗi task có file path + function + acceptance criteria"),
    ("D3", "Dependency Correctness", "DAG trong Mermaid acyclic"),
    ("D4", "Key Links Planned", "Mọi integration point từ SDD có task"),
    ("D5", "Scope Sanity", "Không có orphan task ngoài requirement"),
    ("D6", "Must-Haves Derivation", "Acceptance criteria falsifiable, không mơ hồ"),
    ("D7", "Context Compliance", "Plan tuân theo AGENTS.md/CLAUDE.md"),
    ("D8", "Risk Assessment", "Mọi task R3+ có mitigation"),
    ("D9", "Test Coverage", "Mọi requirement có test case"),
    ("D10", "Rollback Plan", "Mọi task R2+ có rollback"),
]

# Các từ khóa mơ hồ thường gặp trong acceptance criteria kém chất lượng
VAGUE_WORDS = [
    "properly", "appropriate", "good", "nice", "fast", "efficient",
    "user-friendly", "robust", "flexible", "scalable", "modern",
    "tốt", "đẹp", "nhanh", "hiệu quả", "hợp lý", "chuẩn", "ok",
]


def _read_plan(plan_path: Path) -> str:
    """Đọc nội dung plan file, ném lỗi nếu file không tồn tại hoặc rỗng."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Không tìm thấy plan file: {plan_path}")
    text = plan_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Plan file rỗng (không có nội dung)")
    return text


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


def _extract_section(text: str, heading: str) -> str:
    """Trích nội dung một section Markdown theo heading (h2 hoặc h3).

    Trả về chuỗi rỗng nếu không tìm thấy section.
    """
    # Bước 1: Tìm dòng heading (## hoặc ###) có chứa keyword, chỉ trên 1 dòng (không DOTALL)
    heading_pattern = re.compile(
        r"^#{2,3}\s+.*" + re.escape(heading) + r".*$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = heading_pattern.search(text)
    if not m:
        return ""
    # Bước 2: Lấy nội dung từ sau heading đến heading tiếp theo hoặc hết file
    start = m.end()
    rest = text[start:]
    next_heading = re.search(r"^#{2,3}\s+", rest, re.MULTILINE)
    if next_heading:
        return rest[:next_heading.start()].strip()
    return rest.strip()


def _parse_req_ids(text: str) -> list[str]:
    """Trích danh sách REQ ID (ví dụ REQ-001, REQ-01) từ nội dung plan."""
    # Bước 1: Tìm trong coverage matrix / requirement section
    section = _extract_section(text, "Requirement") or _extract_section(text, "Coverage")
    search_text = section if section else text
    # Bước 2: Regex tìm REQ-### dạng chữ-số
    ids = re.findall(r"\bREQ[-_]?(\d+)\b", search_text, re.IGNORECASE)
    # Chuẩn hoá thành REQ-001 (zero-pad 3)
    seen = []
    for n in ids:
        rid = f"REQ-{int(n):03d}"
        if rid not in seen:
            seen.append(rid)
    return seen


def _parse_coverage_table(text: str) -> dict[str, list[str]]:
    """Trích ánh xạ REQ -> [Task IDs] từ bảng coverage matrix trong plan.

    Bảng dạng: | REQ-001 | T1 | hoặc | REQ | Task | (header bỏ qua).
    Trả về dict {req_id: [task_id, ...]}.
    """
    section = _extract_section(text, "Coverage") or _extract_section(text, "Matrix")
    if not section:
        return {}
    mapping: dict[str, list[str]] = {}
    # Bước 1: Duyệt từng dòng bảng (có dấu |)
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        # Bước 2: Tìm REQ ID và Task ID trong các ô
        req_matches = re.findall(r"\bREQ[-_]?(\d+)\b", cells[0], re.IGNORECASE)
        task_matches = re.findall(r"\b(T\d+)\b", cells[1], re.IGNORECASE)
        # Fallback: tìm ở bất kỳ ô nào
        if not req_matches:
            for c in cells:
                req_matches = re.findall(r"\bREQ[-_]?(\d+)\b", c, re.IGNORECASE)
                if req_matches:
                    break
        if not task_matches:
            for c in cells:
                task_matches = re.findall(r"\b(T\d+)\b", c, re.IGNORECASE)
                if task_matches:
                    break
        for n in req_matches:
            rid = f"REQ-{int(n):03d}"
            mapping.setdefault(rid, [])
            for tid in task_matches:
                if tid not in mapping[rid]:
                    mapping[rid].append(tid)
    return mapping


def _extract_file_path(raw: str) -> str:
    """Trích file path từ trường `file:` hoặc `path:` trong task raw.

    Ưu tiên trường `file:` / `path:` chính xác. Nếu không có,
    fallback tìm đường dẫn file-like đầu tiên.
    """
    m = re.search(r"(?:file|file_path|path)\s*[:=]\s*`?([^`\s,;]+)", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip("'\"\u201c\u201d")
    # Fallback cũ, mở rộng để bắt dấu . đầu path và extension dài hơn.
    file_m = re.search(r"[\w.\/\\-]+\.\w{1,10}", raw)
    return file_m.group(0) if file_m else ""


def _extract_function(raw: str) -> str:
    """Trích function name từ trường `func:` hoặc `function:`."""
    m = re.search(r"func(?:tion)?\s*[:=]\s*([A-Za-z_][\w]*)\s*\(?", raw, re.IGNORECASE)
    return m.group(1) if m else ""


def _strip_backticks(s: str) -> str:
    """Bỏ dấu backtick bao quanh và trim khoảng trắng."""
    return s.strip().strip("`").strip()


# Map nhãn risk dạng chữ (Low/Med/High) sang mức số 1/2/3
_RISK_LABELS = {"high": 3, "h": 3, "r3": 3, "r4": 3, "med": 2, "medium": 2, "m": 2, "r2": 2,
                 "low": 1, "l": 1, "r1": 1, "1": 1, "2": 2, "3": 3, "4": 4}


def _risk_label_to_int(label: str) -> int:
    """Map nhãn risk (Low/Med/High hoặc R1-R4 hoặc số) sang mức số."""
    return _RISK_LABELS.get(label.strip().lower(), 0)


# Map tên cột (lower) → key nội bộ trong task dict
_COL_KEYS = {
    "task id": "id", "description": "desc", "file path": "file", "function": "func",
    "acceptance criteria": "ac", "req id": "req", "risk": "risk",
    "mitigation": "mit", "rollback": "rb",
}


def _parse_risk_table(text: str) -> dict[str, tuple[str, str]]:
    """Trích mitigation/rollback fallback từ bảng §7 Risk & Mitigation.

    Trả về dict {tier: (mitigation, rollback)} cho tier đầu tiên khớp (P0/P1/P2/P3).
    """
    section = _extract_section(text, "Risk & Mitigation") or _extract_section(text, "Risk")
    if not section:
        return {}
    result: dict[str, tuple[str, str]] = {}
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Bỏ qua header (cột đầu là "Risk") và dòng thiếu cột
        if len(cells) < 4 or cells[0].lower() == "risk":
            continue
        tier = cells[1].strip().upper()
        if tier and tier not in result:
            result[tier] = (cells[2].strip(), cells[3].strip())
    return result


def _risk_fallback(risk: int, risk_table: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """Chọn mitigation/rollback fallback theo mức risk: High→P0, Med→P1, Low→P2/P3."""
    if risk >= 3:
        return risk_table.get("P0", ("", ""))
    if risk == 2:
        return risk_table.get("P1", ("", ""))
    if risk == 1:
        return risk_table.get("P2", risk_table.get("P3", ("", "")))
    return ("", "")


def _parse_task_tables(text: str, risk_table: dict[str, tuple[str, str]]) -> list[dict]:
    """Trích task từ bảng Markdown có header chứa 'Task ID' (định dạng PLAN_TEMPLATE.md).

    Các cột: Task ID | Description | File Path | Function | Acceptance Criteria | REQ ID | Risk
    (có thể có thêm Mitigation / Rollback). Bỏ qua bảng chỉ có Task ID nhưng không có cột
    định nghĩa task (File Path/Function/Acceptance Criteria) — ví dụ bảng test case §8.1.
    """
    tasks: list[dict] = []
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        # Bước 1: Tìm dòng header bảng có chứa "Task ID"
        if not (line.startswith("|") and "task id" in line.lower()):
            i += 1
            continue
        # Bước 2: Lập bản đồ cột (tên cột → index)
        col_map: dict[str, int] = {}
        for idx, h in enumerate(c.strip().lower() for c in line.strip("|").split("|")):
            key = _COL_KEYS.get(h.strip())
            if key:
                col_map[key] = idx
        # Chỉ xử lý nếu có cột Task ID VÀ ít nhất một cột định nghĩa task
        if "id" not in col_map or not ({"file", "func", "ac"} & col_map.keys()):
            i += 1
            continue
        max_col = max(col_map.values())
        i += 1
        # Bước 3: Bỏ qua dòng separator (---)
        if i < n and "---" in lines[i] and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i]):
            i += 1
        # Bước 4: Đọc các dòng data cho đến khi hết bảng
        while i < n:
            row = lines[i].strip()
            if not row.startswith("|"):
                break
            if "---" in row:
                i += 1
                continue
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) <= max_col:
                i += 1
                continue
            tid = cells[col_map["id"]].strip()
            # Bước 5: Chỉ nhận dòng có Task ID dạng T< số >
            if not re.match(r"^T\d", tid):
                i += 1
                continue
            # Trích các trường theo cột (nếu cột thiếu để rỗng)
            def _cell(key: str) -> str:
                return cells[col_map[key]].strip() if key in col_map else ""
            desc, ac = _cell("desc"), _cell("ac")
            file_path = _strip_backticks(_cell("file"))
            function = _strip_backticks(_cell("func"))
            risk = _risk_label_to_int(_cell("risk"))
            req_cell = _cell("req")
            mitigation, rollback = _cell("mit"), _cell("rb")
            # Bước 6: Fallback mitigation/rollback từ §7 Risk & Mitigation nếu thiếu
            if not mitigation or not rollback:
                fb_mit, fb_rb = _risk_fallback(risk, risk_table)
                mitigation = mitigation or fb_mit
                rollback = rollback or fb_rb
            # Trích REQ ID từ cột REQ ID
            req_ids = [f"REQ-{int(num):03d}" for num in re.findall(r"\bREQ[-_]?(\d+)\b", req_cell, re.IGNORECASE)]
            # raw dùng cho D4 (Key Links Planned) — gom description + AC + REQ
            tasks.append({
                "id": tid, "raw": f"{desc} {ac} {req_cell}".strip(),
                "file_path": file_path, "function": function, "ac": ac, "risk": risk,
                "mitigation": mitigation, "rollback": rollback, "req_ids": req_ids,
            })
            i += 1
        continue
    return tasks


def _parse_tasks(text: str) -> list[dict]:
    """Trích danh sách task từ plan.

    Hỗ trợ 2 định dạng:
      1. Bullet task dạng: `- **T1**: ... file: src/foo.py func: bar() AC: ...`
      2. Markdown task table (header chứa 'Task ID') theo PLAN_TEMPLATE.md.

    Trả về list dict với các key: id, raw, file_path, function, ac, risk, mitigation, rollback, req_ids.
    """
    # Bước 0: Parse bảng §7 Risk & Mitigation để fallback mitigation/rollback
    risk_table = _parse_risk_table(text)
    # Bước 1: Parse coverage table để bổ sung req_ids cho task nếu thiếu
    coverage_map = _parse_coverage_table(text)
    # Đảo ngược: task_id -> [req_ids]
    task_to_reqs: dict[str, list[str]] = {}
    for rid, tids in coverage_map.items():
        for tid in tids:
            task_to_reqs.setdefault(tid, [])
            if rid not in task_to_reqs[tid]:
                task_to_reqs[tid].append(rid)

    # Bước 2: Parse Markdown task tables (định dạng chính thức PLAN_TEMPLATE.md)
    tasks = _parse_task_tables(text, risk_table)
    seen_ids = {t["id"] for t in tasks}

    # Bước 3: Parse bullet task (định dạng cũ) — không trùng ID với table
    task_pattern = re.compile(
        r"^\s*[-\d.\*]+\s*\*{0,2}(T\d+)\*{0,2}\s*[:\-]?\s*(.*)$",
        re.MULTILINE,
    )
    for m in task_pattern.finditer(text):
        tid = m.group(1)
        if tid in seen_ids:
            continue
        raw = m.group(2).strip()
        file_path = _extract_file_path(raw)
        function = _extract_function(raw)
        ac_m = re.search(r"AC\s*:\s*(.+?)(?:\s+R\d|$)", raw, re.IGNORECASE)
        ac = ac_m.group(1).strip() if ac_m else ""
        risk_m = re.search(r"\bR([1-4])\b", raw)
        risk = int(risk_m.group(1)) if risk_m else 0
        mit_m = re.search(r"mitig(?:ation)?:\s*(.+?)(?:\s+rollback:|\s+R\d|$)", raw, re.IGNORECASE)
        mitigation = mit_m.group(1).strip() if mit_m else ""
        rb_m = re.search(r"rollback:\s*(.+?)(?:\s+R\d|$)", raw, re.IGNORECASE)
        rollback = rb_m.group(1).strip() if rb_m else ""
        # Fallback mitigation/rollback từ §7 nếu thiếu
        if not mitigation or not rollback:
            fb_mit, fb_rb = _risk_fallback(risk, risk_table)
            mitigation = mitigation or fb_mit
            rollback = rollback or fb_rb
        req_ids = [f"REQ-{int(n):03d}" for n in re.findall(r"\bREQ[-_]?(\d+)\b", raw, re.IGNORECASE)]
        # Bước bổ sung: Nếu task không có REQ trong dòng, lấy từ coverage table
        if not req_ids and tid in task_to_reqs:
            req_ids = task_to_reqs[tid]
        tasks.append({
            "id": tid, "raw": raw, "file_path": file_path, "function": function,
            "ac": ac, "risk": risk, "mitigation": mitigation, "rollback": rollback,
            "req_ids": req_ids,
        })
        seen_ids.add(tid)
    return tasks


def _parse_mermaid_edges(text: str) -> list[tuple[str, str]]:
    """Trích các cạnh (edge) từ Mermaid graph (flowchart / graph).

    Hỗ trợ cú pháp A --> B, A -->|label| B, A -- B.
    Trả về list tuple (from, to).
    """
    # Bước 1: Tìm khối Mermaid
    edges = []
    blocks = re.findall(r"```mermaid\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    for block in blocks:
        # Bước 2: Mỗi dòng có dạng "A --> B" hoặc "A -->|label| B"
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith(("%%", "graph", "flowchart", "subgraph", "end", "classDef", "class")):
                continue
            # Bỏ nhãn trên edge: A -->|label| B  ->  A --> B
            clean = re.sub(r"\|[^|]*\|", "", line)
            # Tách node theo --, -->, ==>
            parts = re.split(r"-+>|--+|==+>", clean)
            parts = [p.strip().strip("[]") for p in parts if p.strip()]
            for i in range(len(parts) - 1):
                if parts[i] and parts[i + 1]:
                    edges.append((parts[i], parts[i + 1]))
    return edges


def _is_acyclic(edges: list[tuple[str, str]]) -> bool:
    """Kiểm tra đồ thị có hướng có chu trình không (DFS). Trả True nếu acyclic."""
    # Bước 1: Xây adjacency list
    adj: dict[str, list[str]] = {}
    nodes = set()
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        nodes.add(a)
        nodes.add(b)
    # Bước 2: DFS với 3 trạng thái: 0=chưa thăm, 1=đang thăm, 2=đã xong
    state = {n: 0 for n in nodes}

    def dfs(u: str) -> bool:
        state[u] = 1
        for v in adj.get(u, []):
            if state[v] == 1:
                return False  # phát hiện back edge -> có chu trình
            if state[v] == 0 and not dfs(v):
                return False
        state[u] = 2
        return True

    for n in nodes:
        if state[n] == 0 and not dfs(n):
            return False
    return True


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


def run_checks(plan_path: Path) -> dict:
    """Chạy toàn bộ 10 dimension check (+ D11 khi có SDD approval), trả scorecard dict."""
    text = _read_plan(plan_path)
    req_ids = _parse_req_ids(text)
    tasks = _parse_tasks(text)

    results = [
        _check_d1(req_ids, tasks),
        _check_d2(tasks),
        _check_d3(text),
        _check_d4(text, tasks),
        _check_d5(req_ids, tasks),
        _check_d6(tasks),
        _check_d7(text),
        _check_d8(tasks),
        _check_d9(text, req_ids),
        _check_d10(tasks),
    ]

    # CVE-2026-AHD-009: D11 — REQ traceability với SDD approved.
    # Chỉ active khi có SDD approval state (legacy flow không có SDD vẫn 10D).
    if _approved_sdd_state(plan_path) is not None:
        sdd_info = _sdd_trace_info(plan_path)
        results.append(_check_d11(req_ids, sdd_info))
        results[-1]["detail"] += f" (sdd: {sdd_info.get('sdd_path', '?')})"

    passed = sum(1 for r in results if r["pass"])
    scorecard = {
        "plan_file": str(plan_path),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total_dimensions": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "dimensions": results,
        "all_pass": passed == len(results),
    }
    return scorecard


def _render_markdown_report(scorecard: dict) -> str:
    """Tạo báo cáo Markdown từ scorecard."""
    lines = [
        f"# Quality Report — {Path(scorecard['plan_file']).name}",
        "",
        f"- **Checked at**: {scorecard['checked_at']}",
        f"- **Total dimensions**: {scorecard['total_dimensions']}",
        f"- **Passed**: {scorecard['passed']}",
        f"- **Failed**: {scorecard['failed']}",
        f"- **Overall**: {'PASS' if scorecard['all_pass'] else 'FAIL'}",
        "",
        "## Dimension Results",
        "",
        "| ID | Name | Status | Detail |",
        "|----|------|--------|--------|",
    ]
    for d in scorecard["dimensions"]:
        status = "PASS" if d["pass"] else "FAIL"
        detail = d["detail"].replace("|", "\\|")
        lines.append(f"| {d['id']} | {d['name']} | {status} | {detail} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Entry point CLI. Trả exit code 0 nếu PASS, 1 nếu FAIL."""
    _ensure_utf8()
    if len(sys.argv) < 2:
        print("Usage: python plan_quality_check.py <plan_file.md>", file=sys.stderr)
        return 2
    plan_path = Path(sys.argv[1]).resolve()
    try:
        scorecard = run_checks(plan_path)
    except (FileNotFoundError, ValueError) as e:
        # Edge case: file thiếu hoặc rỗng
        print(json.dumps({"error": str(e), "plan_file": str(plan_path)}, ensure_ascii=False, indent=2))
        return 1

    # In JSON scorecard ra stdout
    print(json.dumps(scorecard, ensure_ascii=False, indent=2))

    # Ghi báo cáo Markdown vào docs/plans/QUALITY_REPORT_<plan_name>.md
    repo_root = plan_path.parent
    # Tìm repo root: đi lên cho tới khi thấy .devin hoặc .git
    for parent in [plan_path.parent, *plan_path.parents]:
        if (parent / ".devin").exists() or (parent / ".git").exists():
            repo_root = parent
            break
    report_dir = repo_root / "docs" / "plans"
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"QUALITY_REPORT_{plan_path.stem}.md"
        report_path.write_text(_render_markdown_report(scorecard), encoding="utf-8")
        print(f"\n[REPORT] {report_path}", file=sys.stderr)
    except OSError as e:
        # Edge case: không ghi được report (chỉ cảnh báo, không fail)
        print(f"[WARN] Không ghi được report: {e}", file=sys.stderr)

    return 0 if scorecard["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
