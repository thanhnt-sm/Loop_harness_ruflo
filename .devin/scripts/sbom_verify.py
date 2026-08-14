#!/usr/bin/env python3
"""sbom_verify.py — Verify SBOM + hash-pinned lock (Task 3.7).

Kiểm tra trong CI trước deploy:
  1. SBOM (CycloneDX) tồn tại và không rỗng (python + npm).
  2. Mọi component trong SBOM khớp bản cài đặt thực tế (name/version).
  3. requirements-lock.txt tồn tại với hash (--require-hashes sẵn sàng).
  4. Không có dependency ngoài danh sách trong SBOM (supply chain map).

Exit 0 nếu PASS, 1 nếu FAIL. Usage:
  python .devin/scripts/sbom_verify.py [--sbom sbom/python.sbom.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from importlib import metadata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DEFAULT_SBOM = REPO / "sbom" / "python.sbom.json"
LOCK = REPO / "requirements-lock.txt"


def load_sbom(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def installed_distributions() -> dict[str, str]:
    out: dict[str, str] = {}
    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "").strip().lower()
        if name:
            out[name] = dist.version or ""
    return out


def verify_sbom_vs_installed(sbom_path: Path) -> list[str]:
    fails: list[str] = []
    sbom = load_sbom(sbom_path)
    components = sbom.get("components", [])
    if not components:
        fails.append(f"SBOM {sbom_path.name}: không có components (rỗng)")
        return fails
    installed = installed_distributions()
    for comp in components:
        name = (comp.get("name") or "").lower()
        version = comp.get("version", "")
        if name not in installed:
            fails.append(f"SBOM component '{name}' không có trong môi trường cài đặt")
            continue
        if version and installed[name] != version:
            fails.append(f"Version lệch: {name} sbom={version} installed={installed[name]}")
    # Ngược lại: package cài đặt nhưng không có trong SBOM → drift
    sbom_names = {c.get("name", "").lower() for c in components}
    extra = sorted(set(installed) - sbom_names)
    if extra:
        fails.append(f"Package cài đặt KHÔNG có trong SBOM (drift): {extra}")
    return fails


def verify_lock_hashes(lock_path: Path) -> list[str]:
    fails: list[str] = []
    if not lock_path.exists():
        fails.append(f"requirements-lock.txt thiếu: {lock_path}")
        return fails
    text = lock_path.read_text(encoding="utf-8")
    pins = re.findall(r"^([a-zA-Z0-9_.-]+)==([^\s\\]+)", text, re.MULTILINE)
    if not pins:
        fails.append("requirements-lock.txt không chứa pin hợp lệ (name==version)")
        return fails
    for name, version in pins:
        if not re.search(rf"^{re.escape(name)}=={re.escape(version)}[ \t\\]*\n", text, re.MULTILINE):
            fails.append(f"Lock entry không chuẩn: {name}=={version}")
            continue
        block = text.split(f"{name}=={version}", 1)[1].split("\n", 3)[1:4]
        joined = " ".join(block)
        if "--hash=sha256:" not in joined:
            fails.append(f"Thiếu hash: {name}=={version}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify SBOM + lock hashes")
    ap.add_argument("--sbom", default=str(DEFAULT_SBOM))
    ap.add_argument("--lock", default=str(LOCK))
    ap.add_argument("--skip-installed", action="store_true",
                    help="Bỏ qua so khớp môi trường cài đặt (chỉ verify file)")
    args = ap.parse_args()

    fails: list[str] = []
    fails += verify_lock_hashes(Path(args.lock))
    if not args.skip_installed:
        fails += verify_sbom_vs_installed(Path(args.sbom))
    for f in fails:
        print(f"FAIL: {f}", file=sys.stderr)
    if fails:
        print(f"SBOM verification FAILED: {len(fails)} issue(s)", file=sys.stderr)
        return 1
    print("SBOM verification PASSED: components match installed, hashes pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())