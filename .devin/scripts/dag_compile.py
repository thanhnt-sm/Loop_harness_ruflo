#!/usr/bin/env python3
"""dag_compile.py — Bien dich implementation plan thanh workflow DAG bat bien.

Parse IMPLEMENTATION_PLAN.md de trich xuat task va phu thuoc, xay dung DAG
(co huong khong chu trinh), validate, va bien dich thanh JSON workflow.

DAG: node = task, canh = phu thuoc (dependency).
Validation:
  - Acyclic check (topological sort)
  - Tat ca dependency target deu ton tai
  - Khong co orphan task (task khong co phu thuoc va khong bi ai phu thuoc,
    ngoai tru root tasks)

Output JSON workflow:
  {
    "workflow_id": str,
    "schema_version": 1,
    "tasks": [{"id", "goal", "dependencies", "agent", "file",
               "function", "acceptance_criteria"}],
    "edges": [{"from", "to"}]
  }

CLI:
  python dag_compile.py <plan_file.md> [--output <workflow.json>]

Ma thoat:
  0 = DAG hop le
  1 = DAG co chu trinh hoac khong hop le
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Cau hinh
PLAN_STATE_DIR = ".devin/plan_state"


def _repo_root() -> Path:
    """Tim thu muc goc repo (co .devin)."""
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


def parse_plan(plan_text: str) -> list:
    """Parse plan Markdown de trich xuat danh sach task.

    Moi task co dang:
      ## Task <id>: <description>
      - File: <file>
      - Function: <function>
      - Deps: <task_id1>, <task_id2>
      - Acceptance: <criteria>

    Tra ve list cac dict task.
    """
    tasks = []
    # Bước 1: tim moi block task (header ## Task ...)
    task_pattern = re.compile(
        r"^##\s+Task\s+(?P<id>[^\s:]+)\s*:\s*(?P<desc>.+)$",
        re.MULTILINE,
    )
    matches = list(task_pattern.finditer(plan_text))
    for i, m in enumerate(matches):
        task_id = m.group("id").strip()
        description = m.group("desc").strip()
        # Bước 2: lay noi dung block (tu header nay den header task tiep theo)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(plan_text)
        block = plan_text[start:end]

        # Bước 3: trich xuat cac truong
        file_match = re.search(r"^-?\s*\*?\*?File\*?\*?\s*:\s*(.+)$", block, re.MULTILINE | re.IGNORECASE)
        func_match = re.search(r"^-?\s*\*?\*?Function\*?\*?\s*:\s*(.+)$", block, re.MULTILINE | re.IGNORECASE)
        deps_match = re.search(r"^-?\s*\*?\*?Deps?\*?\*?\s*:\s*(.+)$", block, re.MULTILINE | re.IGNORECASE)
        accept_match = re.search(
            r"^-?\s*\*?\*?Acceptance(?:\s*Criteria)?\*?\*?\s*:\s*(.+)$",
            block, re.MULTILINE | re.IGNORECASE,
        )

        file = file_match.group(1).strip() if file_match else ""
        function = func_match.group(1).strip() if func_match else ""
        deps_raw = deps_match.group(1).strip() if deps_match else ""
        acceptance = accept_match.group(1).strip() if accept_match else ""

        # Parse deps: tach bang dau phay
        deps = []
        if deps_raw and deps_raw.lower() not in ("none", "n/a", "-"):
            deps = [d.strip() for d in re.split(r"[,;]", deps_raw) if d.strip()]

        tasks.append({
            "task_id": task_id,
            "description": description,
            "file": file,
            "function": function,
            "deps": deps,
            "acceptance_criteria": acceptance,
        })
    return tasks


def build_dag(tasks: list) -> tuple:
    """Xay dung DAG tu danh sach task.

    Tra ve (tasks_normalized, edges).
    """
    nodes = []
    edges = []
    for t in tasks:
        nodes.append({
            "id": t["task_id"],
            "goal": t["description"],
            "dependencies": t["deps"],
            "agent": "",
            "file": t["file"],
            "function": t["function"],
            "acceptance_criteria": t["acceptance_criteria"],
        })
        for dep in t["deps"]:
            # canh: dep -> task (dep phai chay truoc)
            edges.append({"from": dep, "to": t["task_id"]})
    return nodes, edges


def topological_sort(nodes: list, edges: list) -> tuple:
    """Sap xep topo de kiem tra acyclic.

    Tra ve (sorted_ids, cycle) — cycle la list id tao chu trinh (rong neu acyclic).
    """
    # Bước 1: xay dung adjacency list + in-degree
    ids = [n["id"] for n in nodes]
    adj = {tid: [] for tid in ids}
    in_degree = {tid: 0 for tid in ids}
    for e in edges:
        src, dst = e["from"], e["to"]
        if src in adj and dst in adj:
            adj[src].append(dst)
            in_degree[dst] += 1

    # Bước 2: Kahn's algorithm
    queue = [tid for tid in ids if in_degree[tid] == 0]
    sorted_ids = []
    while queue:
        node = queue.pop(0)
        sorted_ids.append(node)
        for nb in adj[node]:
            in_degree[nb] -= 1
            if in_degree[nb] == 0:
                queue.append(nb)

    # Bước 3: neu chua sap xet het -> co chu trinh
    if len(sorted_ids) == len(ids):
        return sorted_ids, []

    # Tim cac node con lai (trong chu trinh)
    remaining = [tid for tid in ids if tid not in sorted_ids]
    return sorted_ids, remaining


def validate_dag(nodes: list, edges: list) -> tuple:
    """Validate DAG: acyclic, dependency ton tai, orphan task.

    Tra ve (valid, errors) — errors la list thong bao loi.
    """
    errors = []
    ids = {n["id"] for n in nodes}

    # Bước 1: kiem tra dependency target ton tai
    for e in edges:
        if e["from"] not in ids:
            errors.append(f"dependency khong ton tai: task '{e['to']}' phu thuoc '{e['from']}' khong co")
        if e["to"] not in ids:
            errors.append(f"canh chi den task khong ton tai: '{e['to']}'")

    # Bước 2: kiem tra acyclic
    _, cycle = topological_sort(nodes, edges)
    if cycle:
        errors.append(f"phat hien chu trinh: {' -> '.join(cycle)}")

    # Bước 3: kiem tra orphan task (khong co deps va khong bi ai phu thuoc)
    has_deps = {n["id"] for n in nodes if n.get("dependencies")}
    is_depended_on = {e["from"] for e in edges if e["from"] in ids}
    orphans = ids - has_deps - is_depended_on
    if orphans and len(nodes) > 1:
        errors.append(f"orphan task (khong lien ket): {sorted(orphans)}")

    return len(errors) == 0, errors


def compile_plan(root: Path, plan_file: Path, output: Path | None = None) -> int:
    """Bien dich plan file thanh workflow JSON.

    Tra ve ma thoat (0 = thanh cong, 1 = loi).
    """
    # Bước 1: kiem tra file plan ton tai
    if not plan_file.exists():
        print(f"[ERROR] Khong tim thay file plan: {plan_file}")
        return 1

    try:
        plan_text = plan_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"[ERROR] Khong the doc file plan: {e}")
        return 1

    # Bước 2: parse task
    except Exception as e:
        print(f"[ERROR] Khong the doc file plan: {e}")
        return 1

    # Bước 2: parse task
    tasks = parse_plan(plan_text)
    if not tasks:
        print("[ERROR] Khong tim thay task nao trong plan (can header '## Task <id>: <desc>')")
        return 1

    # Bước 3: xay dung DAG
    nodes, edges = build_dag(tasks)

    # Bước 4: validate
    valid, errors = validate_dag(nodes, edges)
    if not valid:
        print("[FAIL] DAG khong hop le:")
        for err in errors:
            print(f"  - {err}")
        return 1

    # Bước 5: bien dich thanh workflow JSON (schema v1)
    workflow_id = plan_file.stem
    workflow = {
        "workflow_id": workflow_id,
        "schema_version": 1,
        "source": str(plan_file.relative_to(root)) if plan_file.is_relative_to(root) else str(plan_file),
        "tasks": nodes,
        "edges": edges,
        "compiled_at": __import__("datetime").datetime.now().isoformat(),
    }

    # Bước 6: ghi output
    if output is None:
        output = root / PLAN_STATE_DIR / f"{workflow_id}_workflow.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[OK] DAG hop le: {len(nodes)} node, {len(edges)} canh")
    print(f"[OK] Workflow da bien dich: {output}")
    return 0


def main() -> int:
    """Xu ly CLI."""
    import argparse
    ap = argparse.ArgumentParser(description="Bien dich plan thanh workflow DAG")
    ap.add_argument("plan_file", help="Duong dan den file plan Markdown")
    ap.add_argument("--output", help="Duong dan output workflow JSON (mac dinh: .devin/plan_state/<name>_workflow.json)")
    ap.add_argument("--root", default=".", help="Thu muc goc repo")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    plan_file = Path(args.plan_file)
    if not plan_file.is_absolute():
        plan_file = root / plan_file
    output = Path(args.output) if args.output else None
    if output and not output.is_absolute():
        output = root / output

    return compile_plan(root, plan_file, output)


if __name__ == "__main__":
    sys.exit(main())
