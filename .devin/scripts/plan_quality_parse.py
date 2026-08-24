#!/usr/bin/env python3
"""plan_quality_parse.py — lớp parse (trích xuất) cho plan_quality_check.

Tách từ plan_quality_check.py (789 dòng) theo plan section 2.9.
Chứa các hàm thuần (pure) trích xuất REQ ID, task, coverage table,
risk table, Mermaid edges và các helper liên quan. Không import
bất kỳ module plan_quality_* nào khác (lớp đáy, không phụ thuộc vòng).

Các symbol public (underscore) đều được re-export bởi plan_quality_check.py
để giữ nguyên API: `from plan_quality_check import _parse_tasks` ...
"""
from __future__ import annotations

import json
import re


# Các từ khóa mơ hồ thường gặp trong acceptance criteria kém chất lượng
VAGUE_WORDS = [
    "properly", "appropriate", "good", "nice", "fast", "efficient",
    "user-friendly", "robust", "flexible", "scalable", "modern",
    "tốt", "đẹp", "nhanh", "hiệu quả", "hợp lý", "chuẩn", "ok",
]

# Map nhãn risk dạng chữ (Low/Med/High) sang mức số 1/2/3
_RISK_LABELS = {"high": 3, "h": 3, "r3": 3, "r4": 3, "med": 2, "medium": 2, "m": 2, "r2": 2,
                 "low": 1, "l": 1, "r1": 1, "1": 1, "2": 2, "3": 3, "4": 4}

# Map tên cột (lower) → key nội bộ trong task dict
_COL_KEYS = {
    "task id": "id", "description": "desc", "file path": "file", "function": "func",
    "acceptance criteria": "ac", "req id": "req", "risk": "risk",
    "mitigation": "mit", "rollback": "rb",
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


def _risk_label_to_int(label: str) -> int:
    """Map nhãn risk (Low/Med/High hoặc R1-R4 hoặc số) sang mức số."""
    return _RISK_LABELS.get(label.strip().lower(), 0)


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
