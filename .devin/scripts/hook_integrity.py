#!/usr/bin/env python3
"""U41: Hook integrity verification (SHA256) + hook chain order verification.

Kiểm tra toàn vẹn hook (SHA256) và thứ tự chuỗi hook.
- `--verify` / `--generate`: so sánh/generate hash baseline cho từng file hook.
- `--verify-order` / `--regen`: so sánh/generate baseline thứ tự chuỗi hook
  (pre_tool_use -> plan_enforce -> schema_gate -> coverage_enforce -> otel_instrument
  -> [tool execution] -> post_tool_use).

Usage:
    python .devin/scripts/hook_integrity.py --generate       # Generate SHA256 baseline
    python .devin/scripts/hook_integrity.py --verify         # Verify against baseline
    python .devin/scripts/hook_integrity.py --status         # Show status
    python .devin/scripts/hook_integrity.py --regen          # Generate hook order baseline
    python .devin/scripts/hook_integrity.py --verify-order   # Verify hook order baseline
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


HOOKS_DIR = ".devin/hooks"
BASELINE_FILE = ".devin/hook_hashes.json"
ORDER_BASELINE_FILE = ".devin/hook_order.json"
CONFIG_FILE = ".devin/config.json"

# Thứ tự chuỗi hook chuẩn (canonical hook chain order).
# pre_tool_use -> plan_enforce -> schema_gate -> coverage_enforce -> otel_instrument (pre)
# -> [tool execution] -> post_tool_use.
CANONICAL_ORDER: list[str] = [
    "pre_tool_use",
    "plan_enforce",
    "schema_gate",
    "coverage_enforce",
    "otel_instrument",
    "post_tool_use",
]

# Thứ tự event trong config.json để trích xuất order (PreToolUse chạy trước PostToolUse).
_EVENT_ORDER: list[str] = [
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PostCompaction",
]

# Pattern trích tên hook từ command dạng `python .devin/hooks/<name>.py`.
_HOOK_CMD_RE = re.compile(r"\.devin/hooks/([a-zA-Z0-9_]+)\.py")


def compute_sha256(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_hook_files(root: Path) -> list[Path]:
    """Get all hook files."""
    hooks_dir = root / HOOKS_DIR
    if not hooks_dir.exists():
        return []
    return sorted(hooks_dir.glob("*.py"))


def generate_baseline(root: Path) -> int:
    """Generate SHA256 baseline for all hooks."""
    hooks = get_hook_files(root)
    if not hooks:
        print("[ERROR] No hook files found")
        return 1

    baseline = {}
    for h in hooks:
        rel = str(h.relative_to(root)).replace("\\", "/")
        baseline[rel] = compute_sha256(h)
        print(f"[HASH] {rel}: {baseline[rel][:16]}...")

    baseline_path = root / BASELINE_FILE
    baseline_data = {
        "_description": "U41: Hook integrity verification baseline",
        "_generated": str(Path.now() if hasattr(Path, 'now') else ""),
        "hooks": baseline,
    }

    from datetime import datetime
    baseline_data["_generated"] = datetime.now().isoformat()

    baseline_path.write_text(json.dumps(baseline_data, indent=2), encoding="utf-8")
    print(f"\n[OK] Baseline generated: {baseline_path} ({len(hooks)} hooks)")
    return 0


def verify_integrity(root: Path) -> int:
    """Verify hooks against baseline."""
    baseline_path = root / BASELINE_FILE
    if not baseline_path.exists():
        print("[ERROR] No baseline found. Run --generate first.")
        return 1

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    stored = baseline.get("hooks", {})

    hooks = get_hook_files(root)
    if not hooks:
        print("[ERROR] No hook files found")
        return 1

    violations = 0
    for h in hooks:
        rel = str(h.relative_to(root)).replace("\\", "/")
        current_hash = compute_sha256(h)

        if rel not in stored:
            print(f"[NEW] {rel}: not in baseline (new hook?)")
            violations += 1
        elif stored[rel] != current_hash:
            print(f"[TAMPERED] {rel}: hash mismatch")
            print(f"  baseline: {stored[rel][:16]}...")
            print(f"  current:  {current_hash[:16]}...")
            violations += 1
        else:
            print(f"[OK] {rel}: verified")

    # Check for missing hooks (in baseline but not on disk)
    for rel in stored:
        if not (root / rel).exists():
            print(f"[MISSING] {rel}: in baseline but not on disk")
            violations += 1

    if violations == 0:
        print(f"\n[OK] All {len(hooks)} hooks verified. No tampering detected.")
        return 0
    else:
        print(f"\n[FAIL] {violations} violation(s) detected. Review above.")
        return 1


def show_status(root: Path) -> int:
    """Show integrity status."""
    baseline_path = root / BASELINE_FILE
    if not baseline_path.exists():
        print("[STATUS] No baseline generated. Run: --generate")
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    stored = baseline.get("hooks", {})
    hooks = get_hook_files(root)

    print(f"Baseline: {len(stored)} hooks")
    print(f"On disk:  {len(hooks)} hooks")
    print(f"Generated: {baseline.get('_generated', 'unknown')}")

    if len(stored) == len(hooks):
        print("[STATUS] Counts match. Run --verify for full check.")
    else:
        print("[STATUS] Count mismatch! Run --verify.")

    return 0


def extract_hook_order(root: Path) -> list[str]:
    """Trích xuất thứ tự hook từ config.json.

    Duyệt qua các event theo _EVENT_ORDER, trong mỗi event duyệt từng matcher group
    và từng hook theo thứ tự khai báo; lấy tên hook (không có .py) từ command dạng
    `python .devin/hooks/<name>.py`. Giữ thứ tự xuất hiện để phản ánh chuỗi hook thực tế.

    Trả về danh sách tên hook theo thứ tự xuất hiện trong config.
    """
    config_path = root / CONFIG_FILE
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy config: {config_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Lỗi đọc config.json: {exc}") from exc

    hooks_cfg = config.get("hooks", {})
    order: list[str] = []
    for event in _EVENT_ORDER:
        groups = hooks_cfg.get(event, [])
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if not isinstance(hook, dict):
                    continue
                cmd = hook.get("command", "") or ""
                m = _HOOK_CMD_RE.search(cmd)
                if m:
                    name = m.group(1)
                    if name not in order:
                        order.append(name)
    return order


def compare_order(actual: list[str], expected: list[str]) -> tuple[bool, list[str]]:
    """So sánh thứ tự hook thực tế với baseline.

    Trả về (match, diffs). match=True nếu hai danh sách bằng nhau (cùng thứ tự).
    diffs là danh sách mô tả khác biệt để hiển thị cho người dùng.
    """
    diffs: list[str] = []
    if actual == expected:
        return True, []

    # Bước 1: phát hiện hook có trong baseline nhưng thiếu trong actual.
    for name in expected:
        if name not in actual:
            diffs.append(f"[MISSING] hook '{name}' có trong baseline nhưng thiếu trong config")
    # Bước 2: phát hiện hook có trong actual nhưng không có trong baseline.
    for name in actual:
        if name not in expected:
            diffs.append(f"[EXTRA] hook '{name}' có trong config nhưng không có trong baseline")
    # Bước 3: nếu cùng tập hợp nhưng thứ tự khác -> liệt kê.
    if set(actual) == set(expected) and actual != expected:
        diffs.append(f"[ORDER] thứ tự khác nhau\n  baseline: {expected}\n  actual:   {actual}")
    return False, diffs


def regen_order_baseline(root: Path) -> int:
    """Generate lại baseline thứ tự hook từ config.json hiện tại.

    Baseline lưu thứ tự hook trích xuất từ config.json. Chỉ chạy khi user gọi
    `--regen` tường minh (không auto-regen).
    """
    try:
        order = extract_hook_order(root)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    if not order:
        print("[ERROR] Không trích xuất được hook nào từ config.json")
        return 1

    from datetime import datetime
    baseline_path = root / ORDER_BASELINE_FILE
    baseline_data = {
        "_description": "U41/T1.5: Hook chain order baseline (pre->plan->schema->coverage->otel->post)",
        "_generated": datetime.now().isoformat(),
        "canonical_order": CANONICAL_ORDER,
        "hook_order": order,
    }
    try:
        baseline_path.write_text(json.dumps(baseline_data, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] Không ghi được baseline: {exc}")
        return 1
    print(f"[OK] Hook order baseline regenerated: {baseline_path}")
    print(f"      order: {order}")
    return 0


def verify_order(root: Path) -> int:
    """Kiểm tra thứ tự chuỗi hook so với baseline.

    Exit 0 nếu thứ tự khớp baseline, exit 1 nếu mismatch hoặc thiếu baseline.
    Không auto-regen — yêu cầu user chạy `--regen` tường minh khi baseline thiếu.
    """
    baseline_path = root / ORDER_BASELINE_FILE
    if not baseline_path.exists():
        print(f"[ERROR] Không có hook order baseline: {baseline_path}")
        print("[HINT] Chạy: python .devin/scripts/hook_integrity.py --regen")
        return 1

    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Lỗi đọc baseline: {exc}")
        return 1
    expected = baseline.get("hook_order", [])
    if not expected:
        print("[ERROR] Baseline rỗng hoặc thiếu trường 'hook_order'. Chạy --regen.")
        return 1

    try:
        actual = extract_hook_order(root)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    match, diffs = compare_order(actual, expected)
    if match:
        print(f"[OK] Hook order verified ({len(actual)} hooks). Thứ tự khớp baseline.")
        print(f"     order: {actual}")
        return 0

    print("[FAIL] Hook order mismatch:")
    for d in diffs:
        print(f"  {d}")
    print(f"\n  baseline: {expected}")
    print(f"  actual:   {actual}")
    print("[HINT] Nếu thay đổi là cố ý, chạy --regen để cập nhật baseline.")
    return 1


def main():
    import argparse
    from datetime import datetime

    ap = argparse.ArgumentParser(description="U41: Hook integrity verification (hash + order)")
    ap.add_argument("--generate", action="store_true", help="Generate SHA256 baseline")
    ap.add_argument("--verify", action="store_true", help="Verify against SHA256 baseline")
    ap.add_argument("--status", action="store_true", help="Show status")
    ap.add_argument("--regen", action="store_true", help="Regenerate hook order baseline (explicit)")
    ap.add_argument("--verify-order", action="store_true", help="Verify hook chain order against baseline")
    ap.add_argument("--root", default=".", help="Repo root")

    args = ap.parse_args()
    root = Path(args.root).resolve()

    if args.generate:
        return generate_baseline(root)
    elif args.verify:
        return verify_integrity(root)
    elif args.status:
        return show_status(root)
    elif args.regen:
        return regen_order_baseline(root)
    elif args.verify_order:
        return verify_order(root)
    else:
        ap.print_help()
        return 1


if __name__ == "__main__":
    # Bước đảm bảo stdout/stderr dùng UTF-8 (tránh UnicodeEncodeError trên Windows cp1258).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
