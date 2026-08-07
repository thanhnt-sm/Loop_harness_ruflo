#!/usr/bin/env python3
"""build_workflow.py — biên dịch IMPLEMENTATION_PLAN.md thành workflow JSON cho dag_executor.

Đọc task table và Mermaid DAG, xây dựng danh sách tasks với dependencies phù hợp dag_executor.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Đưa thư mục chứa plan_quality_check vào path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / ".devin" / "scripts"))

import plan_quality_check as pqc  # type: ignore


def main() -> int:
    plan_path = ROOT / "docs" / "plans" / "conduct-a-comprehensive-adversarial-red-team-audit-and-long-" / "IMPLEMENTATION_PLAN.md"
    text = pqc._read_plan(plan_path)
    tasks = pqc._parse_tasks(text)
    edges = pqc._parse_mermaid_edges(text)

    task_ids = {t["id"] for t in tasks}
    deps: dict[str, list[str]] = {t["id"]: [] for t in tasks}
    # Mermaid edge A --> B nghĩa là B phụ thuộc A
    for src, dst in edges:
        if src in task_ids and dst in task_ids and src not in deps[dst]:
            deps[dst].append(src)

    workflow_tasks = []
    for t in tasks:
        workflow_tasks.append({
            "id": t["id"],
            "goal": t.get("raw", ""),
            "dependencies": sorted(deps[t["id"]]),
            "agent": "",
            "file": t.get("file_path", ""),
            "function": "",
            "acceptance_criteria": t.get("ac", ""),
        })

    workflow = {
        "workflow_id": plan_path.stem,
        "source": str(plan_path.relative_to(ROOT)),
        "tasks": workflow_tasks,
        "compiled_at": __import__("datetime").datetime.now().isoformat(),
    }

    out_dir = ROOT / ".devin" / "plan_state"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{plan_path.stem}_workflow.json"
    out_path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[OK] Workflow: {len(workflow_tasks)} tasks, {len(edges)} edges")
    print(f"[OK] Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
