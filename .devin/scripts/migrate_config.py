#!/usr/bin/env python3
"""T1.4: Migration script cho .devin/config.json.

Mục đích:
- Đọc file config (mặc định `.devin/config.json`).
- Thay thế các đường dẫn tuyệt đối hardcoded (Windows `D:\\...` hoặc Linux `/home/...`)
  bằng biến placeholder dạng `${REPO_ROOT}`, `${USER_HOME}`, ...
- Giữ nguyên các key config khác.
- Ghi config đã migrate ngược lại file gốc.
- Tạo file `.env.template` chứa các biến placeholder (mỗi dòng `VAR=value`,
  được comment out bằng `#` để người dùng tự điền giá trị thật).
- Idempotent: chạy lại trên file đã migrate là no-op (phát hiện qua việc giá trị
  bắt đầu bằng `${` và kết thúc bằng `}`, hoặc không còn đường dẫn tuyệt đối).

Usage:
    python .devin/scripts/migrate_config.py --config .devin/config.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Hằng số mặc định
DEFAULT_CONFIG_PATH = Path(".devin/config.json")
ENV_TEMPLATE_NAME = ".env.template"

# Regex phát hiện đường dẫn tuyệt đối:
# - Windows: ký tự ổ đĩa `C:\...` hoặc `C:/...` (ví dụ `D:\foo\bar`)
# - Linux/POSIX: `/home/...`, `/Users/...`, `/var/...`, `/opt/...`, `/tmp/...`
# POSIX dùng negative lookbehind `(?<![A-Za-z}:])` để không khớp `/Users` bên trong
# đường dẫn Windows `C:/Users/...` hoặc sau placeholder `${DRIVE_X}`.
_WIN_PATH_RE = re.compile(r"([A-Za-z]:)([\\/][^\"'\s,]*)")
_POSIX_PATH_RE = re.compile(
    r"(?<![A-Za-z}:])/(?:home|Users|var|opt|tmp|root|mnt|etc|usr|srv|data|workspace)(?:[/\w.\-]+)*"
)


def _is_placeholder(value: str) -> bool:
    """Trả về True nếu giá trị đã là placeholder dạng `${VAR}`.

    Phát hiện: bắt đầu bằng `${` và kết thúc bằng `}`.
    """
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return stripped.startswith("${") and stripped.endswith("}")


def _has_absolute_path(value: str) -> bool:
    """Trả về True nếu chuỗi chứa đường dẫn tuyệt đối Windows hoặc POSIX."""
    if not isinstance(value, str):
        return False
    return bool(_WIN_PATH_RE.search(value) or _POSIX_PATH_RE.search(value))


def _detect_repo_root(config_path: Path) -> Path:
    """Suy luận REPO_ROOT từ vị trí file config.

    Quy ước: config nằm tại `<repo_root>/.devin/config.json` → repo_root là cha của `.devin`.
    """
    # config_path có thể là relative hoặc absolute; chuẩn hoá về absolute
    abs_path = config_path.resolve()
    # Nếu nằm trong `.devin/` thì repo_root = parent của `.devin`
    try:
        rel = abs_path.relative_to(Path.cwd())
    except ValueError:
        rel = abs_path
    parts = rel.parts
    if ".devin" in parts:
        idx = parts.index(".devin")
        # repo_root là các phần trước `.devin`
        root_parts = parts[:idx]
        if root_parts:
            return Path(*root_parts).resolve()
        return Path.cwd()
    # Fallback: cha của file config
    return abs_path.parent.parent


def _build_placeholder_map(repo_root: Path) -> dict[str, str]:
    """Xây dựng bảng ánh xạ đường dẫn tuyệt đối → biến placeholder.

    Thứ tự ưu tiên: REPO_ROOT trước (để khớp đường dẫn dài nhất), rồi USER_HOME.
    """
    home = Path.home()
    return {
        "REPO_ROOT": str(repo_root),
        "USER_HOME": str(home),
    }


def _replace_paths_in_string(value: str, placeholders: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Thay thế đường dẫn tuyệt đối trong chuỗi bằng `${VAR}`.

    Trả về (chuỗi đã thay thế, dict biến đã dùng {VAR: giá trị gốc}).
    """
    used: dict[str, str] = {}
    result = value

    # Bước 1: Thay REPO_ROOT, USER_HOME trước (khớp đường dẫn dài nhất trước).
    # Chuẩn hoá separator: biến cả `/` và `\` thành `[/\\]` trong pattern để
    # khớp bất kể hệ điều hành (config có thể dùng `/` dù OS dùng `\`).
    sorted_vars = sorted(placeholders.items(), key=lambda kv: len(kv[1]), reverse=True)
    for var_name, var_value in sorted_vars:
        if not var_value:
            continue
        norm = var_value.replace("\\", "/")
        pattern = re.escape(norm).replace(re.escape("/"), r"[\\\\/]")
        used_flag = {"hit": False}

        def _make_replacement(match: re.Match, vn: str = var_name, vv: str = var_value, uf=used_flag) -> str:
            uf["hit"] = True
            used[vn] = vv
            return "${" + vn + "}"

        new_result = re.sub(pattern, _make_replacement, result)
        result = new_result

    # Bước 2: Thay đường dẫn Windows còn sót — thay cả cụm `X:/rest` hoặc `X:\rest`
    # bằng `${DRIVE_X}` + rest (giữ rest nguyên vẹn, không để POSIX regex bắt nốt).
    def _win_replace(match: re.Match) -> str:
        # Lấy ký tự ổ đĩa (không lấy dấu :) và phần còn lại sau dấu hai chấm
        drive_letter = match.group(1)[0].upper()
        var = f"DRIVE_{drive_letter}"
        used.setdefault(var, f"{drive_letter}:\\")
        return "${" + var + "}" + match.group(2)

    # Chỉ khớp đường dẫn Windows khi có ký tự phân cách \ hoặc / sau ổ đĩa,
    # tránh ăn nhầm pattern dạng `git diff:*` hay `npm test:*`.
    result = re.sub(r"([A-Za-z]:)([\\/][^\"'\s,]*)", _win_replace, result)

    # Bước 3: Thay POSIX path còn sót (đã có lookbehind tránh khớp sau `}` hoặc `X:`)
    def _posix_replace(match: re.Match) -> str:
        used.setdefault("ABS_PATH", "/")
        return "${ABS_PATH}" + match.group(0)[1:]

    result = _POSIX_PATH_RE.sub(_posix_replace, result)

    return result, used


