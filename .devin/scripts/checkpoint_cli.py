#!/usr/bin/env python3
"""checkpoint_cli.py — CLI commands for checkpoint operations.

Handles save, restore, list commands and main entry point.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Import from sub-modules (absolute imports)
from checkpoint_core import (
    _checkpoints_root,
    _load_json,
    _repo_root,
    _safe_ckpt_path,
    _save_json,
    migrate,
    save,
)
from checkpoint_workflow import (
    _build_downstream_map,
    _dependencies_for,
    _load_workflow,
)
from checkpoint_sanitize import _sanitize_step_id


REPAIR_MEMORY_FILE = ".devin/telemetry/repair_memory.json"


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
    except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError) as e:
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
    # Pentest fix: dùng _sanitize_step_id (allowlist) thay vì chỉ thay '/' để chống backslash traversal.
    safe_step = _sanitize_step_id(step_id)
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
    for entry in entries:
        p = _safe_ckpt_path(ckpt_dir, entry.get("file", ""))
        if p is not None:
            return p
    return None


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
            p = _safe_ckpt_path(ckpt_dir, entry.get("file", ""))
            if p is not None and p.exists():
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
    except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError) as e:
        print(f"[WARN] Checkpoint hong, bo qua: {safe_ckpt} ({e})")
        # Thu checkpoint ke tiep
        return 1

    # Bước 3: phuc hoi state snapshot
    restored_step = _sanitize_step_id(str(checkpoint.get("step_id", "unknown")))
    snapshot = checkpoint.get("state_snapshot", {})
    # Ghi snapshot ra file restore (chroot trong ckpt_dir — CVE-2026-AHD-004)
    restore_path = _safe_ckpt_path(ckpt_dir, f"restored_{restored_step}.json")
    if restore_path is None:
        print(f"[ERROR] Khong the tao file restore (path traversal blocked)", file=sys.stderr)
        return 1
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