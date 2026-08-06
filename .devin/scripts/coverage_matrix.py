#!/usr/bin/env python3
"""coverage_matrix.py — sinh và kiểm chứng coverage matrix từ implementation plan.

Script này làm 2 việc:
  1. Không có --verify: Sinh coverage matrix từ plan (parse REQ ID, task, file path, function).
  2. Có --verify: Kiểm chứng matrix với code thực tế (file có tồn tại? function có mặt?).

Cấu trúc matrix:
  {req_id: {task_id, file_path, function, status, evidence}}

Status: PLANNED | EXECUTED | VERIFIED | MISSING | FAIL

Usage:
    python .devin/scripts/coverage_matrix.py <plan_file.md>            # Sinh matrix
    python .devin/scripts/coverage_matrix.py <plan_file.md> --verify   # Kiểm chứng

Exit codes:
    0 = mọi entry VERIFIED/EXECUTED (hoặc sinh matrix thành công)
    1 = có entry MISSING hoặc FAIL
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

# Bước 0: Ép stdout/stderr dùng UTF-8 (tránh lỗi cp1258 trên Windows console với tiếng Việt)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Các trạng thái hợp lệ của một entry trong matrix
STATUS_PLANNED = "PLANNED"      # Task đã lên kế hoạch, chưa thực thi
STATUS_EXECUTED = "EXECUTED"    # File tồn tại nhưng chưa verify function
STATUS_VERIFIED = "VERIFIED"    # File tồn tại VÀ function có mặt
STATUS_MISSING = "MISSING"      # File không tồn tại
STATUS_FAIL = "FAIL"            # File tồn tại nhưng function thiếu


def _read_plan(plan_path: Path) -> str:
    """Đọc nội dung plan file. Ném lỗi nếu thiếu hoặc rỗng."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Không tìm thấy plan file: {plan_path}")
    text = plan_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Plan file rỗng (không có nội dung)")
    return text


