#!/usr/bin/env python3
"""Migration script chuyển các đường dẫn hardcoded trong config thành placeholder dạng `${VAR}`.

Hỗ trợ tự động phát hiện `REPO_ROOT` và `USER_HOME`, tạo `.env.template`, và đảm bảo
idempotent: nếu file đã chứa `${...}` thì không thay đổi.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _is_placeholder(value: Any) -> bool:
    """Kiểm tra xem chuỗi có phải là placeholder dạng `${VAR}` hay không."""
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", value))


def _has_absolute_path(value: str) -> bool:
    """Phát hiện chuỗi chứa đường dẫn tuyệt đối theo kiểu Windows hoặc POSIX."""
    return bool(re.search(r"(?:^|[^A-Za-z0-9_])([A-Za-z]:[\\/]|[\\/])", value))


def _looks_like_path(s: str) -> bool:
    """Heuristic nhận diện chuỗi là đường dẫn tuyệt đối (dùng để xoay mapping)."""
    return bool(re.match(r"^(?:[A-Za-z]:[\\/]|[\\/])", s))


def _detect_repo_root(config_path: str | Path) -> Path:
    """Từ đường dẫn config, tìm thư mục gốc của repo.

    Nếu config nằm trong thư mục `.devin`, repo root là thư mục cha của `.devin`.
    Ngược lại repo root là thư mục chứa file config (hoặc chính đường dẫn nếu là thư mục).
    """
    p = Path(config_path).resolve()
    if p.is_file() or (not p.exists() and p.name == "config.json"):
        start = p.parent
    else:
        start = p

    if start.name == ".devin":
        return start.parent

    return start


def _build_placeholder_map(repo_root: str | Path) -> dict[str, str]:
    """Tạo map placeholder mặc định dạng var -> đường dẫn tuyệt đối POSIX."""
    root = Path(repo_root).resolve()
    home = Path.home()
    return {
        "REPO_ROOT": root.as_posix(),
        "USER_HOME": home.as_posix(),
    }


def _normalize_placeholders(mapping: dict[str, str]) -> dict[str, str]:
    """Chuẩn hóa mapping về dạng var -> path, hỗ trợ cả path->var và var->path."""
    placeholders: dict[str, str] = {}
    for key, value in mapping.items():
        k = str(key)
        v = str(value)
        if _looks_like_path(k) and not _looks_like_path(v):
            # k là path, v là tên biến
            placeholders[v] = k
        elif _looks_like_path(v):
            # v là path, k là tên biến
            placeholders[k] = v
        else:
            # fallback: giữ nguyên key là tên biến
            placeholders[k] = v
    return placeholders


def _replace_paths_in_string(value: str, placeholders: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Thay thế các đường dẫn đã biết trong một chuỗi bằng `${VAR}`.

    Trả về chuỗi mới và dict các placeholder đã dùng (var -> path gốc).
    """
    if not placeholders or not _has_absolute_path(value):
        return value, {}
    if _is_placeholder(value):
        return value, {}

    used: dict[str, str] = {}
    # Sắp xếp theo độ dài path giảm dần để thay path dài/nested trước
    items = sorted(placeholders.items(), key=lambda item: -len(item[1]))
    for var, path in items:
        placeholder = f"${{{var}}}"
        if path in value and placeholder not in value:
            value = value.replace(path, placeholder)
            used[var] = path
    return value, used


def _walk_and_replace(data: Any, placeholders: dict[str, str]) -> tuple[Any, dict[str, str]]:
    """Đệ quy duyệt dict/list và thay thế đường dẫn trong các chuỗi."""
    used: dict[str, str] = {}
    if isinstance(data, dict):
        new_data: dict[str, Any] = {}
        for key, val in data.items():
            new_val, u = _walk_and_replace(val, placeholders)
            new_data[key] = new_val
            used.update(u)
        return new_data, used
    if isinstance(data, list):
        new_data: list[Any] = []
        for val in data:
            new_val, u = _walk_and_replace(val, placeholders)
            new_data.append(new_val)
            used.update(u)
        return new_data, used
    if isinstance(data, str):
        return _replace_paths_in_string(data, placeholders)
    return data, used


def _is_already_migrated(data: Any) -> bool:
    """Kiểm tra xem config đã chứa placeholder `${VAR}` hay chưa (idempotency)."""
    text = json.dumps(data, ensure_ascii=False)
    return bool(re.search(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", text))


def _write_env_template(
    path: str | Path,
    placeholders: dict[str, str],
    commented_vars: set[str] | None = None,
) -> None:
    """Ghi file `.env.template` từ dict placeholder (var -> path).

    Các biến trong `commented_vars` sẽ được ghi dưới dạng comment.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if commented_vars is None:
        commented_vars = {"USER_HOME"}
    lines: list[str] = []
    for var, pth in sorted(placeholders.items()):
        if var in commented_vars:
            lines.append(f"#{var}={pth}")
        else:
            lines.append(f"{var}={pth}")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def migrate(
    config_path: str | Path,
    mapping: dict[str, str] | None = None,
    env_template_name: str = ".env.template",
) -> Path:
    """Đọc file config JSON, thay thế đường dẫn hardcoded bằng placeholder.

    Tự động phát hiện `REPO_ROOT` và `USER_HOME` nếu không cung cấp mapping.
    Ghi file `.env.template` tại repo root. Nếu config đã chứa placeholder thì không thay đổi.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        original = f.read()
    data = json.loads(original)

    if _is_already_migrated(data):
        return config_path.resolve()

    repo_root = _detect_repo_root(config_path)
    if mapping is None:
        placeholders = _build_placeholder_map(repo_root)
        commented_vars: set[str] = {"USER_HOME"}
    else:
        placeholders = _normalize_placeholders(mapping)
        commented_vars = set()

    new_data, _ = _walk_and_replace(data, placeholders)

    # Tạo backup trước khi ghi đè
    backup_path = config_path.parent / (config_path.name + ".bak")
    if not backup_path.exists():
        backup_path.write_text(original, encoding="utf-8")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)

    env_path = repo_root / env_template_name
    _write_env_template(env_path, placeholders, commented_vars)

    return config_path.resolve()


def _main(argv: list[str] | None = None) -> int:
    """CLI handler, hỗ trợ cả positional `config` và `--config <path>`.

    Mã lỗi:
      0: thành công
      1: file không tồn tại hoặc lỗi chung
      2: JSON không hợp lệ
      3: lỗi hệ thống (OSError)
    """
    parser = argparse.ArgumentParser(description="Migrate config JSON placeholders")
    parser.add_argument("config_pos", nargs="?", help="Đường dẫn file config JSON")
    parser.add_argument("--config", dest="config_opt", default=None, help="Đường dẫn file config JSON")
    args = parser.parse_args(argv)

    config = args.config_opt or args.config_pos
    if not config:
        parser.print_usage(sys.stderr)
        return 1

    try:
        migrate(config)
    except FileNotFoundError:
        return 1
    except json.JSONDecodeError:
        return 2
    except OSError:
        return 3
    except Exception:
        return 1
    return 0


def main() -> int:
    """Entry point cho subprocess / __main__ block."""
    return _main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
