"""Regression tests — Phase 2 remediation (CVE-006..010).

Chạy: python -m pytest tests/test_cve_remediation_phase2.py -q -p no:cacheprovider --timeout=90 -o addopts=""
"""
import base64
import importlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".devin" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".devin" / "hooks"))

crypto = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

import approval_gate as ag  # noqa: E402


@pytest.fixture()
def plan_file(tmp_path):
    p = tmp_path / "IMPLEMENTATION_PLAN.md"
    p.write_text("# Plan\n- T1\n", encoding="utf-8", newline="\n")
    return p


@pytest.fixture()
def signer():
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode()
    return priv, pub_b64


# ---------------------------------------------------------------------------
# CVE-006: approval gate Ed25519
# ---------------------------------------------------------------------------
def test_approve_without_keys_legacy(plan_file, monkeypatch):
    monkeypatch.delenv("AHD_REVIEWER_KEYS", raising=False)
    r = ag.cmd_approve(plan_file, "alice", "ok")
    assert r["status"] == "approved"


def test_approve_missing_signature_rejected(plan_file, signer, monkeypatch):
    _, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    r = ag.cmd_approve(plan_file, "alice", "ok")
    assert r["status"] == "pending"
    assert "Signature" in r.get("error", "")


def test_approve_valid_signature(plan_file, signer, monkeypatch):
    priv, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    ts = "2026-08-14T10:00:00+00:00"
    ph = ag.plan_hash(plan_file)
    sig = base64.b64encode(priv.sign(ag._sig_message(ph, "alice", ts))).decode()
    r = ag.cmd_approve(plan_file, "alice", "ok", signature=sig, signed_ts=ts)
    assert r["status"] == "approved"
    assert r["date"] == ts
    assert r["plan_hash"] == ph
    assert r["signature"] == sig


def test_approve_forged_signature_rejected(plan_file, signer, monkeypatch):
    priv, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    ts = "2026-08-14T10:00:00+00:00"
    ph = ag.plan_hash(plan_file)
    other = Ed25519PrivateKey.generate()
    sig = base64.b64encode(other.sign(ag._sig_message(ph, "alice", ts))).decode()
    r = ag.cmd_approve(plan_file, "alice", "ok", signature=sig, signed_ts=ts)
    assert r["status"] == "pending"
    assert "hợp lệ" in r.get("error", "")


def test_approve_reviewer_mismatch_rejected(plan_file, signer, monkeypatch):
    priv, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    ts = "2026-08-14T10:00:00+00:00"
    ph = ag.plan_hash(plan_file)
    sig = base64.b64encode(priv.sign(ag._sig_message(ph, "mallory", ts))).decode()
    r = ag.cmd_approve(plan_file, "alice", "ok", signature=sig, signed_ts=ts)
    assert r["status"] == "pending"


def test_approve_tampered_plan_rejected(plan_file, signer, monkeypatch):
    """Signature gắn với plan_hash — sửa plan sau khi ký -> phải từ chối."""
    priv, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    ts = "2026-08-14T10:00:00+00:00"
    ph = ag.plan_hash(plan_file)
    sig = base64.b64encode(priv.sign(ag._sig_message(ph, "alice", ts))).decode()
    plan_file.write_text("# Plan\n- T1\n- T2 EVIL\n", encoding="utf-8")
    r = ag.cmd_approve(plan_file, "alice", "ok", signature=sig, signed_ts=ts)
    assert r["status"] == "pending"


def test_approve_key_rotation(plan_file, signer, monkeypatch):
    priv, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    ts = "2026-08-14T10:00:00+00:00"
    ph = ag.plan_hash(plan_file)
    sig = base64.b64encode(priv.sign(ag._sig_message(ph, "alice", ts))).decode()
    assert ag.cmd_approve(plan_file, "alice", "ok", signature=sig, signed_ts=ts)["status"] == "approved"
    # Rotate: key cũ bị remove, key mới được chấp nhận
    priv_new = Ed25519PrivateKey.generate()
    monkeypatch.setenv("AHD_REVIEWER_KEYS", base64.b64encode(priv_new.public_key().public_bytes_raw()).decode())
    sig_new = base64.b64encode(priv_new.sign(ag._sig_message(ph, "alice", ts))).decode()
    assert ag.cmd_approve(plan_file, "alice", "ok", signature=sig_new, signed_ts=ts)["status"] == "approved"
    assert ag.cmd_approve(plan_file, "alice", "ok", signature=sig, signed_ts=ts)["status"] == "pending"


