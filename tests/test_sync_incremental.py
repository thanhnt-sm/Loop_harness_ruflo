"""Tests cho incremental sync (sync_to_mirrors.py với state file)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
sys.path.insert(0, str(ROOT / "HLK"))
from scripts import sync_to_mirrors  # noqa: E402


@pytest.fixture
def mock_hlk_repo(tmp_path):
    """Tạo mock repo với HLK/chain/ + .devin/scripts/ + .commandcode/ + .opencode/."""
    hlk_chain = tmp_path / "HLK" / "chain"
    hlk_skill = tmp_path / "HLK" / "skills" / "verify-first"
    devin_scripts = tmp_path / ".devin" / "scripts"
    cmdc_skills = tmp_path / ".commandcode" / "skills" / "verify-first"
    opencode_cmd = tmp_path / ".opencode" / "command"
    state_dir = tmp_path / ".devin" / "state"

    hlk_chain.mkdir(parents=True)
    hlk_skill.mkdir(parents=True)
    devin_scripts.mkdir(parents=True)
    cmdc_skills.mkdir(parents=True)
    opencode_cmd.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    # Tạo 3 HLK modules với __all__
    for name in ["alpha", "beta", "gamma"]:
        (hlk_chain / f"{name}.py").write_text(
            f'__all__ = ["func_{name}"]\n'
            f'def func_{name}():\n    return "{name}"\n',
            encoding="utf-8",
        )
    (hlk_skill / "SKILL.md").write_text("# verify-first skill\n", encoding="utf-8")
    return tmp_path


def test_first_run_creates_all(mock_hlk_repo):
    """Lần đầu sync: tất cả files được tạo."""
    state_file = mock_hlk_repo / ".devin" / "state" / "sync_state.json"
    actions = sync_to_mirrors.sync_to_devin(mock_hlk_repo, dry_run=False,
                                          incremental=True, state={},
                                          state_file=state_file)
    assert len(actions) == 3
    assert all("created/updated" in a[0] for a in actions)
    # State file phải tồn tại và có 3 entries
    assert state_file.exists()
    state = sync_to_mirrors.load_state(state_file)
    assert len([k for k in state if k.startswith("devin:")]) == 3


def test_second_run_skips_all(mock_hlk_repo):
    """Lần 2 sync (không có thay đổi): tất cả files skipped."""
    state_file = mock_hlk_repo / ".devin" / "state" / "sync_state.json"
    # Lần 1: tạo + save state
    sync_to_mirrors.sync_to_devin(mock_hlk_repo, dry_run=False,
                                  incremental=True, state={},
                                  state_file=state_file)
    # Lần 2: load state + skip
    state = sync_to_mirrors.load_state(state_file)
    actions = sync_to_mirrors.sync_to_devin(mock_hlk_repo, dry_run=False,
                                          incremental=True, state=state,
                                          state_file=state_file)
    assert len(actions) == 0  # tất cả skipped


def test_modify_one_file_syncs_only_one(mock_hlk_repo):
    """Modify 1 file HLK → chỉ file đó sync ở lần 2."""
    state_file = mock_hlk_repo / ".devin" / "state" / "sync_state.json"
    # Lần 1
    sync_to_mirrors.sync_to_devin(mock_hlk_repo, dry_run=False,
                                  incremental=True, state={},
                                  state_file=state_file)
    # Modify alpha.py
    (mock_hlk_repo / "HLK" / "chain" / "alpha.py").write_text(
        '__all__ = ["func_alpha", "new_func"]\n'
        'def func_alpha():\n    return "alpha"\n'
        'def new_func():\n    return "new"\n',
        encoding="utf-8",
    )
    # Lần 2
    state = sync_to_mirrors.load_state(state_file)
    actions = sync_to_mirrors.sync_to_devin(mock_hlk_repo, dry_run=False,
                                          incremental=True, state=state,
                                          state_file=state_file)
    assert len(actions) == 1
    assert "alpha.py" in actions[0][1]


def test_force_flag_bypasses_state(mock_hlk_repo):
    """--force → sync tất cả, bỏ qua state."""
    state_file = mock_hlk_repo / ".devin" / "state" / "sync_state.json"
    # Lần 1
    sync_to_mirrors.sync_to_devin(mock_hlk_repo, dry_run=False,
                                  incremental=True, state={},
                                  state_file=state_file)
    # Lần 2 với --force (incremental=False)
    state = sync_to_mirrors.load_state(state_file)
    actions = sync_to_mirrors.sync_to_devin(mock_hlk_repo, dry_run=False,
                                          incremental=False, state=state,
                                          state_file=None)
    assert len(actions) == 3  # tất cả sync lại


def test_sync_to_cmdc_uses_state(mock_hlk_repo):
    """sync_to_cmdc dùng state để skip khi không đổi."""
    state_file = mock_hlk_repo / ".devin" / "state" / "sync_state.json"
    sync_to_mirrors.sync_to_cmdc(mock_hlk_repo, dry_run=False,
                                 incremental=True, state={},
                                 state_file=state_file)
    state = sync_to_mirrors.load_state(state_file)
    actions = sync_to_mirrors.sync_to_cmdc(mock_hlk_repo, dry_run=False,
                                          incremental=True, state=state,
                                          state_file=state_file)
    assert len(actions) == 0  # skipped (no change)


def test_sync_to_opencode_uses_state(mock_hlk_repo):
    """sync_to_opencode dùng state."""
    state_file = mock_hlk_repo / ".devin" / "state" / "sync_state.json"
    sync_to_mirrors.sync_to_opencode(mock_hlk_repo, dry_run=False,
                                    incremental=True, state={},
                                    state_file=state_file)
    state = sync_to_mirrors.load_state(state_file)
    actions = sync_to_mirrors.sync_to_opencode(mock_hlk_repo, dry_run=False,
                                              incremental=True, state=state,
                                              state_file=state_file)
    assert len(actions) == 0
