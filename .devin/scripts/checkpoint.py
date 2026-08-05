#!/usr/bin/env python3
"""checkpoint.py — Luu/phuc hoi trang thai (checkpointed backtracking).

Luu checkpoint (snapshot trang thai) cho moi buoc trong workflow, cho phep
phuc hoi (restore) khi that bai, va danh dau cac buoc xuong dong (downstream)
la "needs_replay" de chay lai.

Checkpoint structure:
  {
    "step_id": str,
    "state_snapshot": dict,   # ban sao chep sau trang thai
    "timestamp": str,         # ISO format
    "dependencies": list,     # cac buoc phu thuoc
    "downstream_steps": list  # cac buoc xuong dong
  }

CLI:
  python checkpoint.py <workflow.json> --save <step_id> <state_file>
  python checkpoint.py <workflow.json> --restore <step_id>
  python checkpoint.py <workflow.json> --list

Trang thai:
  .devin/checkpoints/<workflow_id>/

Repair memory: ghi loi + phuc hoi vao .devin/telemetry/repair_memory.json.

Ma thoat:
  0 = thanh cong
  1 = khong tim thay checkpoint an toan / loi
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Cau hinh
CHECKPOINTS_DIR = ".devin/checkpoints"
REPAIR_MEMORY_FILE = ".devin/telemetry/repair_memory.json"


def _repo_root() -> Path:
    """Tim thu muc goc repo (co .devin)."""
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


def _load_json(path: Path, default):
    """Doc JSON an toan (tra ve default neu loi/khong ton tai)."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> None:
    """Ghi JSON an toan."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[checkpoint] khong the ghi {path}: {e}", file=sys.stderr)


def _checkpoints_root(root: Path, workflow_id: str) -> Path:
    """Duong dan thu muc checkpoint cho workflow."""
    return root / CHECKPOINTS_DIR / workflow_id


def _load_workflow(root: Path, workflow_path: Path) -> dict | None:
    """Tai workflow JSON. Tra ve None neu khong ton tai / hong."""
    if not workflow_path.exists():
        print(f"[ERROR] Khong tim thay workflow file: {workflow_path}")
        return None
    try:
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"[ERROR] Workflow file hong: {e}")
        return None
    return None


def _build_downstream_map(workflow: dict) -> dict:
    """Xay dung anh xa: step_id -> list downstream steps (transitive).

    Dua vao edges (from -> to): downstream cua X = tat ca node ma X co the den.
    """
    edges = workflow.get("edges", [])
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
    # Tinh transitive downstream bang BFS
    downstream = {}
    nodes = {n["task_id"] for n in workflow.get("nodes", [])}
    for start in nodes:
        visited = set()
        queue = list(adj.get(start, []))
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            queue.extend(adj.get(node, []))
        downstream[start] = sorted(visited)
    return downstream


def _dependencies_for(workflow: dict, step_id: str) -> list:
    """Lay danh sach phu thuoc cua 1 step tu workflow."""
    for n in workflow.get("nodes", []):
        if n["task_id"] == step_id:
            return n.get("deps", [])
    return []


def cmd_save(root: Path, workflow: dict, workflow_id: str, step_id: str, state_file: str) -> int:
    """Luu checkpoint cho 1 buoc: snapshot trang thai, timestamp, deps, downstream."""
    # Bước 1: doc state file (snapshot sau trang thai)
    state_path = Path(state_file)
    if not state_path.is_absolute():
        state_path = root / state_path
    if not state_path.exists():
        print(f"[ERROR] Khong tim thay state file: {state_path}")
        return 1
    try:
        snapshot = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] State file hong: {e}")
        return 1

    # Bước 2: tinh dependencies + downstream
    deps = _dependencies_for(workflow, step_id)
    downstream_map = _build_downstream_map(workflow)
    downstream = downstream_map.get(step_id, [])

    # Bước 3: tao checkpoint
    checkpoint = {
        "step_id": step_id,
        "state_snapshot": snapshot,
        "timestamp": datetime.now().isoformat(),
        "dependencies": deps,
        "downstream_steps": downstream,
    }

    # Bước 4: luu vao thu muc checkpoint
    ckpt_dir = _checkpoints_root(root, workflow_id)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    # Luu theo step_id + timestamp de giu lich su
    safe_step = step_id.replace("/", "_")
    ckpt_path = ckpt_dir / f"{safe_step}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    _save_json(ckpt_path, checkpoint)
    # Cap nhat index
    index_path = ckpt_dir / "index.json"
    index = _load_json(index_path, {"checkpoints": []})
    if not isinstance(index, dict):
        index = {"checkpoints": []}
    index.setdefault("checkpoints", []).append({
        "step_id": step_id,
        "file": ckpt_path.name,
        "timestamp": checkpoint["timestamp"],
    })
    _save_json(index_path, index)

    print(f"[OK] Da luu checkpoint cho step '{step_id}': {ckpt_path}")
    print(f"     Dependencies: {deps}")
    print(f"     Downstream: {downstream}")
    return 0


def _find_latest_checkpoint(ckpt_dir: Path, step_id: str) -> Path | None:
    """Tim checkpoint moi nhat cho 1 step_id."""
    index = _load_json(ckpt_dir / "index.json", {"checkpoints": []})
    entries = [c for c in index.get("checkpoints", []) if c.get("step_id") == step_id]
    if not entries:
        return None
    # Sap xep theo timestamp giam dan
    entries.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
    return ckpt_dir / entries[0]["file"]


def _find_safe_checkpoint_before(ckpt_dir: Path, failed_step: str, workflow: dict) -> Path | None:
    """Tim checkpoint an toan moi nhat TRUOC buoc that bai.

    Uu tien checkpoint cua cac dependency gan nhat cua failed_step.
    Tra ve duong dan checkpoint, None neu khong co.
    """
    # Bước 1: lay dependencies cua failed_step
    deps = _dependencies_for(workflow, failed_step)
    # Bước 2: tim checkpoint moi nhat cua moi dep (uu tien dep cuoi cung)
    candidates = []
    for dep in reversed(deps):
        ckpt = _find_latest_checkpoint(ckpt_dir, dep)
        if ckpt and ckpt.exists():
            candidates.append(ckpt)
    # Bước 3: neu khong co dep checkpoint -> tim bat ky checkpoint truoc failed_step
    if not candidates:
        index = _load_json(ckpt_dir / "index.json", {"checkpoints": []})
        all_entries = index.get("checkpoints", [])
        # Sap xep theo timestamp giam dan, bo qua failed_step
        all_entries = [c for c in all_entries if c.get("step_id") != failed_step]
        all_entries.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
        for entry in all_entries:
            p = ckpt_dir / entry["file"]
            if p.exists():
                candidates.append(p)
                break
    return candidates[0] if candidates else None


def cmd_restore(root: Path, workflow: dict, workflow_id: str, failed_step: str) -> int:
    """Phuc hoi: tim checkpoint an toan truoc failed_step, restore, invalidate downstream."""
    ckpt_dir = _checkpoints_root(root, workflow_id)
    if not ckpt_dir.exists():
        print(f"[ERROR] Khong co checkpoint nao cho workflow '{workflow_id}'")
        return 1

    # Bước 1: tim checkpoint an toan truoc failed_step
    safe_ckpt = _find_safe_checkpoint_before(ckpt_dir, failed_step, workflow)
    if not safe_ckpt:
        print(f"[ERROR] Khong tim thay checkpoint an toan truoc step '{failed_step}'")
        return 1

    # Bước 2: doc checkpoint (xu ly state hong)
    try:
        checkpoint = json.loads(safe_ckpt.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Checkpoint hong, bo qua: {safe_ckpt} ({e})")
        # Thu checkpoint ke tiep
        return 1

    # Bước 3: phuc hoi state snapshot
    restored_step = checkpoint["step_id"]
    snapshot = checkpoint.get("state_snapshot", {})
    # Ghi snapshot ra file restore
    restore_path = ckpt_dir / f"restored_{restored_step}.json"
    _save_json(restore_path, snapshot)

    # Bước 4: invalidate downstream (danh dau needs_replay)
    downstream_map = _build_downstream_map(workflow)
    downstream = downstream_map.get(restored_step, [])
    replay_path = ckpt_dir / "replay_queue.json"
    replay = _load_json(replay_path, {"steps": []})
    if not isinstance(replay, dict):
        replay = {"steps": []}
    existing = {s["step_id"] for s in replay.get("steps", [])}
    for step in downstream:
        if step not in existing:
            replay.setdefault("steps", []).append({
                "step_id": step,
                "reason": f"invalidated_sau_restore_{restored_step}",
                "timestamp": datetime.now().isoformat(),
            })
    _save_json(replay_path, replay)

    # Bước 5: ghi repair memory
    memory = _load_json(root / REPAIR_MEMORY_FILE, {"entries": []})
    if not isinstance(memory, dict):
        memory = {"entries": []}
    memory.setdefault("entries", []).append({
        "timestamp": datetime.now().isoformat(),
        "event": "checkpoint_restore",
        "failed_step": failed_step,
        "restored_from": restored_step,
        "checkpoint_file": str(safe_ckpt),
        "invalidated_steps": downstream,
    })
    if len(memory["entries"]) > 200:
        memory["entries"] = memory["entries"][-200:]
    _save_json(root / REPAIR_MEMORY_FILE, memory)

    print(f"[OK] Da phuc hoi tu checkpoint step '{restored_step}': {safe_ckpt}")
    print(f"     State restore: {restore_path}")
    print(f"     Downstream invalidated (needs_replay): {downstream}")
    return 0


def cmd_list(root: Path, workflow: dict, workflow_id: str) -> int:
    """Liet ke tat ca checkpoint cua 1 workflow."""
    ckpt_dir = _checkpoints_root(root, workflow_id)
    if not ckpt_dir.exists():
        print(f"[INFO] Chua co checkpoint nao cho workflow '{workflow_id}'")
        return 0
    index = _load_json(ckpt_dir / "index.json", {"checkpoints": []})
    entries = index.get("checkpoints", [])
    if not entries:
        print(f"[INFO] Chua co checkpoint nao cho workflow '{workflow_id}'")
        return 0
    print(f"Checkpoints cho workflow '{workflow_id}' ({len(entries)}):")
    for entry in sorted(entries, key=lambda c: c.get("timestamp", "")):
        print(f"  - step: {entry['step_id']} | file: {entry['file']} | time: {entry['timestamp']}")
    # Hien thi replay queue neu co
    replay_path = ckpt_dir / "replay_queue.json"
    if replay_path.exists():
        replay = _load_json(replay_path, {"steps": []})
        steps = replay.get("steps", [])
        if steps:
            print(f"\nReplay queue ({len(steps)} buoc can chay lai):")
            for s in steps:
                print(f"  - {s['step_id']}: {s.get('reason', '')}")
    return 0


def main() -> int:
    """Xu ly CLI."""
    import argparse
    ap = argparse.ArgumentParser(description="Checkpointed backtracking — luu/phuc hoi trang thai")
    ap.add_argument("workflow", help="Duong dan den workflow JSON")
    ap.add_argument("--save", nargs=2, metavar=("STEP_ID", "STATE_FILE"), help="Luu checkpoint cho 1 buoc")
    ap.add_argument("--restore", metavar="STEP_ID", help="Phuc hoi tu checkpoint an toan truoc buoc that bai")
    ap.add_argument("--list", action="store_true", help="Liet ke tat ca checkpoint")
    ap.add_argument("--root", default=".", help="Thu muc goc repo")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    workflow_path = Path(args.workflow)
    if not workflow_path.is_absolute():
        workflow_path = root / workflow_path

    workflow = _load_workflow(root, workflow_path)
    if workflow is None:
        return 1
    workflow_id = workflow.get("workflow_id", workflow_path.stem)

    if args.save:
        step_id, state_file = args.save
        return cmd_save(root, workflow, workflow_id, step_id, state_file)
    elif args.restore:
        return cmd_restore(root, workflow, workflow_id, args.restore)
    elif args.list:
        return cmd_list(root, workflow, workflow_id)
    else:
        ap.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
