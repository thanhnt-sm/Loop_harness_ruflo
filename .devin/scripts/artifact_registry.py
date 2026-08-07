#!/usr/bin/env python3
"""artifact_registry.py — Artifact Registry (T4.11, REQ-020).

Mục đích: đăng ký và truy xuất artifact theo (type, id) với schema validation
và race-safe (file-lock chống concurrent write corruption).

Hàm chính:
  - register(type, id, schema) -> None  : đăng ký artifact mới.
  - get(type, id) -> Artifact            : truy xuất artifact đã đăng ký.

Quy tắc:
  - Mỗi (type, id) là duy nhất; register trùng -> raise hoặc update tùy flag.
  - Concurrent write cùng region -> lock/queue, không corrupt JSON.
  - File < 500 dòng, typed interface (Pydantic).

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


# --- Vị trí lưu artifact registry ---
_REGISTRY_DIR = "artifact_registry"

# --- Allowlist type/id ---
_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


# --- Artifact schema ---
class Artifact(BaseModel):
    """Một artifact đã đăng ký trong registry."""
    type: str = Field(max_length=64)
    id: str = Field(max_length=64)
    schema_def: dict[str, Any] = Field(default_factory=dict, alias="schema")
    registered_at: float = Field(ge=0.0)
    version: int = Field(ge=1, le=1000000)

    model_config = {"populate_by_name": True}

    @field_validator("schema_def")
    @classmethod
    def _check_schema(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        if len(v) > 64:
            raise ValueError("schema dict vượt quá 64 keys")
        return v


def _repo_root() -> Path:
    """Trả về repo root, ưu tiên ahd_session.get_repo_root()."""
    try:
        import ahd_session
        return ahd_session.get_repo_root()
    except Exception:
        p = Path(__file__).resolve().parent
        for parent in [p, *p.parents]:
            if (parent / ".devin").is_dir():
                return parent
        return p


def _config_root(root: Path) -> Path:
    """Trả về config root (thường là .devin)."""
    try:
        import ahd_session
        return ahd_session.get_config_root(root)
    except Exception:
        return root / ".devin"


def _registry_root(root: Path | None = None) -> Path:
    """Trả về đường dẫn thư mục artifact registry."""
    root = root or _repo_root()
    return _config_root(root) / _REGISTRY_DIR


def _sanitize_id(value: str) -> str:
    """Làm sạch id/type theo allowlist ^[a-zA-Z0-9_-]{1,64}$."""
    if not value:
        return "unnamed"
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    if not cleaned:
        return "unnamed"
    cleaned = cleaned[:64]
    if not _ID_PATTERN.match(cleaned):
        return "unnamed"
    return cleaned


def _artifact_path(type_: str, id_: str, root: Path | None = None) -> Path:
    """Trả về đường dẫn file artifact cho (type, id)."""
    safe_type = _sanitize_id(type_)
    safe_id = _sanitize_id(id_)
    return _registry_root(root) / safe_type / f"{safe_id}.json"


def _lock_path(path: Path) -> Path:
    """Đường dẫn lock cho artifact file."""
    return path.with_suffix(".lock")


def _acquire_lock(lock_path: Path, timeout: float = 5.0) -> tuple[Path, Any, bool]:
    """Lấy file-lock liên tiến trình (race-safe).

    Trả về (lock_path, handle, is_sentinel).
    """
    try:
        import ahd_session
        handle = ahd_session._acquire_lock(lock_path, timeout=timeout)
        return (lock_path, handle, False)
    except Exception:
        # Fallback: không có ahd_session -> dùng sentinel đơn giản
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                os.close(fd)
                return (lock_path, lock_path, True)
            except FileExistsError:
                time.sleep(0.05)
        return (lock_path, None, True)


def _release_lock(lock_handle: tuple[Path, Any, bool]) -> None:
    """Giải phóng file-lock.

    Đảm bảo release đúng loại (ahd_session handle hoặc sentinel file).
    """
    if lock_handle is None:
        return
    lock_path, handle, is_sentinel = lock_handle
    if handle is None:
        return
    if is_sentinel:
        try:
            if isinstance(handle, Path) and handle.exists():
                handle.unlink()
        except Exception:
            pass
        return
    try:
        import ahd_session
        ahd_session._release_lock(handle)
        return
    except Exception:
        # Nếu ahd release thất bại, xóa sentinel file nếu nó tồn tại để tránh leak.
        try:
            if lock_path.exists():
                lock_path.unlink()
        except Exception:
            pass


def register(
    type: str,
    id: str,
    schema: dict[str, Any],
    *,
    root: Path | None = None,
    update: bool = False,
) -> None:
    """Đăng ký artifact mới vào registry.

    Nhận vào:
        type   — loại artifact (vd "checkpoint", "cot", "verdict").
        id     — định danh artifact (unique trong type).
        schema — dict schema/metadata của artifact.
        root   — repo root (mặc định tự phát hiện).
        update — nếu True, cho phép ghi đè artifact đã tồn tại;
                 nếu False, raise ValueError khi (type, id) đã có.

    Side-effect: ghi file JSON atomic (lock + tmp + rename).
    Trả về None.
    """
    if not type or not id:
        raise ValueError("type và id phải không rỗng")
    if not isinstance(schema, dict):
        raise TypeError("schema phải là dict")

    path = _artifact_path(type, id, root)
    lock = _lock_path(path)
    lock_result = _acquire_lock(lock)
    if lock_result is None:
        raise TimeoutError(f"Không thể lấy lock cho artifact {type}/{id}")
    _lock_path_val, lock_handle, _is_sentinel = lock_result
    if lock_handle is None:
        raise TimeoutError(f"Không thể lấy lock cho artifact {type}/{id}")

    try:
        # Kiểm tra tồn tại
        if path.exists() and not update:
            raise ValueError(f"Artifact {type}/{id} đã tồn tại — dùng update=True để ghi đè")

        # Xây artifact
        version = 1
        if path.exists() and update:
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
                version = int(old.get("version", 1)) + 1
            except Exception:
                version = 1

        artifact = Artifact(
            type=_sanitize_id(type),
            id=_sanitize_id(id),
            schema_def=schema,
            registered_at=time.time(),
            version=version,
        )

        # Ghi atomic: tmp -> rename
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            artifact.model_dump_json(indent=2, by_alias=True),
            encoding="utf-8",
        )
        tmp.replace(path)
    finally:
        _release_lock((_lock_path_val, lock_handle, _is_sentinel))


def get(type: str, id: str, root: Path | None = None) -> Optional[Artifact]:
    """Truy xuất artifact theo (type, id).

    Nhận vào:
        type — loại artifact.
        id   — định danh artifact.
        root — repo root (mặc định tự phát hiện).

    Trả về Artifact hoặc None nếu không tồn tại.
    """
    if not type or not id:
        return None
    path = _artifact_path(type, id, root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Artifact.model_validate(data)
    except Exception:
        return None


def list_artifacts(type: str | None = None, root: Path | None = None) -> list[str]:
    """Liệt kê artifact id đã đăng ký (tùy chọn lọc theo type)."""
    registry = _registry_root(root)
    if not registry.exists():
        return []
    ids: list[str] = []
    if type:
        safe_type = _sanitize_id(type)
        type_dir = registry / safe_type
        if type_dir.exists():
            for f in type_dir.glob("*.json"):
                ids.append(f"{safe_type}/{f.stem}")
    else:
        for type_dir in registry.iterdir():
            if type_dir.is_dir():
                for f in type_dir.glob("*.json"):
                    ids.append(f"{type_dir.name}/{f.stem}")
    return sorted(ids)


def _cli() -> int:
    """CLI stub:
    - register <type> <id> <schema_json>
    - get <type> <id>
    - list [type]
    """
    if len(sys.argv) < 2:
        print("Usage: artifact_registry.py [register <type> <id> <schema> | get <type> <id> | list [type]]", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    if cmd == "register":
        if len(sys.argv) < 5:
            print("Usage: register <type> <id> <schema_json>", file=sys.stderr)
            return 1
        try:
            schema = json.loads(sys.argv[4])
        except Exception as e:
            print(f"schema JSON không hợp lệ: {e}", file=sys.stderr)
            return 1
        register(sys.argv[2], sys.argv[3], schema)
        print(f"registered: {sys.argv[2]}/{sys.argv[3]}")
        return 0
    if cmd == "get":
        if len(sys.argv) < 4:
            print("Usage: get <type> <id>", file=sys.stderr)
            return 1
        art = get(sys.argv[2], sys.argv[3])
        if art is None:
            print("not found", file=sys.stderr)
            return 1
        print(art.model_dump_json(indent=2))
        return 0
    if cmd == "list":
        type_filter = sys.argv[2] if len(sys.argv) > 2 else None
        for entry in list_artifacts(type_filter):
            print(entry)
        return 0
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
