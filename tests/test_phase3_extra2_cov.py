"""Coverage bổ sung: cost_ledger CLI/key-fallback + memory_audit distill/dedupe."""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
HOOKS = SCRIPTS.parent / "hooks"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HOOKS))


class TestCostLedgerCLIAndKey:
    def test_cli_verify(self, tmp_path, monkeypatch):
        import cost_ledger as cl

        monkeypatch.delenv("AHD_COST_LEDGER_KEY", raising=False)
        cl.append_entry(tmp_path, "s", "bash", 0.5, 0.5)
        cl.append_entry(tmp_path, "s", "edit", 0.5, 1.0)
        report = cl.verify_integrity(tmp_path)
        assert report["total"] == 2

    def test_cli_global_and_usage(self, tmp_path, monkeypatch):
        import cost_ledger as cl

        monkeypatch.setenv("AHD_COST_LEDGER_KEY", "k")
        monkeypatch.chdir(tmp_path)
        cl.append_entry(tmp_path, "s", "bash", 0.5, 0.5)
        assert cl.global_cumulative(tmp_path) == 0.5
        assert cl._load_hmac_key(tmp_path) == b"k"

    def test_key_from_state_file(self, tmp_path, monkeypatch):
        import cost_ledger as cl

        monkeypatch.delenv("AHD_COST_LEDGER_KEY", raising=False)
        kf = tmp_path / ".agents" / "state" / ".cost_ledger_key"
        kf.parent.mkdir(parents=True, exist_ok=True)
        kf.write_text("file-key", encoding="utf-8")
        assert cl._load_hmac_key(tmp_path) == b"file-key"

    def test_key_from_hlk_vault(self, tmp_path, monkeypatch):
        import cost_ledger as cl

        monkeypatch.delenv("AHD_COST_LEDGER_KEY", raising=False)
        env = tmp_path / "HLK" / "config" / "secrets.env"
        env.parent.mkdir(parents=True, exist_ok=True)
        env.write_text('COST_LEDGER_KEY="vault-key"\n', encoding="utf-8")
        assert cl._load_hmac_key(tmp_path) == b"vault-key"
        # vault tồn tại nhưng không có key -> fallback state file
        env.write_text("OTHER=1\n", encoding="utf-8")
        kf = tmp_path / ".agents" / "state" / ".cost_ledger_key"
        kf.parent.mkdir(parents=True, exist_ok=True)
        kf.write_text("file-key", encoding="utf-8")
        assert cl._load_hmac_key(tmp_path) == b"file-key"

    def test_cli_subprocess(self, tmp_path):
        import subprocess

        env = dict(__import__("os").environ, AHD_COST_LEDGER_KEY="cli-key")
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "cost_ledger.py"), "verify"],
            capture_output=True, text=True, timeout=60, cwd=tmp_path, env=env,
        )
        assert r.returncode == 0, r.stderr
        report = json.loads(r.stdout)
        assert "total" in report
        r2 = subprocess.run(
            [sys.executable, str(SCRIPTS / "cost_ledger.py"), "global"],
            capture_output=True, text=True, timeout=60, cwd=tmp_path, env=env,
        )
        assert r2.returncode == 0 and "global_cumulative" in r2.stdout
        r3 = subprocess.run(
            [sys.executable, str(SCRIPTS / "cost_ledger.py"), "bogus"],
            capture_output=True, text=True, timeout=60, cwd=tmp_path, env=env,
        )
        assert r3.returncode == 2

    def test_config_root_fallback(self, tmp_path, monkeypatch):
        import cost_ledger as cl

        # ahd_session không import được -> fallback root/.devin / cwd
        monkeypatch.setitem(sys.modules, "ahd_session", None)
        assert cl._config_root(tmp_path) == tmp_path / ".devin"
        assert cl._repo_root(None) == Path.cwd()

    def test_verify_hmac_mismatch(self, tmp_path, monkeypatch):
        import cost_ledger as cl

        monkeypatch.setenv("AHD_COST_LEDGER_KEY", "k1")
        cl.append_entry(tmp_path, "s", "bash", 0.5, 0.5)
        entries = cl.read_ledger(tmp_path)
        assert cl._verify(dict(entries[0]), b"k1") is True
        assert cl._verify(dict(entries[0]), b"wrong") is False
        assert cl._verify({"cost": 1.0}, b"k1") is False  # thiếu hmac


class TestMemoryAuditDistill:
    def test_dedupe_and_valid_filter(self, tmp_path):
        import memory_audit as ma

        existing = [{"trigger": "a", "correct_action": "x"},
                    {"trigger": "b", "correct_action": "y"}]
        cands = [{"trigger": "a", "correct_action": "x"},  # dup
                 {"trigger": "c"},                          # invalid
                 {"trigger": "d", "correct_action": "z"}]
        out = ma._dedupe(existing, cands)
        assert out == existing + [{"trigger": "d", "correct_action": "z"}]
        assert ma._valid({"trigger": "t", "correct_action": "c"}) is True
        assert ma._valid({"trigger": "t"}) is False

    def test_distill_caps_at_20(self, tmp_path):
        import memory_audit as ma

        entries = [{"trigger": f"t{i}", "correct_action": f"c{i}",
                    "ts": f"{i}"} for i in range(25)]
        out = ma._distill(entries)
        assert len(out) == 20
        assert out[-1]["trigger"] == "t24"

    def test_parse_knowledge_entries_multiline(self, tmp_path):
        import memory_audit as ma

        text = (
            "- trigger: t1\n"
            "  correct_action: c1\n"
            "  counter: k1\n"
            "  ts: 2026-01-01\n"
            "\n"
            "- trigger: t2\n"
            "  correct_action: c2\n"
            "\n"
        )
        entries = ma._parse_knowledge_entries(text)
        assert len(entries) == 2
        assert entries[0]["counter"] == "k1"
        assert entries[1]["correct_action"] == "c2"
        assert "ts" not in entries[1]
        # entry dang dở không có blank line cuối
        entries2 = ma._parse_knowledge_entries("- trigger: t3\n  correct_action: c3")
        assert len(entries2) == 1 and entries2[0]["trigger"] == "t3"