def _extract_section(text: str, heading: str) -> str:
    """Trích nội dung một section Markdown theo heading (h2 hoặc h3)."""
    heading_pattern = re.compile(
        r"^#{2,3}\s+.*" + re.escape(heading) + r".*$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = heading_pattern.search(text)
    if not m:
        return ""
    start = m.end()
    rest = text[start:]
    next_heading = re.search(r"^#{2,3}\s+", rest, re.MULTILINE)
    if next_heading:
        return rest[:next_heading.start()].strip()
    return rest.strip()


def _parse_coverage_table(text: str) -> dict[str, list[str]]:
    """Trích ánh xạ REQ -> [Task IDs] từ bảng coverage matrix trong plan."""
    section = _extract_section(text, "Coverage") or _extract_section(text, "Matrix")
    if not section:
        return {}
    mapping: dict[str, list[str]] = {}
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        req_matches = re.findall(r"\bREQ[-_]?(\d+)\b", cells[0], re.IGNORECASE)
        task_matches = re.findall(r"\b(T\d+)\b", cells[1], re.IGNORECASE)
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


def _parse_tasks(text: str) -> list[dict]:
    """Trích danh sách task từ plan (tương tự plan_quality_check.py).

    Trả về list dict: id, raw, file_path, function, req_ids.
    """
    tasks = []
    task_pattern = re.compile(
        r"^\s*[-\d.\*]+\s*\*{0,2}(T\d+)\*{0,2}\s*[:\-]?\s*(.*)$",
        re.MULTILINE,
    )
    # Bước 0: Parse coverage table để bổ sung req_ids cho task nếu thiếu
    coverage_map = _parse_coverage_table(text)
    task_to_reqs: dict[str, list[str]] = {}
    for rid, tids in coverage_map.items():
        for tid in tids:
            task_to_reqs.setdefault(tid, [])
            if rid not in task_to_reqs[tid]:
                task_to_reqs[tid].append(rid)

    for m in task_pattern.finditer(text):
        tid = m.group(1)
        raw = m.group(2).strip()
        # Trích file path từ trường file: / path:
        file_path = _extract_file_path(raw)
        # Trích function từ trường func: / function:
        function = _extract_function(raw)
        req_ids = [f"REQ-{int(n):03d}" for n in re.findall(r"\bREQ[-_]?(\d+)\b", raw, re.IGNORECASE)]
        # Bổ sung từ coverage table nếu task không có REQ trong dòng
        if not req_ids and tid in task_to_reqs:
            req_ids = task_to_reqs[tid]
        tasks.append({
            "id": tid,
            "raw": raw,
            "file_path": file_path,
            "function": function,
            "req_ids": req_ids,
        })
    return tasks


def _parse_req_ids(text: str) -> list[str]:
    """Trích danh sách REQ ID từ plan."""
    ids = re.findall(r"\bREQ[-_]?(\d+)\b", text, re.IGNORECASE)
    seen = []
    for n in ids:
        rid = f"REQ-{int(n):03d}"
        if rid not in seen:
            seen.append(rid)
    return seen


def generate_matrix(plan_path: Path) -> dict:
    """Sinh coverage matrix từ plan (chưa verify code thực tế).

    Trả về dict: {matrix: {...}, meta: {...}}.
    """
    text = _read_plan(plan_path)
    tasks = _parse_tasks(text)
    req_ids = _parse_req_ids(text)

    matrix: dict[str, dict] = {}
    # Bước 1: Khởi tạo mỗi REQ với status PLANNED
    for rid in req_ids:
        matrix[rid] = {
            "task_id": "",
            "file_path": "",
            "function": "",
            "status": STATUS_PLANNED,
            "evidence": "Chưa có task ánh xạ",
        }
    # Bước 2: Ánh xạ task vào REQ
    for t in tasks:
        for rid in t["req_ids"]:
            if rid not in matrix:
                matrix[rid] = {
                    "task_id": "",
                    "file_path": "",
                    "function": "",
                    "status": STATUS_PLANNED,
                    "evidence": "REQ xuất hiện trong task nhưng không có section requirement",
                }
            matrix[rid].update({
                "task_id": t["id"],
                "file_path": t["file_path"],
                "function": t["function"],
                "status": STATUS_PLANNED,
                "evidence": f"Task {t['id']} lên kế hoạch",
            })
    # Bước 3: Task không có REQ -> gắn vào key "_orphan_<tid>"
    for t in tasks:
        if not t["req_ids"]:
            key = f"_orphan_{t['id']}"
            matrix[key] = {
                "task_id": t["id"],
                "file_path": t["file_path"],
                "function": t["function"],
                "status": STATUS_PLANNED,
                "evidence": "Orphan task (không tham chiếu REQ)",
            }
    return {
        "plan_file": str(plan_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "req_count": len(req_ids),
        "task_count": len(tasks),
        "matrix": matrix,
    }


def _file_exists(repo_root: Path, file_path: str) -> Path | None:
    """Kiểm tra file có tồn tại trong repo không. Trả về Path nếu có, None nếu không."""
    if not file_path:
        return None
    # Thử đường dẫn tương đối từ repo root
    candidates = [
        repo_root / file_path,
        repo_root / file_path.lstrip("/\\"),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _grep_function(repo_root: Path, file_path: Path, function: str) -> bool:
    """Kiểm tra function có mặt trong file không (dùng grep qua subprocess).

    Trả True nếu tìm thấy định nghĩa function (def/func/function/function()).
    """
    if not function:
        return False
    # Bước 1: Tìm pattern định nghĩa function trong file
    patterns = [
        rf"\bdef\s+{re.escape(function)}\b",
        rf"\bfunc(?:tion)?\s+{re.escape(function)}\b",
        rf"\b{re.escape(function)}\s*[:=]\s*function",
        rf"\bexport\s+(?:async\s+)?function\s+{re.escape(function)}\b",
    ]
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for p in patterns:
        if re.search(p, content):
            return True
    # Bước 2: Fallback dùng grep qua subprocess (nếu đọc file thất bại hoặc pattern phức tạp)
    try:
        result = subprocess.run(
            ["grep", "-rE", patterns[0], str(file_path)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # grep không có trên Windows hoặc timeout -> bỏ qua, dùng kết quả regex
        pass
    return False


def verify_matrix(plan_path: Path) -> dict:
    """Sinh matrix rồi verify với code thực tế.

    Kiểm tra: file có tồn tại? function có mặt?
    Cập nhật status: PLANNED -> MISSING/EXECUTED/VERIFIED/FAIL.
    """
    result = generate_matrix(plan_path)
    matrix = result["matrix"]

    # Bước 1: Xác định repo root (đi lên cho tới khi thấy .devin hoặc .git)
    repo_root = plan_path.parent
    for parent in [plan_path.parent, *plan_path.parents]:
        if (parent / ".devin").exists() or (parent / ".git").exists():
            repo_root = parent
            break

    # Bước 2: Verify từng entry
    for rid, entry in matrix.items():
        fp = entry["file_path"]
        func = entry["function"]
        if not fp:
            # Không có file path -> giữ PLANNED (chưa thể verify)
            entry["evidence"] = "Không có file_path để verify"
            continue
        # Kiểm tra file tồn tại
        found = _file_exists(repo_root, fp)
        if found is None:
            entry["status"] = STATUS_MISSING
            entry["evidence"] = f"File không tồn tại: {fp}"
            continue
        # File tồn tại -> ít nhất EXECUTED
        entry["status"] = STATUS_EXECUTED
        entry["evidence"] = f"File tồn tại: {found.relative_to(repo_root)}"
        # Kiểm tra function nếu có
        if func:
            if _grep_function(repo_root, found, func):
                entry["status"] = STATUS_VERIFIED
                entry["evidence"] += f"; function '{func}' tìm thấy"
            else:
                entry["status"] = STATUS_FAIL
                entry["evidence"] += f"; function '{func}' KHÔNG tìm thấy"
        else:
            # Không có function để verify -> VERIFIED nếu file tồn tại
            entry["status"] = STATUS_VERIFIED
            entry["evidence"] += "; không yêu cầu function cụ thể"

    result["verified_at"] = datetime.now(timezone.utc).isoformat()
    # Đếm trạng thái
    status_counts: dict[str, int] = {}
    for entry in matrix.values():
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1
    result["status_counts"] = status_counts
    result["all_verified"] = all(
        entry["status"] in (STATUS_VERIFIED, STATUS_EXECUTED) for entry in matrix.values()
    )
    return result


def _render_markdown_report(data: dict) -> str:
    """Tạo báo cáo Markdown từ matrix."""
    matrix = data["matrix"]
    lines = [
        f"# Coverage Matrix — {Path(data['plan_file']).name}",
        "",
        f"- **Generated at**: {data.get('generated_at', '')}",
        f"- **Verified at**: {data.get('verified_at', 'N/A')}",
        f"- **REQ count**: {data.get('req_count', 0)}",
        f"- **Task count**: {data.get('task_count', 0)}",
    ]
    if "status_counts" in data:
        lines.append(f"- **Status counts**: {json.dumps(data['status_counts'], ensure_ascii=False)}")
    lines += ["", "## Matrix", "",
              "| REQ | Task | File | Function | Status | Evidence |",
              "|-----|------|------|----------|--------|----------|"]
    for rid in sorted(matrix.keys()):
        e = matrix[rid]
        ev = e["evidence"].replace("|", "\\|")
        lines.append(f"| {rid} | {e['task_id']} | {e['file_path']} | {e['function']} | {e['status']} | {ev} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Entry point CLI."""
    if len(sys.argv) < 2:
        print("Usage: python coverage_matrix.py <plan_file.md> [--verify]", file=sys.stderr)
        return 2
    plan_path = Path(sys.argv[1]).resolve()
    do_verify = "--verify" in sys.argv[2:]

    try:
        if do_verify:
            data = verify_matrix(plan_path)
        else:
            data = generate_matrix(plan_path)
    except (FileNotFoundError, ValueError) as e:
        # Edge case: plan thiếu hoặc rỗng
        print(json.dumps({"error": str(e), "plan_file": str(plan_path)}, ensure_ascii=False, indent=2))
        return 1

    # In JSON matrix ra stdout
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # Ghi báo cáo Markdown
    repo_root = plan_path.parent
    for parent in [plan_path.parent, *plan_path.parents]:
        if (parent / ".devin").exists() or (parent / ".git").exists():
            repo_root = parent
            break
    report_dir = repo_root / "docs" / "plans"
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_verified" if do_verify else ""
        report_path = report_dir / f"COVERAGE_MATRIX_{plan_path.stem}{suffix}.md"
        report_path.write_text(_render_markdown_report(data), encoding="utf-8")
        print(f"\n[REPORT] {report_path}", file=sys.stderr)
    except OSError as e:
        print(f"[WARN] Không ghi được report: {e}", file=sys.stderr)

    # Exit code: khi verify, 0 nếu all verified, 1 nếu có MISSING/FAIL
    if do_verify:
        return 0 if data.get("all_verified", False) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
