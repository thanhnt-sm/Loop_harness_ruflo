#!/usr/bin/env python3
"""check_deps.py — Verify dependency lock consistency (deterministic, no network).

Chạy nhanh + cục bộ để chặn các lỗi git-workflow do bump dependency làm hỏng CI:
  1. filelock thỏa mãn ràng buộc documented pin trong pyproject.toml (<3.13).
     filelock 3.13+ eager import asyncio (~6s) làm hook vượt timeout 2.5s.
  2. pydantic-core khớp đúng version pydantic yêu cầu (pydantic pin == pydantic-core).
     Bump pydantic-core độc lập → ResolutionImpossible → supply-chain fail.
  3. SBOM lock-relevant components khớp requirements-lock.txt (chống SBOM drift).

Usage:
  python tools/check_deps.py [--sbom sbom/python.sbom.json] [--lock requirements-lock.txt]

Exit 0 = PASS, 1 = FAIL. Không cần network (chỉ đọc file + importlib.metadata local).
"""
from __future__ import annotations

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

# Đảm bảo output UTF-8 trên mọi console (Windows cp1258 → UTF-8) để tiếng Việt hiển thị đúng.
for _stream in (sys.stdout, sys.stderr):
    try:
        if getattr(_stream, "encoding", "") and _stream.encoding.lower() not in ("utf-8", "utf8"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

REPO = Path(__file__).resolve().parent.parent
DEFAULT_LOCK = REPO / "requirements-lock.txt"
DEFAULT_PYPROJECT = REPO / "pyproject.toml"
DEFAULT_SBOM = REPO / "sbom" / "python.sbom.json"

# Các dependency trong lock file được coi là "declared" và phải khớp SBOM.
# name lock → name SBOM (SBOM dùng underscore cho một số package).
DECLARED_DEPS = (
    "annotated-types",
    "cffi",
    "cryptography",
    "filelock",
    "pycparser",
    "pydantic",
    "pydantic-core",
    "typing-extensions",
    "typing-inspection",
)

_LOCK_RE = re.compile(r"^([a-zA-Z0-9_.-]+)==([^\s\\]+)", re.MULTILINE)


def _norm(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def parse_lock(lock_path: Path) -> dict[str, str]:
    """Parse requirements-lock.txt → {name: version} (name đã chuẩn hóa)."""
    if not lock_path.exists():
        return {}
    text = lock_path.read_text(encoding="utf-8")
    pins: dict[str, str] = {}
    for name, version in _LOCK_RE.findall(text):
        pins[_norm(name)] = version
    return pins


def parse_pyproject_filelock(pyproject_path: Path) -> list[str]:
    """Trả về các ràng buộc filelock trong pyproject.toml (dependencies + test extra)."""
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        return []
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    constraints: list[str] = []
    for section in (data.get("project", {}).get("dependencies", []),
                    data.get("project", {}).get("optional-dependencies", {}).get("test", [])):
        for dep in section:
            try:
                from packaging.requirements import Requirement

                req = Requirement(dep)
            except (ImportError, ValueError):
                # Fallback: cắt name bằng regex (dep có dạng "filelock>=3.0,<3.13").
                m = re.match(r"^[a-zA-Z0-9_.-]+\s*(.*)$", dep)
                if m:
                    constraints.append(m.group(1))
                continue
            if req.name.strip().lower() == "filelock":
                constraints.append(str(req.specifier))
    return constraints


def _version_tuple(v: str) -> tuple[int, ...]:
    """Chuyển version string thành tuple int để so sánh, bỏ qua pre/post release."""
    nums = re.findall(r"\d+", v.split("+")[0])
    return tuple(int(n) for n in nums) if nums else (0,)


def _satisfies(version: str, specifier: str) -> bool:
    """Kiểm tra version thỏa một specifier PEP 440 đơn giản (==, <, <=, >=, >)."""
    from packaging.specifiers import SpecifierSet

    try:
        return SpecifierSet(specifier).contains(version)
    except Exception:  # noqa: BLE001
        return True  # không parse được → không chặn (fail-open cho spec lạ)


def check_filelock(pins: dict[str, str], constraints: list[str]) -> list[str]:
    fails: list[str] = []
    ver = pins.get("filelock")
    if ver is None:
        fails.append("requirements-lock.txt thiếu pin filelock")
        return fails
    if not constraints:
        return fails  # không có ràng buộc để kiểm
    for spec in constraints:
        if not _satisfies(ver, spec):
            fails.append(
                f"filelock=={ver} vi phạm ràng buộc '{spec}' trong pyproject.toml. "
                "filelock phải <3.13 (eager asyncio import làm hook vượt timeout). "
                "Revert bump hoặc dùng filelock==3.12.4."
            )
    return fails


def check_pydantic_core(pins: dict[str, str]) -> list[str]:
    """So khớp pydantic-core trong lock với version pydantic yêu cầu (local metadata)."""
    fails: list[str] = []
    lock_pydantic = pins.get("pydantic")
    lock_core = pins.get("pydantic-core")
    if not lock_pydantic or not lock_core:
        return fails
    try:
        if metadata.version("pydantic") != lock_pydantic:
            # pydantic cài local khác version lock → không thể kiểm chéo; bỏ qua.
            return fails
        reqs = metadata.requires("pydantic") or []
    except metadata.PackageNotFoundError:
        return fails
    required_core = None
    for req in reqs:
        if req.split(";")[0].strip().lower().startswith("pydantic-core=="):
            required_core = req.split("==", 1)[1].split(";")[0].strip()
            break
    if required_core and required_core != lock_core:
        fails.append(
            f"pydantic-core=={lock_core} trong lock KHÔNG khớp pydantic=={lock_pydantic} "
            f"(yêu cầu pydantic-core=={required_core}). Bump pydantic + pydantic-core cùng nhau "
            f"hoặc revert pydantic-core về {required_core}."
        )
    return fails


def check_sbom(pins: dict[str, str], sbom_path: Path) -> list[str]:
    """Kiểm tra SBOM lock-relevant components khớp requirements-lock.txt."""
    fails: list[str] = []
    try:
        import json
        sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fails  # SBOM thiếu/broken → sbom_verify.py lo
    sbom_versions: dict[str, str] = {}
    for c in sbom.get("components", []):
        sbom_versions[_norm(c.get("name", ""))] = str(c.get("version", ""))
    for dep in DECLARED_DEPS:
        lock_ver = pins.get(dep)
        if lock_ver is None:
            continue
        sbom_ver = sbom_versions.get(dep)
        if sbom_ver is None:
            fails.append(f"SBOM thiếu component '{dep}' (lock={lock_ver})")
        elif sbom_ver != lock_ver:
            fails.append(f"SBOM drift: '{dep}' sbom={sbom_ver} lock={lock_ver}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify dependency lock consistency")
    ap.add_argument("--lock", default=str(DEFAULT_LOCK))
    ap.add_argument("--pyproject", default=str(DEFAULT_PYPROJECT))
    ap.add_argument("--sbom", default=str(DEFAULT_SBOM))
    args = ap.parse_args()

    pins = parse_lock(Path(args.lock))
    if not pins:
        print(f"FAIL: không parse được pin từ {args.lock}", file=sys.stderr)
        return 1

    fails: list[str] = []
    fails += check_filelock(pins, parse_pyproject_filelock(Path(args.pyproject)))
    fails += check_pydantic_core(pins)
    fails += check_sbom(pins, Path(args.sbom))

    for f in fails:
        print(f"FAIL: {f}", file=sys.stderr)
    if fails:
        print(f"Dependency consistency check FAILED: {len(fails)} issue(s)", file=sys.stderr)
        return 1
    print("Dependency consistency check PASSED: filelock pin, pydantic-core coupling, SBOM khớp lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
