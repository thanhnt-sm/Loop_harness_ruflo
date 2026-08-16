"""V5-01: Agent registry lifecycle — owner/expiry/revocation enforcement."""
from datetime import date
from pathlib import Path

import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))

from agents.registry import AgentCapability, AgentRegistry


def _registry() -> AgentRegistry:
    reg = AgentRegistry(definitions_dir=Path("unused"))
    reg._loaded = True
    return reg


def _seed(reg: AgentRegistry, *caps: AgentCapability) -> None:
    reg._agents = {c.id: c for c in caps}


def _cap(agent_id: str, **kw) -> AgentCapability:
    defaults = dict(id=agent_id, version="1.0", capabilities=["code_implementation"])
    defaults.update(kw)
    return AgentCapability(**defaults)


def test_active_no_expires_matches():
    reg = _registry()
    _seed(reg, _cap("a"))
    assert [a.id for a in reg.match(["code_implementation"])] == ["a"]


def test_expired_excluded():
    reg = _registry()
    _seed(reg, _cap("good", expires="2999-01-01"), _cap("stale", expires="2000-01-01"))
    assert [a.id for a in reg.match(["code_implementation"])] == ["good"]


def test_revoked_excluded():
    reg = _registry()
    _seed(reg, _cap("a"), _cap("bad"))
    assert reg.revoke("bad")
    assert [a.id for a in reg.match(["code_implementation"])] == ["a"]


def test_decommissioned_excluded():
    reg = _registry()
    _seed(reg, _cap("a"), _cap("retired"))
    assert reg.decommission("retired")
    assert [a.id for a in reg.match(["code_implementation"])] == ["a"]


def test_form_team_skips_revoked():
    reg = _registry()
    _seed(reg, _cap("builder", capabilities=["code_implementation", "test_writing"]), _cap("hijacked"))
    reg.revoke("hijacked")
    team = reg.form_team({"builder": ["code_implementation", "test_writing"]})
    assert team["builder"].id == "builder"


def test_legacy_missing_fields_still_active():
    reg = _registry()
    _seed(reg, _cap("legacy"))
    assert reg._is_active(_cap("legacy"))
    assert [a.id for a in reg.match(["code_implementation"])] == ["legacy"]


def test_revoke_unknown_id_returns_false():
    reg = _registry()
    _seed(reg, _cap("a"))
    assert not reg.revoke("nope")


def test_list_agents_default_excludes_inactive():
    reg = _registry()
    _seed(reg, _cap("a"), _cap("dead", status="decommissioned"))
    assert [a.id for a in reg.list_agents()] == ["a"]
    assert len(reg.list_agents(include_inactive=True)) == 2


def test_unparseable_expires_fails_closed():
    reg = _registry()
    _seed(reg, _cap("a", expires="not-a-date"))
    assert not reg._is_active(_cap("a", expires="not-a-date"))
    assert reg.match(["code_implementation"]) == []


def test_yaml_load_respects_lifecycle(tmp_path):
    (tmp_path / "manifest.yaml").write_text("registry: test\n")
    (tmp_path / "live.yaml").write_text(
        'id: live\nversion: "1.0"\ncapabilities: [x]\nexpires: \'2999-01-01\'\n'
    )
    (tmp_path / "expired.yaml").write_text(
        'id: dead\nversion: "1.0"\ncapabilities: [x]\nexpires: \'2000-01-01\'\n'
    )
    reg = AgentRegistry(definitions_dir=tmp_path)
    import asyncio

    asyncio.run(reg.load())
    assert [a.id for a in reg.match(["x"])] == ["live"]