def test_reject_needs_no_signature(plan_file, signer, monkeypatch):
    _, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    r = ag.cmd_reject(plan_file, "alice", "thiếu test")
    assert r["status"] == "rejected"


def test_audit_log_append_only(plan_file, signer, monkeypatch, tmp_path):
    _, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    ag.cmd_reject(plan_file, "alice", "no")
    ag.cmd_reject(plan_file, "alice", "no again")
    audit = tmp_path / ".devin" / "telemetry" / "approvals.jsonl"
    lines = audit.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "mỗi event 1 dòng append-only, không ghi đè"
    for line in lines:
        rec = json.loads(line)
        assert rec["event"] == "approval_rejected"
        assert rec["plan_hash"]


def test_verify_signature_bad_inputs(plan_file):
    assert ag.verify_signature(b"msg", "", []) is False
    assert ag.verify_signature(b"msg", "!!!not-base64!!!", ["AAAA"]) is False
    assert ag.verify_signature(b"msg", "AAAA", ["not-base64-key"]) is False


# ---------------------------------------------------------------------------
# CVE-007: encoding bypass detection order (pre_tool_use)
# ---------------------------------------------------------------------------
def _run_pre_tool_use(command: str, reload: bool = True, monkeypatch=None) -> int:
    import io
    import pre_tool_use
    import pre_tool_callgraph
    import pre_tool_gates
    import pre_tool_cli
    import pre_tool_workspace
    # Set cost ledger key for tests (CVE-2026-AHD-013 fail-closed requires it)
    # Use monkeypatch if available, otherwise set directly and clean up
    key = "test-key-" + "k" * 32
    if monkeypatch is not None:
        monkeypatch.setenv("AHD_COST_LEDGER_KEY", key)
    else:
        os.environ["AHD_COST_LEDGER_KEY"] = key
    if reload:
        importlib.reload(pre_tool_workspace)
        importlib.reload(pre_tool_callgraph)
        importlib.reload(pre_tool_gates)
        importlib.reload(pre_tool_cli)
        importlib.reload(pre_tool_use)
    # Mock call-graph gate and workspace layout gate to not interfere with encoding bypass tests
    # Direct assignment works better than monkeypatch across reloads
    mocked = [
        (pre_tool_use, "_check_call_graph_gate"),
        (pre_tool_gates, "_check_call_graph_gate"),
        (pre_tool_callgraph, "_check_call_graph_gate"),
        (pre_tool_cli, "_check_call_graph_gate"),
        (pre_tool_gates, "_check_workspace_layout_gate"),
        (pre_tool_workspace, "_check_workspace_layout_gate"),
        (pre_tool_cli, "_check_workspace_layout_gate"),
    ]
    _MISSING = object()
    saved = [(mod, name, getattr(mod, name, _MISSING)) for mod, name in mocked]
    for mod, name in mocked:
        setattr(mod, name, lambda _data: None)
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
        try:
            pre_tool_use.main()
        except SystemExit as e:
            return e.code if e.code is not None else 0
    finally:
        sys.stdin = old_stdin
        if monkeypatch is None:
            os.environ.pop("AHD_COST_LEDGER_KEY", None)
        # Hoàn nguyên gate gốc để tránh nhiễm state sang test file khác.
        # pre_tool_use from-import copy reference nên phải re-bind tay sau khi restore.
        for mod, name, fn in saved:
            if fn is _MISSING:
                delattr(mod, name)
            else:
                setattr(mod, name, fn)
        for name in ("_check_call_graph_gate", "_check_workspace_layout_gate"):
            if hasattr(pre_tool_gates, name):
                setattr(pre_tool_use, name, getattr(pre_tool_gates, name))
    return 0


@pytest.mark.parametrize("command", [
    r"echo \x72\x6d -rf /",              # hex escape rm (double-encoded)
    r"rm -rf \x2f",                      # hex escape path separator
    r"echo \u0072m -rf /",               # unicode escape rm
    r"echo \162\155 -rf /",              # octal escape rm
    "echo '+ADw-script+AD4-' | bash",    # UTF-7 encoded <script>
    "echo '+AGY-' | bash",               # UTF-7 pipe to shell
    "ping xn--malicious.com",            # punycode
    "echo '&#47;etc&#47;passwd'",        # HTML entity
    "echo aGVsbG8= | base64 -d | sh",    # base64 pipe
])
def test_cve007_encoded_bypass_blocked(command, monkeypatch):
    assert _run_pre_tool_use(command, monkeypatch=monkeypatch) == 2


