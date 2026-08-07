#!/usr/bin/env python3
"""Kiểm thử cấu hình .devin/config.json và migrate_config (T1.4)."""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Thêm .devin/scripts vào sys.path để import migrate_config
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import migrate_config  # noqa: E402


def test_config_is_valid_json():
    # config.json phải parse được
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    assert "permissions" in config
    assert "hooks" in config


def test_plan_enforce_registered_for_write_and_edit():
    # Hook plan_enforce chỉ được gắn cho matcher write và edit
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    hooks = config.get("hooks", {}).get("PreToolUse", [])
    matched = {h.get("matcher"): h for h in hooks}
    assert "write" in matched
    assert "edit" in matched
    assert "exec" not in matched or all(
        "plan_enforce" not in (cmd.get("command", "") for cmd in matched["exec"].get("hooks", []))
        for _ in [0]
    )
    for m in ("write", "edit"):
        commands = [cmd.get("command", "") for cmd in matched[m].get("hooks", [])]
        assert any("plan_enforce.py" in c for c in commands)


def test_deny_list_has_destructive_patterns():
    # deny list phải chứa các lệnh nguy hiểm
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    deny = config.get("permissions", {}).get("deny", [])
    patterns = ["rm -rf", "git push --force", "git push -f", "git reset --hard", "git clean -fd"]
    for p in patterns:
        assert any(p in d.lower() for d in deny), f"deny list thiếu pattern: {p}"


def test_core_scripts_allowed():
    # Các script cốt lõi phải nằm trong allow list
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    allow = config.get("permissions", {}).get("allow", [])
    required = [
        "Exec(python .devin/scripts/plan_orchestrator.py:*)",
        "Exec(python .devin/scripts/approval_gate.py:*)",
        "Exec(python .devin/scripts/plan_quality_check.py:*)",
    ]
    for r in required:
        assert r in allow, f"allow list thiếu: {r}"


def test_python_scripts_compile():
    # Kiểm tra tất cả script Python không có lỗi cú pháp
    scripts_dir = REPO_ROOT / ".devin" / "scripts"
    hooks_dir = REPO_ROOT / ".devin" / "hooks"
    for f in list(scripts_dir.glob("*.py")) + list(hooks_dir.glob("*.py")):
        result = subprocess.run([sys.executable, "-m", "py_compile", str(f)], capture_output=True, text=True)
        assert result.returncode == 0, f"Syntax error in {f}: {result.stderr}"


# ---------------------------------------------------------------------------
# T1.4: Tests cho migrate_config.py
# ---------------------------------------------------------------------------

def _make_temp_config(tmp_path: Path, payload: dict) -> Path:
    """Tạo file config tạm trong tmp_path/.devin/config.json và trả về đường dẫn."""
    devin_dir = tmp_path / ".devin"
    devin_dir.mkdir(parents=True, exist_ok=True)
    cfg = devin_dir / "config.json"
    cfg.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return cfg


def test_migrate_imports():
    # import migrate_config phải thành công và có hàm migrate
    assert hasattr(migrate_config, "migrate")
    assert callable(migrate_config.migrate)


def test_migrate_replaces_absolute_paths(tmp_path, monkeypatch):
    # Cấu hình chứa đường dẫn tuyệt đối Windows + POSIX phải được thay bằng placeholder
    repo_root = tmp_path
    fake_home = tmp_path / "home" / "user"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    payload = {
        "hooks": {
            "PreToolUse": [
                {"command": f"{repo_root.as_posix()}/HLK/wrappers/hook.mjs", "timeout": 3},
                {"command": f"{fake_home.as_posix()}/.cache/script.sh", "timeout": 5},
            ]
        },
        "other": "giá-trị-bình-thường",
    }
    cfg = _make_temp_config(tmp_path, payload)

    migrated_path = migrate_config.migrate(cfg)
    assert migrated_path == cfg.resolve()

    data = json.loads(cfg.read_text(encoding="utf-8"))
    commands = [h["command"] for h in data["hooks"]["PreToolUse"]]
    # Đường dẫn tuyệt đối phải bị thay bằng placeholder
    assert any("${REPO_ROOT}" in c for c in commands), f"REPO_ROOT không được thay: {commands}"
    assert any("${USER_HOME}" in c for c in commands), f"USER_HOME không được thay: {commands}"
    # Key khác phải giữ nguyên
    assert data["other"] == "giá-trị-bình-thường"