def _walk_and_replace(obj: Any, placeholders: dict[str, str]) -> tuple[Any, dict[str, str]]:
    """Đệ quy duyệt cấu trúc JSON, thay thế đường dẫn tuyệt đối trong mọi chuỗi.

    Trả về (cấu trúc đã thay thế, dict biến đã dùng).
    """
    used: dict[str, str] = {}
    if isinstance(obj, dict):
        new_obj: dict[str, Any] = {}
        for k, v in obj.items():
            new_v, v_used = _walk_and_replace(v, placeholders)
            new_obj[k] = new_v
            used.update(v_used)
        return new_obj, used
    if isinstance(obj, list):
        new_list: list[Any] = []
        for item in obj:
            new_item, item_used = _walk_and_replace(item, placeholders)
            new_list.append(new_item)
            used.update(item_used)
        return new_list, used
    if isinstance(obj, str):
        # Bỏ qua nếu đã là placeholder thuần hoặc không có đường dẫn tuyệt đối
        if _is_placeholder(obj) or not _has_absolute_path(obj):
            return obj, used
        replaced, str_used = _replace_paths_in_string(obj, placeholders)
        used.update(str_used)
        return replaced, used
    # Kiểu khác (int, bool, None) giữ nguyên
    return obj, used


def _is_already_migrated(obj: Any) -> bool:
    """Kiểm tra đệ quy xem cấu trúc JSON đã được migrate chưa.

    Đã migrate nếu: KHÔNG còn bất kỳ chuỗi nào chứa đường dẫn tuyệt đối.
    (Placeholder `${...}` không chứa đường dẫn tuyệt đối.)
    """
    if isinstance(obj, dict):
        return all(_is_already_migrated(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_is_already_migrated(item) for item in obj)
    if isinstance(obj, str):
        return not _has_absolute_path(obj)
    return True


def _write_env_template(template_path: Path, used_vars: dict[str, str]) -> None:
    """Ghi file `.env.template` với mỗi biến một dòng, comment out.

    Format: `# VAR=giá_trị_gốc` (để người dùng tự bỏ comment và điền giá trị thật).
    Nếu used_vars rỗng, vẫn ghi file với header giải thích (idempotent).
    """
    lines = [
        "# T1.4: .env.template sinh tự động bởi migrate_config.py",
        "# Mỗi dòng là một biến placeholder dùng trong config đã migrate.",
        "# Bỏ dấu `#` và điền giá trị thật cho môi trường của bạn.",
        "# KHÔNG commit file .env (chỉ .env.template là an toàn).",
        "",
    ]
    for var in sorted(used_vars.keys()):
        value = used_vars[var]
        lines.append(f"# {var}={value}")
    if not used_vars:
        lines.append("# (Không có biến placeholder nào — config không chứa đường dẫn tuyệt đối.)")
    lines.append("")
    template_path.write_text("\n".join(lines), encoding="utf-8")


def migrate(config_path: Path) -> Path:
    """Migrate file config: thay đường dẫn tuyệt đối bằng placeholder.

    Args:
        config_path: Đường dẫn tới file config JSON (mặc định `.devin/config.json`).

    Returns:
        Đường dẫn file config đã migrate (Path absolute).

    Raises:
        FileNotFoundError: file config không tồn tại.
        json.JSONDecodeError: file config không phải JSON hợp lệ.
        OSError: lỗi I/O khi đọc/ghi.
    """
    # Bước 1: Chuẩn hoá đường dẫn và kiểm tra tồn tại
    config_path = config_path.resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"File config không tồn tại: {config_path}")
    if not config_path.is_file():
        raise FileNotFoundError(f"Đường dẫn không phải file: {config_path}")

    # Bước 2: Đọc và parse JSON (báo lỗi rõ ràng nếu malformed)
    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Không đọc được file config {config_path}: {exc}") from exc
    try:
        config = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"File config {config_path} không phải JSON hợp lệ: {exc.msg} (dòng {exc.lineno}, cột {exc.colno})",
            exc.doc,
            exc.pos,
        ) from exc

    # Bước 3: Kiểm tra idempotent — nếu đã migrate (không còn đường dẫn tuyệt đối) thì no-op
    if _is_already_migrated(config):
        # Vẫn đảm bảo .env.template tồn tại (idempotent: ghi lại template rỗng/cũ)
        env_template = config_path.parent.parent / ENV_TEMPLATE_NAME
        # Nếu template đã có thì giữ nguyên, không ghi đè để tránh mất tuỳ chỉnh người dùng
        if not env_template.exists():
            _write_env_template(env_template, {})
        return config_path

    # Bước 4: Xây dựng placeholder map và thay thế
    repo_root = _detect_repo_root(config_path)
    placeholders = _build_placeholder_map(repo_root)
    migrated_config, used_vars = _walk_and_replace(config, placeholders)

    # Bước 5: Ghi config đã migrate ngược lại file gốc (atomic: ghi .tmp rồi rename)
    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    try:
        tmp_path.write_text(
            json.dumps(migrated_config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(config_path)
    except OSError as exc:
        # Dọn tmp file nếu lỗi
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise OSError(f"Không ghi được file config đã migrate {config_path}: {exc}") from exc

    # Bước 6: Ghi .env.template tại repo_root (cha của .devin/)
    env_template = config_path.parent.parent / ENV_TEMPLATE_NAME
    _write_env_template(env_template, used_vars)

    return config_path


def _main(argv: list[str] | None = None) -> int:
    """CLI stub: chấp nhận `--config <path>`, in ra đường dẫn config đã migrate."""
    # Đảm bảo stdout dùng UTF-8 để in tiếng Việt an toàn trên Windows console
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        # Python cũ hoặc stream không hỗ trợ reconfigure — bỏ qua
        pass

    parser = argparse.ArgumentParser(
        description="Migrate .devin/config.json: replace absolute paths with ${VAR} placeholders."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args(argv)

    try:
        migrated_path = migrate(args.config)
        print(f"[OK] Config đã migrate: {migrated_path}")
        env_template = migrated_path.parent.parent / ENV_TEMPLATE_NAME
        print(f"[OK] .env.template: {env_template}")
        return 0
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[ERROR] JSON không hợp lệ: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"[ERROR] Lỗi I/O: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(_main())