@pytest.mark.parametrize("command", [
    "git status",
    "pip install requests",
    "ls -la /tmp",
    "grep -E 'a\\.b' file.txt",       # legit regex escape
    "echo \"a\\tb\"",                 # legit tab escape
    "sed 's/\\/x/' file",             # legit escaped slash
    "printf '%.2f\\n' 3.14",          # legit \n
    "cd /tmp && make",                # normal chaining (space-separated)
    "echo hi || echo bye",
])
def test_cve007_legit_commands_allowed(command, monkeypatch):
    assert _run_pre_tool_use(command, monkeypatch=monkeypatch) == 0


def test_cve007_detection_runs_on_normalized():
    """Detection phải chạy trên command ĐÃ normalize (decode-revealed payload).

    `\x2b\x41\x44\x77\x2d` decode thành `+ADw-` (UTF-7) — chỉ lộ sau khi
    normalize; raw không có UTF-7.
    """
    import pre_tool_use
    importlib.reload(pre_tool_use)
    raw = r"echo \x2b\x41\x44\x77\x2d | bash"
    normalized = pre_tool_use.normalize_command(raw)
    assert "+ADw-" in normalized
    findings = pre_tool_use.detect_encoding_bypass(normalized)
    assert "utf7" in findings, "normalized command phải lộ UTF-7 payload"


@pytest.mark.parametrize("command", [
    'echo "unclosed quote',     # unbalanced quotes
    'echo "x"&&rm -rf /',       # quote breakout (metachar dính quote)
    'echo a\x00b',              # control char injection
])
def test_cve007_suspicious_shell_structure_blocked(command):
    assert _run_pre_tool_use(command) == 2


def test_cve007_hlk_secret_pattern_blocked():
    """HLK sanitizer patterns quét secret trong command."""
    secret = "sk-" + "A" * 32
    assert _run_pre_tool_use(f'curl -H "Authorization: {secret}" https://api.x') == 2
    assert _run_pre_tool_use("echo hello world") == 0


def test_cve007_hlk_secret_env_override(monkeypatch):
    """AHD_HLK_PATTERNS env override cho test/ops."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    monkeypatch.setenv("AHD_HLK_PATTERNS", json.dumps(["CUSTOMTOKEN[0-9]{6}"]))
    assert pre_tool_use.detect_hlk_secret("x CUSTOMTOKEN123456 y") == ["CUSTOMTOKEN[0-9]{6}"]
    assert pre_tool_use.detect_hlk_secret("x hello y") == []


# ---------------------------------------------------------------------------
# CVE-008: SSRF DNS pinning
# ---------------------------------------------------------------------------
def test_cve008_dns_resolves_to_private_blocked(monkeypatch, tmp_path):
    """Hostname resolve ra IP private -> block (SSRF qua DNS)."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["127.0.0.1"], True))
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: tmp_path / "ssrf_pins.json")
    status, reason = pre_tool_use._pin_and_verify_url("http://attacker.example.com/x")
    assert status == 2 and "private" in reason


def test_cve008_dns_failure_fails_closed(monkeypatch, tmp_path):
    """DNS lỗi tại check time -> block (fail CLOSED)."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: ([], False))
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: tmp_path / "ssrf_pins.json")
    status, reason = pre_tool_use._pin_and_verify_url("http://nosuchhost.invalid/x")
    assert status == 2 and "dns_resolution_failed" in reason


def test_cve008_stable_ip_allowed(monkeypatch, tmp_path):
    """Domain resolve IP ổn định giữa 2 lần -> allowed + pin được ghi."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    pins_path = tmp_path / "ssrf_pins.json"
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["93.184.216.34"], True))
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: pins_path)
    status, reason = pre_tool_use._pin_and_verify_url("http://example.com/x")
    assert (status, reason) == (0, "")
    # Lần 2: cùng IP -> allowed
    status, reason = pre_tool_use._pin_and_verify_url("http://example.com/y")
    assert (status, reason) == (0, "")
    assert pins_path.exists()