def test_migrate_creates_env_template(tmp_path, monkeypatch):
    # Sau khi migrate phải tồn tại file .env.template tại repo_root
    fake_home = tmp_path / "home" / "user"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    payload = {"path": f"{fake_home.as_posix()}/data"}
    cfg = _make_temp_config(tmp_path, payload)

    migrate_config.migrate(cfg)
    env_template = tmp_path / ".env.template"
    assert env_template.exists(), ".env.template chưa được tạo"
    content = env_template.read_text(encoding="utf-8")
    # Phải có dòng USER_HOME được comment out
    assert any("USER_HOME=" in line and line.strip().startswith("#") for line in content.splitlines()), (
        f".env.template thiếu dòng USER_HOME comment: {content}"
    )


def test_migrate_idempotent(tmp_path, monkeypatch):
    # Chạy migrate lần 2 trên file đã migrate phải là no-op (nội dung không đổi)
    fake_home = tmp_path / "home" / "user"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    payload = {"path": f"{fake_home.as_posix()}/data", "keep": 1}
    cfg = _make_temp_config(tmp_path, payload)

    migrate_config.migrate(cfg)
    after_first = cfg.read_text(encoding="utf-8")

    # Chạy lại — phải no-op
    migrate_config.migrate(cfg)
    after_second = cfg.read_text(encoding="utf-8")
    assert after_first == after_second, "Migrate không idempotent — nội dung thay đổi ở lần 2"


def test_migrate_skips_already_placeholder(tmp_path, monkeypatch):
    # Giá trị đã là ${VAR} thuần phải được giữ nguyên (không thay đổi)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    payload = {"path": "${REPO_ROOT}/HLK/hook.mjs", "other": "plain"}
    cfg = _make_temp_config(tmp_path, payload)
    original = cfg.read_text(encoding="utf-8")

    migrate_config.migrate(cfg)
    after = cfg.read_text(encoding="utf-8")
    assert original == after, "Placeholder thuần bị thay đổi dù đã migrate"


def test_migrate_preserves_non_path_strings(tmp_path, monkeypatch):
    # Chuỗi không chứa đường dẫn tuyệt đối phải giữ nguyên
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    payload = {"cmd": "python script.py", "num": 42, "flag": True, "nested": {"a": ["x", "y"]}}
    cfg = _make_temp_config(tmp_path, payload)
    original = cfg.read_text(encoding="utf-8")

    migrate_config.migrate(cfg)
    after = cfg.read_text(encoding="utf-8")
    assert json.loads(after) == json.loads(original), "Config không-path bị thay đổi"


def test_migrate_missing_file_raises(tmp_path):
    # File không tồn tại phải raise FileNotFoundError
    import pytest
    with pytest.raises(FileNotFoundError):
        migrate_config.migrate(tmp_path / "nonexistent.json")


def test_migrate_malformed_json_raises(tmp_path):
    # JSON malformed phải raise json.JSONDecodeError
    import pytest
    devin_dir = tmp_path / ".devin"
    devin_dir.mkdir(parents=True, exist_ok=True)
    cfg = devin_dir / "config.json"
    cfg.write_text("{ không hợp lệ }", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        migrate_config.migrate(cfg)


def test_migrate_returns_absolute_path(tmp_path, monkeypatch):
    # migrate phải trả về đường dẫn absolute
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    cfg = _make_temp_config(tmp_path, {"a": "b"})
    result = migrate_config.migrate(cfg)
    assert result.is_absolute(), f"Kết quả không phải absolute path: {result}"
