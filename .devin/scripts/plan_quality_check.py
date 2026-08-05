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

Usage:
    python .devin/scripts/plan_quality_check.py <plan_file.md>

Exit codes:
    0 = mọi dimension PASS
    1 = có ít nhất một dimension FAIL
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

# Bước 0: Ép stdout/stderr dùng UTF-8 (tránh lỗi cp1258 trên Windows console với tiếng Việt)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
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


def _parse_tasks(text: str) -> list[dict]:
    """Trích danh sách task từ plan.

    Mỗi task được mô tả dạng:
      - **T1**: ... file: src/foo.py func: bar() AC: ...
    Trả về list dict với các key: id, raw, file_path, function, ac, risk, mitigation, rollback, req_ids.
    """
    tasks = []
    # Tìm các dòng task dạng "- **T1**:" hoặc "- T1:" hoặc "1. T1:"
    task_pattern = re.compile(
        r"^\s*[-\d.\*]+\s*\*{0,2}(T\d+)\*{0,2}\s*[:\-]?\s*(.*)$",
        re.MULTILINE,
    )
    # Bước 0: Parse coverage table để bổ sung req_ids cho task nếu thiếu
    coverage_map = _parse_coverage_table(text)
    # Đảo ngược: task_id -> [req_ids]
    task_to_reqs: dict[str, list[str]] = {}
    for rid, tids in coverage_map.items():
        for tid in tids:
            task_to_reqs.setdefault(tid, [])
            if rid not in task_to_reqs[tid]:
                task_to_reqs[tid].append(rid)

    for m in task_pattern.finditer(text):
        tid = m.group(1)
        raw = m.group(2).strip()
        # Trích file path (đường dẫn có .py / .js / .ts / .md ...)
        file_m = re.search(r"[\w/\\]+\.\w{1,6}", raw)
        file_path = file_m.group(0) if file_m else ""
        # Trích function (func: name() hoặc function: name)
        func_m = re.search(r"func(?:tion)?:\s*([A-Za-z_][\w]*)\s*\(", raw, re.IGNORECASE)
        function = func_m.group(1) if func_m else ""
        # Trích acceptance criteria (AC: ...)
        ac_m = re.search(r"AC\s*:\s*(.+?)(?:\s+R\d|$)", raw, re.IGNORECASE)
        ac = ac_m.group(1).strip() if ac_m else ""
        # Trích risk level (R1/R2/R3/R4)
        risk_m = re.search(r"\bR([1-4])\b", raw)
        risk = int(risk_m.group(1)) if risk_m else 0
        # Trích mitigation (mitigation: ...)
        mit_m = re.search(r"mitig(?:ation)?:\s*(.+?)(?:\s+rollback:|\s+R\d|$)", raw, re.IGNORECASE)
        mitigation = mit_m.group(1).strip() if mit_m else ""
        # Trích rollback (rollback: ...)
        rb_m = re.search(r"rollback:\s*(.+?)(?:\s+R\d|$)", raw, re.IGNORECASE)
        rollback = rb_m.group(1).strip() if rb_m else ""
        # Trích REQ ID liên quan từ dòng task
        req_ids = [f"REQ-{int(n):03d}" for n in re.findall(r"\bREQ[-_]?(\d+)\b", raw, re.IGNORECASE)]
        # Bước bổ sung: Nếu task không có REQ trong dòng, lấy từ coverage table
        if not req_ids and tid in task_to_reqs:
            req_ids = task_to_reqs[tid]
        tasks.append({
            "id": tid,
            "raw": raw,
            "file_path": file_path,
            "function": function,
            "ac": ac,
            "risk": risk,
            "mitigation": mitigation,
            "rollback": rollback,
            "req_ids": req_ids,
        })
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
    # Bước 1: Có từ khóa xác nhận/khẳng định
    has_assertion = any(k in low for k in ["should", "must", "shall", "will", "phải", "tại", "trả về", "return"])
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
    test_section = _extract_section(text, "Test") or _extract_section(text, "Acceptance Test")
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
    """Chạy toàn bộ 10 dimension check, trả về scorecard dict."""
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