def test_cve008_dns_rebinding_blocked(monkeypatch, tmp_path):
    """IP public đổi hoàn toàn trong TTL -> DNS rebinding -> block."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    pins_path = tmp_path / "ssrf_pins.json"
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: pins_path)
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["1.2.3.4"], True))
    status, _ = pre_tool_use._pin_and_verify_url("http://rebind.example.com/x")
    assert status == 0
    # Attacker flip DNS -> IP public khác hoàn toàn
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["5.6.7.8"], True))
    status, reason = pre_tool_use._pin_and_verify_url("http://rebind.example.com/x")
    assert status == 2 and "dns_rebinding" in reason


def test_cve008_rebinding_after_ttl_allowed(monkeypatch, tmp_path):
    """Sau TTL, IP đổi là hợp lệ (không còn là rebinding)."""
    import pre_tool_use
    import pre_tool_secrets
    importlib.reload(pre_tool_use)
    importlib.reload(pre_tool_secrets)
    pins_path = tmp_path / "ssrf_pins.json"
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: pins_path)
    monkeypatch.setattr(pre_tool_secrets, "time", time)
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["1.2.3.4"], True))
    assert pre_tool_use._pin_and_verify_url("http://ttl.example.com/x")[0] == 0
    # Giả lập TTL đã hết: ghi đè ts quá khứ
    pins = pre_tool_use._load_ssrf_pins()
    pins["ttl.example.com"]["ts"] = time.time() - 3600
    pre_tool_use._save_ssrf_pins(pins)
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["9.9.9.9"], True))
    status, reason = pre_tool_use._pin_and_verify_url("http://ttl.example.com/x")
    assert status == 0, reason


def test_cve008_ipv6_support(monkeypatch, tmp_path):
    """IPv6: resolve ra ::1 (loopback) -> block; ::ffff private -> block."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: tmp_path / "ssrf_pins.json")
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["::1"], True))
    status, reason = pre_tool_use._pin_and_verify_url("http://v6.example.com/x")
    assert status == 2 and "private" in reason
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["::ffff:192.168.1.1"], True))
    status, reason = pre_tool_use._pin_and_verify_url("http://v6b.example.com/x")
    assert status == 2 and "private" in reason


