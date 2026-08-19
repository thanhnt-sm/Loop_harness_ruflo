#!/usr/bin/env python3
"""Kiểm thử merge_updates.py — merge an toàn một nguồn vendored-skill.

Bao phủ: _glob_match, is_protected, classify_file, backup_directory,
restore_directory, clone_repo, py_compile_files, verify_after_update,
apply_vendored_copy, source_id_to_label, main().
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import merge_updates  # noqa: E402


@pytest.fixture
def patched_merge(tmp_path):
    """Patch REPO_ROOT, DEFAULT_BACKUP, TRACKER to tmp_path."""
    original_root = merge_updates.REPO_ROOT
    original_backup = merge_updates.DEFAULT_BACKUP
    original_tracker = merge_updates.TRACKER
    original_dirty = merge_updates.update_common.is_dirty_workspace
    merge_updates.REPO_ROOT = tmp_path
    merge_updates.DEFAULT_BACKUP = tmp_path / "backups"
    merge_updates.TRACKER = tmp_path / "REPOS_TRACKER.json"
    merge_updates.update_common.is_dirty_workspace = lambda: False
    yield tmp_path
    merge_updates.REPO_ROOT = original_root
    merge_updates.DEFAULT_BACKUP = original_backup
    merge_updates.TRACKER = original_tracker
    merge_updates.update_common.is_dirty_workspace = original_dirty


# --- _glob_match ---

@pytest.mark.parametrize("name,pat,expected", [
    ("README.md", "README*.md", True),
    ("README_API.md", "README*.md", True),
    ("SKILL.md", "SKILL.md", True),
    ("promo/banner.png", "*.png", True),
    (".gitignore", ".gitignore", True),
    ("promo/banner.md", "*.png", False),
    ("LICENSE", "LICENSE", True),
    ("examples/foo.json", "examples/**", True),
])
def test_glob_match(name, pat, expected):
    assert merge_updates._glob_match(name, pat) is expected


# --- is_protected ---

@pytest.mark.parametrize("path", [
    ".env",
    "secrets/key.pem",
    "HLK/config.json",
    ".devin/hooks/post_tool_use.py",
    ".devin/config.json",
    ".claude/settings.json",
    "credentials/token.key",
])
def test_is_protected_blocks(path):
    assert merge_updates.is_protected(path, merge_updates.PROTECTED_PATTERNS) is True


@pytest.mark.parametrize("path", [
    "src/foo.py",
    "docs/USAGE_GUIDE.md",
    "README.md",
    ".devin/scripts/merge_updates.py",
    "tools/check_updates.py",
])
def test_is_protected_allows(path):
    assert merge_updates.is_protected(path, merge_updates.PROTECTED_PATTERNS) is False


# --- classify_file ---

@pytest.mark.parametrize("rel,expected", [
    ("SKILL.md", "core"),
    ("README.md", "core"),
    ("README_API.md", "core"),
    ("LICENSE", "core"),
    ("scripts/something.py", "core"),
    ("ATTRIBUTION.md", "customization"),
    ("examples/foo.json", "customization"),
    ("local/config.json", "customization"),
    ("foo.local.json", "customization"),
    (".github/workflows/ci.yml", "skip"),
    (".gitignore", "skip"),
    (".gitattributes", "skip"),
    ("promo/banner.png", "skip"),
    ("promotion/old.md", "skip"),
    ("marketing/ad.png", "skip"),
    ("image.png", "skip"),
    ("data.zip", "skip"),
    ("archive.tar.gz", "skip"),
    ("foo.txt", "core"),
])
def test_classify_file(rel, expected):
    assert merge_updates.classify_file(rel) == expected


# --- source_id_to_label ---

def test_source_id_to_label_simple():
    assert merge_updates.source_id_to_label("nuwa-skill") == "nuwa-skill"


def test_source_id_to_label_with_slash():
    assert merge_updates.source_id_to_label("foo/bar") == "foo-bar"


def test_source_id_to_label_with_backslash():
    assert merge_updates.source_id_to_label("foo\\bar") == "foo-bar"


# --- backup_directory / restore_directory ---

def test_backup_directory_creates_copy(patched_merge, tmp_path):
    src = tmp_path / "skill"
    src.mkdir()
    (src / "SKILL.md").write_text("# Skill", encoding="utf-8")
    (src / "subdir").mkdir()
    (src / "subdir" / "file.txt").write_text("data", encoding="utf-8")

    backup = merge_updates.backup_directory(src, "test-skill")

    assert backup.exists()
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "# Skill"
    assert (backup / "subdir" / "file.txt").read_text(encoding="utf-8") == "data"


def test_restore_directory_restores_content(patched_merge, tmp_path):
    src = tmp_path / "original"
    src.mkdir()
    (src / "file.txt").write_text("original content", encoding="utf-8")

    import shutil
    backup = tmp_path / "backup"
    shutil.copytree(src, backup, dirs_exist_ok=True)

    target = tmp_path / "target"
    target.mkdir()
    (target / "file.txt").write_text("modified", encoding="utf-8")

    result = merge_updates.restore_directory(backup, target)
    assert result is True
    assert (target / "file.txt").read_text(encoding="utf-8") == "original content"


def test_restore_directory_missing_backup(patched_merge, tmp_path):
    backup = tmp_path / "nonexistent"
    target = tmp_path / "target"
    target.mkdir()
    result = merge_updates.restore_directory(backup, target)
    assert result is False


def test_restore_directory_outside_repo(patched_merge, tmp_path):
    backup = tmp_path / "backup"
    backup.mkdir()
    (backup / "x.txt").write_text("data", encoding="utf-8")
    outside = Path("/tmp/should-not-be-touched")
    result = merge_updates.restore_directory(backup, outside)
    assert result is False


# --- clone_repo ---

def test_clone_repo_rejects_non_https_url(patched_merge, tmp_path):
    dest = tmp_path / "clone-dest"
    result = merge_updates.clone_repo("file:///etc/passwd", dest)
    assert result is False


def test_clone_repo_rejects_untrusted_host(patched_merge, tmp_path):
    dest = tmp_path / "clone-dest"
    result = merge_updates.clone_repo("https://evil.com/repo.git", dest)
    assert result is False


def test_clone_repo_success_mock(patched_merge, tmp_path):
    dest = tmp_path / "clone-dest"
    with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
        result = merge_updates.clone_repo(
            "https://github.com/owner/repo.git", dest, "main", depth=1
        )
    assert result is True


def test_clone_repo_git_failure_mock(patched_merge, tmp_path):
    dest = tmp_path / "clone-dest"
    dest.mkdir()
    with patch.object(merge_updates, "run_cmd", return_value=(1, "", "clone error")):
        result = merge_updates.clone_repo(
            "https://github.com/owner/repo.git", dest
        )
    assert result is False


# --- py_compile_files ---

def test_py_compile_files_pass(patched_merge, tmp_path):
    good = tmp_path / "good.py"
    good.write_text("x = 1\n", encoding="utf-8")
    with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
        result = merge_updates.py_compile_files([good])
    assert result is True


def test_py_compile_files_fail(patched_merge, tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    with patch.object(merge_updates, "run_cmd", return_value=(1, "", "syntax error")):
        result = merge_updates.py_compile_files([bad])
    assert result is False


# --- verify_after_update ---

def test_verify_after_update_all_pass(patched_merge):
    with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
        result = merge_updates.verify_after_update([])
    assert result is True


def test_verify_after_update_verify_workspace_fails(patched_merge):
    def mock_run_cmd(cmd, **kwargs):
        cmd_str = " ".join(str(c) for c in cmd)
        if "verify-workspace" in cmd_str:
            return (1, "", "error")
        return (0, "", "")
    with patch.object(merge_updates, "run_cmd", side_effect=mock_run_cmd):
        result = merge_updates.verify_after_update([])
    assert result is False


def test_verify_after_update_hlk_fails(patched_merge):
    def mock_run_cmd(cmd, **kwargs):
        cmd_str = " ".join(str(c) for c in cmd)
        if "hlk-verify-integrity" in cmd_str:
            return (1, "", "error")
        return (0, "", "")
    with patch.object(merge_updates, "run_cmd", side_effect=mock_run_cmd):
        result = merge_updates.verify_after_update([])
    assert result is False


def test_verify_after_update_py_compile_fails(patched_merge, tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text("x = 1", encoding="utf-8")
    touched = [py_file]
    with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
        with patch.object(merge_updates, "py_compile_files", return_value=False):
            result = merge_updates.verify_after_update(touched)
    assert result is False


def test_verify_after_update_import_smoke_fails(patched_merge, tmp_path):
    py_file = Path(".devin/scripts/test.py")
    touched = [py_file]
    def mock_run_cmd(cmd, **kwargs):
        cmd_str = " ".join(str(c) for c in cmd)
        if "import_smoke_test" in cmd_str:
            return (1, "", "error")
        return (0, "", "")
    with patch.object(merge_updates, "run_cmd", side_effect=mock_run_cmd):
        result = merge_updates.verify_after_update(touched)
    assert result is False


# --- apply_vendored_copy ---

def test_apply_vendored_copy_dry_run_no_writes(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text("# new skill", encoding="utf-8")
    (upstream / "README.md").write_text("# readme", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=True, force_overwrite=False
    )

    assert "SKILL.md" in actions["copied"]
    assert "README.md" in actions["copied"]
    assert not (target / "SKILL.md").exists()
    assert not (target / "README.md").exists()


def test_apply_vendored_copy_new_files_copied(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text("# new", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=False, force_overwrite=False
    )

    assert "SKILL.md" in actions["copied"]
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "# new"


def test_apply_vendored_copy_identical_skipped(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text("# content", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()
    (target / "SKILL.md").write_text("# content", encoding="utf-8")

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=False, force_overwrite=False
    )

    assert "identical:SKILL.md" in actions["skipped"]
    assert "SKILL.md" not in actions["copied"]
    assert "SKILL.md" not in actions["overwritten"]


def test_apply_vendored_copy_core_overwrite(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text("# updated", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()
    (target / "SKILL.md").write_text("# old", encoding="utf-8")

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=False, force_overwrite=False
    )

    assert "SKILL.md" in actions["overwritten"]
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "# updated"


def test_apply_vendored_copy_protected_skipped(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text("# new", encoding="utf-8")
    (upstream / ".env").write_text("# upstream secret", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()
    (target / ".env").write_text("OLD=secret", encoding="utf-8")

    actions = merge_updates.apply_vendored_copy(
        upstream, target, [".env"], dry_run=False, force_overwrite=False
    )

    assert ".env" in actions["protected"]
    assert (target / ".env").read_text(encoding="utf-8") == "OLD=secret"


def test_apply_vendored_copy_customization_preserved(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "ATTRIBUTION.md").write_text("# upstream", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()
    (target / "ATTRIBUTION.md").write_text("# local", encoding="utf-8")

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=False, force_overwrite=False
    )

    assert "preserve:ATTRIBUTION.md" in actions["skipped"]
    assert (target / "ATTRIBUTION.md").read_text(encoding="utf-8") == "# local"


def test_apply_vendored_copy_skip_patterns(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "promo").mkdir()
    (upstream / "promo" / "banner.png").write_text("png", encoding="utf-8")
    (upstream / ".github").mkdir()
    (upstream / ".github" / "workflows").mkdir()
    (upstream / ".github" / "workflows" / "ci.yml").write_text("yml", encoding="utf-8")
    (upstream / "SKILL.md").write_text("# ok", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=False, force_overwrite=False
    )

    assert any("promo/banner.png" in s for s in actions["skipped"])
    assert any(".github/workflows/ci.yml" in s for s in actions["skipped"])
    assert "SKILL.md" in actions["copied"]


def test_apply_vendored_copy_force_overwrite_customization(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "ATTRIBUTION.md").write_text("# upstream", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()
    (target / "ATTRIBUTION.md").write_text("# local", encoding="utf-8")

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=False, force_overwrite=True
    )

    assert "ATTRIBUTION.md" in actions["overwritten"]
    assert (target / "ATTRIBUTION.md").read_text(encoding="utf-8") == "# upstream"


def test_apply_vendored_copy_skips_git_dir(patched_merge, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / ".git").mkdir()
    (upstream / ".git" / "config").write_text("git", encoding="utf-8")
    (upstream / "SKILL.md").write_text("# ok", encoding="utf-8")

    target = tmp_path / "skill"
    target.mkdir()

    actions = merge_updates.apply_vendored_copy(
        upstream, target, merge_updates.PROTECTED_PATTERNS, dry_run=True, force_overwrite=False
    )

    assert "SKILL.md" in actions["copied"]
    assert not any(".git" in s for s in actions["copied"])


# --- main() ---

def _write_tracker(tmp_path, source):
    """Helper: write a tracker JSON with one source."""
    tracker = tmp_path / "REPOS_TRACKER.json"
    tracker.write_text(json.dumps({"sources": [source]}), encoding="utf-8")
    return tracker


def test_main_source_id_not_found(patched_merge, tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill", "url": "https://github.com/owner/repo",
        "branch": "main", "vendored_path": "test-skill/", "merge_strategy": "direct-copy-vendored",
    })
    with patch("sys.argv", ["merge_updates.py", "--source-id", "nonexistent", "--tracker", str(tracker)]):
        with patch.object(merge_updates, "guard_branch", return_value=True):
            with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
                code = merge_updates.main()
    assert code == 1


def test_main_up_to_date(patched_merge, tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "abc1234", "upstream_commit": "abc1234",
        "status": "up-to-date", "merge_strategy": "direct-copy-vendored",
        "vendored_path": "test-skill/",
    })
    with patch("sys.argv", ["merge_updates.py", "--source-id", "test-skill", "--tracker", str(tracker)]):
        with patch.object(merge_updates, "guard_branch", return_value=True):
            code = merge_updates.main()
            assert code == 0


def test_main_invalid_strategy(patched_merge, tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "canon-source", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "old", "upstream_commit": "new123",
        "status": "behind", "merge_strategy": "manual-canon-update",
        "vendored_path": "",
    })
    with patch("sys.argv", ["merge_updates.py", "--source-id", "test-skill", "--tracker", str(tracker)]):
        with patch.object(merge_updates, "guard_branch", return_value=True):
            with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
                code = merge_updates.main()
    assert code == 0


def test_main_dry_run(patched_merge, tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "old", "upstream_commit": "new1234",
        "upstream_commit_full": "new1234full", "status": "behind",
        "merge_strategy": "direct-copy-vendored", "vendored_path": "test-skill/",
    })
    target = tmp_path / "test-skill"
    target.mkdir()
    with patch("sys.argv", ["merge_updates.py", "--source-id", "test-skill", "--tracker", str(tracker), "--dry-run"]):
        with patch.object(merge_updates, "guard_branch", return_value=True):
            with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
                with patch.object(merge_updates, "clone_repo", return_value=True):
                    with patch.object(merge_updates, "apply_vendored_copy",
                                      return_value={"copied": ["SKILL.md"], "overwritten": [], "skipped": [], "protected": []}):
                        code = merge_updates.main()
    assert code == 0


def test_main_no_changes(patched_merge, tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "old", "upstream_commit": "new1234",
        "upstream_commit_full": "new1234full", "status": "behind",
        "merge_strategy": "direct-copy-vendored", "vendored_path": "test-skill/",
    })
    target = tmp_path / "test-skill"
    target.mkdir()
    with patch("sys.argv", ["merge_updates.py", "--source-id", "test-skill", "--tracker", str(tracker)]):
        with patch.object(merge_updates, "guard_branch", return_value=True):
            with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
                with patch.object(merge_updates, "clone_repo", return_value=True):
                    with patch.object(merge_updates, "apply_vendored_copy",
                                      return_value={"copied": [], "overwritten": [], "skipped": [], "protected": []}):
                        code = merge_updates.main()
    assert code == 0


def test_main_verify_fail_rollback(patched_merge, tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "old", "upstream_commit": "new1234",
        "upstream_commit_full": "new1234full", "status": "behind",
        "merge_strategy": "direct-copy-vendored", "vendored_path": "test-skill/",
    })
    target = tmp_path / "test-skill"
    target.mkdir()
    with patch("sys.argv", ["merge_updates.py", "--source-id", "test-skill", "--tracker", str(tracker)]):
        with patch.object(merge_updates, "guard_branch", return_value=True):
            with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
                with patch.object(merge_updates, "clone_repo", return_value=True):
                    with patch.object(merge_updates, "apply_vendored_copy",
                                      return_value={"copied": ["SKILL.md"], "overwritten": [], "skipped": [], "protected": []}):
                        with patch.object(merge_updates, "backup_directory",
                                          return_value=tmp_path / "backup"):
                            with patch.object(merge_updates, "restore_directory", return_value=True):
                                with patch.object(merge_updates, "verify_after_update", return_value=False):
                                    code = merge_updates.main()
    assert code == 1


def test_main_success_tracker_updated(patched_merge, tmp_path):
    tracker = _write_tracker(tmp_path, {
        "id": "test-skill", "type": "vendored-skill", "url": "https://github.com/owner/repo",
        "branch": "main", "current_commit": "old", "upstream_commit": "new1234",
        "upstream_commit_full": "new1234full", "status": "behind",
        "merge_strategy": "direct-copy-vendored", "vendored_path": "test-skill/",
    })
    target = tmp_path / "test-skill"
    target.mkdir()
    with patch("sys.argv", ["merge_updates.py", "--source-id", "test-skill", "--tracker", str(tracker)]):
        with patch.object(merge_updates, "guard_branch", return_value=True):
            with patch.object(merge_updates, "run_cmd", return_value=(0, "", "")):
                with patch.object(merge_updates, "clone_repo", return_value=True):
                    with patch.object(merge_updates, "apply_vendored_copy",
                                      return_value={"copied": ["SKILL.md"], "overwritten": [], "skipped": [], "protected": []}):
                        with patch.object(merge_updates, "backup_directory",
                                          return_value=tmp_path / "backup"):
                            with patch.object(merge_updates, "verify_after_update", return_value=True):
                                code = merge_updates.main()
    assert code == 0
    data = json.loads(tracker.read_text(encoding="utf-8"))
    assert data["sources"][0]["status"] == "up-to-date"
    assert data["sources"][0]["current_commit"] == "new1234"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))