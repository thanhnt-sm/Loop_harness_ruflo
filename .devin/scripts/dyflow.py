#!/usr/bin/env python3
"""dyflow.py — Dynamic Workflow (T4.12, REQ-019).

Mục đích: phát hiện dependency giữa các file trong workspace, xây graph, rồi
generate workflow (DAG) từ graph đó. Workflow sinh ra khác static baseline
vì dựa trên dependency thực tế.

Hàm chính:
  - discover_deps(workspace: Path) -> Graph
  - generate_workflow(graph: Graph) -> Workflow

Graph: dict dạng {node: [dependencies]}.
Workflow: dict dạng {nodes: [...], edges: [...], order: [topo_order]}.

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
File < 500 dòng, typed interface (Pydantic).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# --- Graph / Workflow schema ---
class Graph(BaseModel):
    """Dependency graph: node -> list dependency."""
    nodes: list[str] = Field(default_factory=list, max_length=500)
    edges: dict[str, list[str]] = Field(default_factory=dict)
    workspace: str = Field(max_length=512)


class Workflow(BaseModel):
    """Workflow DAG sinh ra từ graph."""
    nodes: list[str] = Field(default_factory=list, max_length=500)
    edges: list[tuple[str, str]] = Field(default_factory=list, max_length=1000)
    order: list[str] = Field(default_factory=list, max_length=500)
    has_cycle: bool = False


# --- Pattern phát hiện dependency ---
# Python: import statements, from X import Y
_PY_IMPORT_RE = re.compile(
    r'^\s*(?:from\s+([\w\.]+)\s+import\s+([\w\.,\s]+)|import\s+([\w\.]+))',
    re.MULTILINE,
)
# Relative import: from . import X, from .. import X, from .sub import Y
_PY_REL_IMPORT_RE = re.compile(
    r'^\s*from\s+(\.+)([\w\.]*)\s+import\s+([\w\.,\s]+)',
    re.MULTILINE,
)


def _normalize_module_to_path(module: str, current_file: Path, workspace: Path) -> str | None:
    """Chuyển module name thành đường dẫn file tương đối workspace.

    Vd: 'mymodule.utils' -> 'mymodule/utils.py' (hoặc __init__.py).
    Trả về None nếu không ánh xạ được.
    """
    if not module:
        return None
    parts = module.split(".")
    # Bỏ phần tử rỗng
    parts = [p for p in parts if p]
    if not parts:
        return None
    # Thử .py
    candidate = workspace.joinpath(*parts).with_suffix(".py")
    if candidate.exists():
        try:
            return str(candidate.relative_to(workspace)).replace("\\", "/")
        except ValueError:
            return None
    # Thử __init__.py (package)
    candidate = workspace.joinpath(*parts, "__init__.py")
    if candidate.exists():
        try:
            return str(candidate.relative_to(workspace)).replace("\\", "/")
        except ValueError:
            return None
    return None


def _resolve_relative_import(
    dots: str, submodule: str, current_file: Path, workspace: Path
) -> str | None:
    """Resolve relative import (from . import X) thành đường dẫn file."""
    # Đếm số dấu chấm: 1 = cùng package, 2 = cha, ...
    level = len(dots)
    current_rel = current_file.relative_to(workspace) if current_file.is_absolute() else current_file
    parts = list(current_rel.parts)
    # Bỏ tên file, giữ thư mục cha
    if parts and parts[-1].endswith(".py"):
        parts = parts[:-1]
    # Lên level-1 cấp
    for _ in range(level - 1):
        if parts:
            parts.pop()
        else:
            return None
    if submodule:
        parts.extend(submodule.split("."))
    if not parts:
        return None
    candidate = workspace.joinpath(*parts).with_suffix(".py")
    if candidate.exists():
        try:
            return str(candidate.relative_to(workspace)).replace("\\", "/")
        except ValueError:
            return None
    candidate = workspace.joinpath(*parts, "__init__.py")
    if candidate.exists():
        try:
            return str(candidate.relative_to(workspace)).replace("\\", "/")
        except ValueError:
            return None
    return None


def _discover_python_deps(file_path: Path, workspace: Path) -> list[str]:
    """Phát hiện dependency của một file Python."""
    deps: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return deps

    # Absolute imports: from X import Y, hoặc import X
    except Exception:
        return deps

    # Absolute imports: from X import Y, hoặc import X
    for m in _PY_IMPORT_RE.finditer(content):
        # group(1) = module (from X), group(2) = imported names (from X import Y)
        # group(3) = module (import X)
        module = m.group(1) or m.group(3)
        if not module:
            continue
        # Bỏ stdlib / third-party (không có path tương ứng trong workspace)
        resolved = _normalize_module_to_path(module, file_path, workspace)
        if resolved and resolved not in deps:
            deps.append(resolved)
        # Nếu là `from X import Y`, Y có thể là submodule của X
        if m.group(1) and m.group(2):
            for name in m.group(2).split(","):
                name = name.strip().split(" as ")[0].strip()
                if not name:
                    continue
                sub_module = f"{module}.{name}"
                resolved = _normalize_module_to_path(sub_module, file_path, workspace)
                if resolved and resolved not in deps:
                    deps.append(resolved)

    # Relative imports: from . import X, from .sub import Y
    for m in _PY_REL_IMPORT_RE.finditer(content):
        dots = m.group(1)
        submodule = m.group(2) or ""
        imported_names = m.group(3) or ""
        # Resolve package itself (from . import -> __init__.py của package)
        resolved = _resolve_relative_import(dots, submodule, file_path, workspace)
        if resolved and resolved not in deps:
            deps.append(resolved)
        # Mỗi imported name có thể là module trong package
        for name in imported_names.split(","):
            name = name.strip().split(" as ")[0].strip()
            if not name:
                continue
            full_sub = f"{submodule}.{name}" if submodule else name
            resolved = _resolve_relative_import(dots, full_sub, file_path, workspace)
            if resolved and resolved not in deps:
                deps.append(resolved)

    return deps


def discover_deps(workspace: Path) -> Graph:
    """Phát hiện dependency giữa các file Python trong workspace.

    Nhận vào:
        workspace — thư mục cần quét (Path).

    Trả về Graph với:
      - nodes: danh sách file .py (relative path, / separator).
      - edges: dict {file: [dependency files]}.
      - workspace: đường dẫn workspace.
    """
    if not isinstance(workspace, Path):
        raise TypeError("workspace phải là Path")
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"workspace không tồn tại hoặc không phải thư mục: {workspace}")

    nodes: list[str] = []
    edges: dict[str, list[str]] = {}

    # Bước 1: thu thập tất cả file .py
    for py_file in sorted(workspace.rglob("*.py")):
        try:
            rel = py_file.relative_to(workspace)
        except ValueError:
            continue
        # Bỏ __pycache__
        if "__pycache__" in rel.parts:
            continue
        norm = str(rel).replace("\\", "/")
        nodes.append(norm)

    # Bước 2: phát hiện dependency cho mỗi file
    for node in nodes:
        file_path = workspace / node
        deps = _discover_python_deps(file_path, workspace)
        # Chỉ giữ dependency tồn tại trong nodes (chính là workspace)
        deps = [d for d in deps if d in nodes and d != node]
        edges[node] = deps

    return Graph(nodes=nodes, edges=edges, workspace=str(workspace))


def _topo_sort(nodes: list[str], edges: dict[str, list[str]]) -> tuple[list[str], bool]:
    """Topological sort (Kahn's algorithm). Trả về (order, has_cycle)."""
    # Bước 1: tính in-degree
    in_degree: dict[str, int] = {n: 0 for n in nodes}
    for node, deps in edges.items():
        # edge: dep -> node (node phụ thuộc dep, dep phải chạy trước)
        for dep in deps:
            if dep in in_degree:
                in_degree[node] = in_degree.get(node, 0) + 1

    # Bước 2: queue các node in_degree=0
    queue: list[str] = [n for n in nodes if in_degree.get(n, 0) == 0]
    order: list[str] = []
    # Sắp xếp queue để deterministic
    queue.sort()

    while queue:
        node = queue.pop(0)
        order.append(node)
        # Giảm in-degree của các node phụ thuộc node
        for other in nodes:
            if node in edges.get(other, []):
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    # Insert sorted để deterministic
                    inserted = False
                    for i, q in enumerate(queue):
                        if other < q:
                            queue.insert(i, other)
                            inserted = True
                            break
                    if not inserted:
                        queue.append(other)

    has_cycle = len(order) != len(nodes)
    return order, has_cycle


def generate_workflow(graph: Graph) -> Workflow:
    """Sinh workflow DAG từ dependency graph.

    Nhận vào:
        graph — Graph từ discover_deps.

    Trả về Workflow với:
      - nodes: danh sách node.
      - edges: list tuple (dep, node) — dep phải chạy trước node.
      - order: topological order (rỗng nếu có cycle).
      - has_cycle: True nếu graph có chu trình.
    """
    if not isinstance(graph, Graph):
        raise TypeError("graph phải là Graph")

    # Bước 1: xây edge list (dep -> node)
    edge_list: list[tuple[str, str]] = []
    for node, deps in graph.edges.items():
        for dep in deps:
            edge_list.append((dep, node))

    # Bước 2: topo sort
    order, has_cycle = _topo_sort(graph.nodes, graph.edges)

    return Workflow(
        nodes=graph.nodes,
        edges=edge_list,
        order=order,
        has_cycle=has_cycle,
    )


def _cli() -> int:
    """CLI stub: discover_deps + generate_workflow, in JSON."""
    import json
    if len(sys.argv) < 2:
        print("Usage: dyflow.py <workspace_path>", file=sys.stderr)
        return 1
    workspace = Path(sys.argv[1])
    try:
        graph = discover_deps(workspace)
        workflow = generate_workflow(graph)
        out = {
            "graph": graph.model_dump(),
            "workflow": workflow.model_dump(),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"[dyflow] lỗi: {e}", file=sys.stderr)
        return 1


    except Exception as e:
        print(f"[dyflow] lỗi: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