def test_cve008_ip_literal_skips_dns(monkeypatch, tmp_path):
    """IP literal (kể cả encoded) không cần DNS — không bao giờ resolve."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    called = []
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: called.append(host) or ([], True))
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: tmp_path / "ssrf_pins.json")
    assert pre_tool_use._pin_and_verify_url("http://93.184.216.34/x")[0] == 0
    assert pre_tool_use._pin_and_verify_url("http://2130706433/x")[0] == 0
    assert called == [], "IP literal không được phép resolve DNS"


def test_cve008_gate_blocks_rebinding_command(monkeypatch, tmp_path, capsys):
    """Gate-level: command với host rebinding -> exit 2."""
    import pre_tool_use
    importlib.reload(pre_tool_use)
    pins_path = tmp_path / "ssrf_pins.json"
    monkeypatch.setattr(pre_tool_use, "_ssrf_pins_path", lambda: pins_path)
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["1.2.3.4"], True))
    monkeypatch.setenv("AHD_SSRF_ALLOWLIST", "")
    # Lần 1: pin (reload=False — giữ monkeypatch của module)
    assert _run_pre_tool_use("curl http://gate-rebind.example.com/x", reload=False) == 0
    # Lần 2: IP đổi -> block
    monkeypatch.setattr(pre_tool_use, "_resolve_host", lambda host: (["5.6.7.8"], True))
    assert _run_pre_tool_use("curl http://gate-rebind.example.com/x", reload=False) == 2


# ---------------------------------------------------------------------------
# CVE-009: REQ ID cross-reference với approved SDD
# ---------------------------------------------------------------------------
def _make_plan_repo(tmp_path, sdd_reqs: list[str], plan_reqs: list[str]) -> Path:
    """Tạo repo giả: docs/plans/task1/{SOLUTION_DESIGN.md, IMPLEMENTATION_PLAN.md}
    + SDD approval state (hash hợp lệ)."""
    root = tmp_path / "repo"
    plans_dir = root / "docs" / "plans" / "task1"
    plans_dir.mkdir(parents=True)
    (root / ".devin").mkdir()

    sdd_text = "## Requirements\n" + "\n".join(f"- {r}: thing" for r in sdd_reqs) + "\n"
    sdd = plans_dir / "SOLUTION_DESIGN.md"
    sdd.write_text(sdd_text, encoding="utf-8")

    plan = plans_dir / "IMPLEMENTATION_PLAN.md"
    plan.write_text(
        "## Requirements\n"
        + "\n".join(f"- {r}: do thing" for r in plan_reqs)
        + "\n\n## Test\n"
        + "\n".join(f"{r} test case" for r in plan_reqs)
        + "\n\n"
        + "\n".join(
            f"- T{i+1}: do thing file: src/foo.py func: bar AC: returns 42 R2 rollback: revert"
            for i in range(len(plan_reqs))
        )
        + "\nPlan follows AGENTS.md\n",
        encoding="utf-8",
    )

    import hashlib
    state_dir = root / ".devin" / "plan_state"
    state_dir.mkdir()
    state = {
        "plan_file": "docs/plans/task1/SOLUTION_DESIGN.md",
        "artifact": "sd",
        "status": "approved",
        "reviewer": "alice",
        "date": "2026-08-14T10:00:00+00:00",
        "plan_hash": hashlib.sha256(sdd.read_bytes()).hexdigest(),
    }
    (state_dir / "task1_sd_approved.json").write_text(json.dumps(state), encoding="utf-8")
    return root


def test_cve009_plan_with_extra_req_fails(tmp_path):
    """Plan có REQ không nằm trong SDD -> D11 FAIL -> all_pass False."""
    from plan_quality_check import run_checks
    root = _make_plan_repo(tmp_path, sdd_reqs=["REQ-001"], plan_reqs=["REQ-001", "REQ-999"])
    plan = root / "docs" / "plans" / "task1" / "IMPLEMENTATION_PLAN.md"
    sc = run_checks(plan)
    d11 = next(d for d in sc["dimensions"] if d["id"] == "D11")
    assert d11["pass"] is False
    assert "REQ-999" in d11["detail"]
    assert sc["all_pass"] is False


def test_cve009_plan_subset_passes(tmp_path):
    """Plan REQ ⊆ SDD REQ -> D11 PASS."""
    from plan_quality_check import run_checks
    root = _make_plan_repo(tmp_path, sdd_reqs=["REQ-001", "REQ-002"], plan_reqs=["REQ-001"])
    plan = root / "docs" / "plans" / "task1" / "IMPLEMENTATION_PLAN.md"
    sc = run_checks(plan)
    d11 = next(d for d in sc["dimensions"] if d["id"] == "D11")
    assert d11["pass"] is True


def test_cve009_sdd_modified_after_approval_fails(tmp_path):
    """SDD bị sửa sau approval -> hash mismatch -> D11 FAIL (fail closed)."""
    from plan_quality_check import run_checks
    root = _make_plan_repo(tmp_path, sdd_reqs=["REQ-001"], plan_reqs=["REQ-001"])
    sdd = root / "docs" / "plans" / "task1" / "SOLUTION_DESIGN.md"
    sdd.write_text("## Requirements\n- REQ-001: EVIL MODIFIED\n", encoding="utf-8")
    plan = root / "docs" / "plans" / "task1" / "IMPLEMENTATION_PLAN.md"
    sc = run_checks(plan)
    d11 = next(d for d in sc["dimensions"] if d["id"] == "D11")
    assert d11["pass"] is False
    assert "hash_mismatch" in d11["detail"]


def test_cve009_no_sdd_state_keeps_10d(tmp_path):
    """Legacy flow không có SDD approval state -> vẫn 10 dimensions (không D11)."""
    from plan_quality_check import run_checks
    p = tmp_path / "plan.md"
    p.write_text(
        "## Requirements\n- REQ-001: do thing\n\n"
        "## Test\nREQ-001 test case\n\n"
        "- T1: do thing file: src/foo.py func: bar AC: returns 42 R2 rollback: revert\n"
        "Plan follows AGENTS.md\n",
        encoding="utf-8",
    )
    sc = run_checks(p)
    assert sc["total_dimensions"] == 10
    assert all(d["id"] != "D11" for d in sc["dimensions"])


# ---------------------------------------------------------------------------
# CVE-010: coverage matrix file hash verification
# ---------------------------------------------------------------------------
def _make_approved_repo(tmp_path, plan_text: str, files: dict[str, bytes]) -> Path:
    """Tạo repo có plan approved (file_hashes trong state) + các file tham chiếu."""
    import hashlib
    root = tmp_path / "repo10"
    plans_dir = root / "docs" / "plans" / "task1"
    plans_dir.mkdir(parents=True)
    (root / ".devin").mkdir()
    for rel, content in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content)
    plan = plans_dir / "IMPLEMENTATION_PLAN.md"
    plan.write_text(plan_text, encoding="utf-8")
    state_dir = root / ".devin" / "plan_state"
    state_dir.mkdir()
    file_hashes = {}
    for rel, content in files.items():
        file_hashes[rel] = hashlib.sha256(content).hexdigest()
    state = {
        "plan_file": "docs/plans/task1/IMPLEMENTATION_PLAN.md",
        "artifact": "plan",
        "status": "approved",
        "reviewer": "alice",
        "plan_hash": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "file_hashes": file_hashes,
    }
    (state_dir / "task1_approved.json").write_text(json.dumps(state), encoding="utf-8")
    return root


PLAN_T1 = (
    "## Requirements\n- REQ-001: do thing\n\n"
    "## Test\nREQ-001 test case\n\n"
    "- T1: REQ-001 do thing file: `src/foo.py` func: bar AC: returns 42 R2 rollback: revert\n"
    "Plan follows AGENTS.md\n"
)


def test_cve010_file_replaced_after_approval_fails(tmp_path):
    """File bị sửa sau approval -> verification FAIL (file modified since approval)."""
    from coverage_matrix import verify_matrix
    root = _make_approved_repo(tmp_path, PLAN_T1, {"src/foo.py": b"def bar(): return 1\n"})
    plan = root / "docs" / "plans" / "task1" / "IMPLEMENTATION_PLAN.md"
    sc = verify_matrix(plan)
    assert sc["all_verified"] is True
    # Sửa file sau approval
    (root / "src" / "foo.py").write_bytes(b"def bar(): return 2  # EVIL\n")
    sc = verify_matrix(plan)
    assert sc["all_verified"] is False
    entry = list(sc["matrix"].values())[0]
    assert entry["status"] == "FAIL"
    assert "modified since approval" in entry["evidence"]


def test_cve010_unchanged_file_passes(tmp_path):
    """File không đổi -> verification PASS."""
    from coverage_matrix import verify_matrix
    root = _make_approved_repo(tmp_path, PLAN_T1, {"src/foo.py": b"def bar(): return 1\n"})
    plan = root / "docs" / "plans" / "task1" / "IMPLEMENTATION_PLAN.md"
    sc = verify_matrix(plan)
    assert sc["all_verified"] is True


def test_cve010_symlink_swap_detected(tmp_path):
    """Symlink swap: target đổi -> hash của target đổi -> FAIL."""
    from coverage_matrix import verify_matrix
    root = _make_approved_repo(tmp_path, PLAN_T1, {"src/foo.py": b"def bar(): return 1\n"})
    # Swap: thay file thật bằng symlink trỏ file khác nội dung
    target2 = root / "src" / "evil.py"
    target2.write_bytes(b"def bar(): return 1  # evil content\n")
    real = root / "src" / "foo.py"
    real.unlink()
    try:
        real.symlink_to(target2)
        plan = root / "docs" / "plans" / "task1" / "IMPLEMENTATION_PLAN.md"
        sc = verify_matrix(plan)
        assert sc["all_verified"] is False
        entry = list(sc["matrix"].values())[0]
        assert entry["status"] == "FAIL"
        assert "modified since approval" in entry["evidence"]
    except OSError:
        pytest.skip("symlink not supported on this platform")


def test_cve010_large_file_chunked_hash(tmp_path):
    """File lớn (>4MB) hash qua chunk — không OOM, kết quả đúng."""
    from coverage_matrix import _sha256_chunked
    import hashlib
    big = tmp_path / "big.bin"
    content = b"x" * (4 * 1024 * 1024 + 123)
    big.write_bytes(content)
    assert _sha256_chunked(big) == hashlib.sha256(content).hexdigest()


def test_cve010_archive_immutable(plan_file, signer, monkeypatch, tmp_path):
    """Plan approved được archive vào .devin/artifacts/<plan_hash>/ (immutable)."""
    priv, pub_b64 = signer
    monkeypatch.setenv("AHD_REVIEWER_KEYS", pub_b64)
    ts = "2026-08-14T10:00:00+00:00"
    ph = ag.plan_hash(plan_file)
    sig = base64.b64encode(priv.sign(ag._sig_message(ph, "alice", ts))).decode()
    r = ag.cmd_approve(plan_file, "alice", "ok", signature=sig, signed_ts=ts, artifact="plan")
    assert r["status"] == "approved"
    root = ag._repo_root(plan_file)
    artifact = root / ".devin" / "artifacts" / ph / plan_file.name
    assert artifact.exists()
    assert artifact.read_bytes() == plan_file.read_bytes()
    # Sửa plan sau approval -> archive không đổi (immutable)
    plan_file.write_text("# Plan modified\n", encoding="utf-8")
    assert artifact.read_bytes() == b"# Plan\n- T1\n"
    assert r["file_hashes"] == {}