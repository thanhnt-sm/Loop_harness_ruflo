# Constraint Ledger — Test Remediation (14 Failed + 36 Errors Pre-existing)

**Generated:** 2026-08-24
**Task:** Fix pre-existing test failures in: `test_cost_guard (3)`, `test_apply_ahd_patch_verify (1)`, `test_coverage_boost3 (3)`, `test_coverage_boost5 (1)`, `test_targeted_coverage_boost (3)`, `test_cve_remediation_phase2 (1)`, `test_harness_architecture_supreme (1)`, `test_import_smoke (1)`, `test_opencode_harness (1)`, `test_targeted_coverage_low_modules (30 errors)`
**Note:** Current run shows 812 passed, 4 skipped; only coverage gate fails (33% < 80%). Ledger captures constraints for any remediation work.

---

## 1. Security Policies (MUST COMPLY)

### 1.1 Project Security Policy (SECURITY.md)

| Policy | Requirement | Enforcement |
|--------|-------------|-------------|
| **Input Validation** | Zod schemas for all public API inputs | Schema gate hook (`.devin/hooks/schema_gate.py`) |
| **SQL Injection Prevention** | Parameterized queries only | Code review, static analysis |
| **Path Traversal Prevention** | `PathValidator` module | `.devin/hooks/pre_tool_use.py` SSRF/encoding checks |
| **Command Injection Protection** | `SafeExecutor` module | `.devin/hooks/pre_tool_use.py` dangerous command block |
| **Vulnerability Reporting** | Email `security@cognitum.one` | 48h ack, 7d assessment, 30d fix target |
| **Safe Harbor** | Good-faith research authorized | No legal action if guidelines followed |

### 1.2 Hook Enforcement (Runtime Guards)

| Hook | Security Function | Fail Mode |
|------|-------------------|-----------|
| `pre_tool_use.py` | SSRF block, encoding bypass detection, dangerous command block (`rm -rf`, `git push --force`, `DROP TABLE`), cost cap gate, reflection gate | **Fail-closed** — blocks on parse error or missing HMAC |
| `schema_gate.py` | Validates tool input against JSON schemas | Blocks invalid payloads |
| `approval_gate.py` | Ed25519 signature verification for reviewer approval | Fail-closed without valid signature |
| `hook_integrity.py` | SHA-256 baseline verification of hook files | Detects tampering |

### 1.3 CVE Remediation Requirements (From Test Names)

| CVE ID | Requirement | Test Coverage |
|--------|-------------|---------------|
| CVE-2026-AHD-003 | Idempotency fail-closed with `filelock` backend | `test_cve_remediation_phase2.py` |
| CVE-2026-AHD-006 | Approval gate Ed25519 verify with `cryptography` | `test_cve_remediation_phase3.py` |
| Dependency Pinning | `filelock<3.13` (asyncio import regression) | `pyproject.toml` enforced |

---

## 2. Performance Budgets (HARD LIMITS)

### 2.1 Test Execution Budgets

| Metric | Budget | Source | Violation Action |
|--------|--------|--------|------------------|
| **Hook Timeout** | 2.5 seconds per hook | `pre_tool_use.py` | Hook kills process, fail-closed |
| **Import Time (filelock)** | < 0.5s (v3.12.x), ~6s (v3.13+) | `pyproject.toml` comment | Pin `<3.13` mandatory |
| **Pytest Session** | < 120s total (CI) | `pytest.ini` hypothesis config | Parallelize or reduce `max_examples` |
| **Hypothesis Examples** | 100 per property | `pytest.ini` + `pyproject.toml` | Hard limit |
| **Coverage Gate** | ≥ 80% line coverage | `pytest.ini --cov-fail-under=80` | **Hard FAIL** — blocks CI |

### 2.2 Resource Budgets

| Resource | Limit | Monitoring |
|----------|-------|------------|
| **Memory Cap** | Configurable via `check_memory_cap` | `.devin/scripts/ahd_session.py` |
| **Circuit Breaker** | Trips after N failures | `AhdSession.record_failure()` |
| **Token Budget** | Per-request via `token_budget.py` | Runtime enforcement |

---

## 3. Compatibility Matrix

### 3.1 Python Version Support

| Python | Status | Notes |
|--------|--------|-------|
| **3.11** | ✅ Minimum required | `pyproject.toml: requires-python = ">=3.11"` |
| **3.12** | ✅ Tested | CI target |
| **3.13** | ⚠️ Supported | `filelock<3.13` pin avoids asyncio import regression |

### 3.2 Platform Compatibility

| Platform | Symlink Support | Notes |
|----------|-----------------|-------|
| **Linux** | ✅ Full | Primary CI target |
| **macOS** | ✅ Full | |
| **Windows** | ❌ Limited | `test_cve_remediation_phase2.py:553`, `test_targeted_coverage_low_modules.py:422,439` skipped — "Không có quyền tạo symlink" |

### 3.3 Dependency Compatibility

| Dependency | Version Constraint | Rationale |
|------------|-------------------|-----------|
| `pydantic` | `>=2.0` | Data models, schema validation |
| `filelock` | `>=3.0,<3.13` | **CVE-2026-AHD-003** — asyncio import regression in 3.13+ |
| `cryptography` | `>=41.0` | **CVE-2026-AHD-006** — Ed25519 verify |
| `pytest` | `>=7.0` | Test runner |
| `pytest-cov` | `>=4.0` | Coverage measurement |
| `hypothesis` | `>=6.0` | Property-based testing |

### 3.4 Test Configuration Compatibility

| Config File | Purpose | Override Priority |
|-------------|---------|-------------------|
| `pytest.ini` | Primary test config | Highest for test discovery |
| `pyproject.toml` | Coverage + tool config | Coverage `fail_under=80` |
| `.coveragerc` | Coverage fine-tuning | Lowest priority |

---

## 4. Compliance Standards (MANDATORY)

### 4.1 Regulatory Frameworks (from Web Search)

| Standard | Scope | Test Artifacts Required | Relevance to This Task |
|----------|-------|------------------------|------------------------|
| **DORA (Digital Operational Resilience Act)** | EU financial entities + critical ICT third parties | Threat-led penetration testing (TLPT), scenario-based resilience testing, ICT risk register tied to test outcomes | **HIGH** — Harness runs penetration tests (`test_pentest_*.py`), red-team simulations |
| **PCI DSS v4.0** | Cardholder data environments | Vulnerability scans, penetration test reports, change control test evidence, PCI/non-PCI separation | **MEDIUM** — If harness processes payment flows |
| **SOX Section 404** | US public companies — ICFR | Control test results, change approval records, segregation-of-duties evidence | **MEDIUM** — If used in financial reporting pipelines |
| **FFIEC IT Examination Handbook** | US banks, credit unions, service providers | Documented testing methodology, traceability requirements→test cases, regression evidence, UAT sign-offs | **HIGH** — Testing methodology documentation required |
| **NIST SP 800-160 Vol.1 Rev.1** | Engineering trustworthy secure systems | Data sanitization for test environments, production data protection | **HIGH** — Test fixtures must not use real secrets |

### 4.2 Testing Methodology Requirements (FFIEC V.B + DORA)

| Requirement | Implementation in Harness |
|-------------|---------------------------|
| **Test Policies/Standards/Procedures** | `pytest.ini`, `pyproject.toml`, `AGENTS.md` workflow |
| **Testing Scope Documentation** | Test file naming (`test_*.py`), class organization (`Test*`) |
| **Production Data Controls** | **MUST NOT** use real secrets — `test_no_secret_log.py`, `test_pentest_secret_redaction.py` |
| **Test Results Documentation** | Coverage reports, `EXECUTION_REPORT.md` per plan |
| **Corrective Action Tracking** | Git commits linked to plan tasks, `check_governance.py` |
| **Security Testing** | SAST (ruff), penetration tests (`test_pentest_*.py`), red-team (`test_red_team_suite.py`) |
| **Regression Testing** | Full suite on every change (`pytest.ini addopts`) |
| **Traceability** | `REQ ID` in `IMPLEMENTATION_PLAN.md` → test functions |

### 4.3 Azure Well-Architected Security Testing (Microsoft Learn)

| Control | Validation Required |
|---------|---------------------|
| **Encryption Controls** | Test after every key rotation, cert renewal |
| **Network Controls** | Deny-by-default verification, topology change tests |
| **Application Code** | Deployed app resistance to common attacks (not just source scan) |
| **Identity-Based Attacks** | AuthZ bypass, token theft/replay, lateral movement, privilege escalation |
| **Threat Detection** | End-to-end simulation → SIEM correlation → alert SLA validation |
| **Adversary-Based Testing** | Red-team/blue-team exercises, penetration testing |

---

## 5. Test Remediation Constraints (SPECIFIC TO THIS TASK)

### 5.1 Test-Specific Constraints

| Test Module | Known Issues | Constraints |
|-------------|--------------|-------------|
| `test_cost_guard` (3 failures) | Cost cap state logic, fixture mismatch | Must preserve `filelock<3.13` behavior; cost tracking via `.devin/scripts/cost_tracker.py` |
| `test_apply_ahd_patch_verify` (1 failure) | Smoke test verification logic | Must use `approval_gate.py` Ed25519 verify; no mock HMAC in production |
| `test_coverage_boost3` (3 failures) | DAG executor state management | State persistence via `.devin/scripts/dag_executor.py`; resume-from-dict logic |
| `test_coverage_boost5` (1 failure) | Session/blackboard/event bus integration | Shared state paths must use `AhdSession.get_*_root()`; no hardcoded paths |
| `test_targeted_coverage_boost` (3 failures) | CLI path coverage for multiple scripts | Each CLI `main()` must handle `--help`, missing args, invalid JSON |
| `test_cve_remediation_phase2` (1 failure) | Idempotency + filelock + symlink | **Windows symlink skipped**; fallback lock must work; `filelock<3.13` pin |
| `test_harness_architecture_supreme` (1 failure) | Architecture validation | Must validate all 3 executors (lightning/glm/kimi) + orchestrator FSM |
| `test_import_smoke` (1 failure) | Import chain completeness | All `.devin/scripts/*.py` must import without side effects |
| `test_opencode_harness` (1 failure) | OpenCode integration guard | HMAC key required; pre_tool_use blocks without it |
| `test_targeted_coverage_low_modules` (30 errors) | Low-coverage module CLI tests | Each module's `main()` must be exercised; helpers must have unit tests |

### 5.2 Governance Constraints (WORKSPACE_GOVERNANCE.md)

| Rule | Enforcement |
|------|-------------|
| **No junk files** | `tmp/` only for scratch; auto-clean; `tools/junk_file_scanner.py` |
| **File placement** | Scripts → `.devin/scripts/` + `tests/test_*.py`; Hooks → `.devin/hooks/`; Plans → `docs/plans/<slug>/` |
| **Plan ↔ Act** | Only modify files listed in approved `IMPLEMENTATION_PLAN.md`; write `EXECUTION_REPORT.md` after |
| **Root markdown ban** | No new `.md` at root — use `docs/` or `docs/plans/<slug>/` |
| **Provider isolation** | `.devin/` state only for Devin; `.khuym/` only for Khuym; no cross-contamination |

---

## 6. Remediation Approach Constraints

### 6.1 Allowed Changes

| Category | Allowed | Not Allowed |
|----------|---------|-------------|
| **Test Logic** | Fix assertions, add missing fixtures, correct mock setup | Change production code behavior to match broken tests |
| **Fixtures** | Add `pytest.fixture` for shared state isolation | Use production state paths in tests |
| **Mocks** | Mock external dependencies (network, time, HMAC) | Mock internal logic that should be tested |
| **Coverage** | Add tests for uncovered branches | Remove coverage gate or lower threshold |
| **Symlinks** | Use `tmp_path` fixture; skip on Windows | Require symlinks for test validity |

### 6.2 Forbidden Patterns

| Pattern | Reason | Detection |
|---------|--------|-----------|
| Hardcoded `.devin/state/` paths in tests | Breaks isolation, corrupts prod state | `pre_tool_use.py` path validation |
| Real secrets in test fixtures | PCI DSS / FFIEC violation | `test_no_secret_log.py`, secret scanner |
| `time.sleep()` in tests | Flakiness, slows CI | Use `freezegun` or async mock |
| Modifying `HLK/` or `.devin/canon/` | Security layer integrity | `hlk-integrity-check` blocks |
| Cross-provider state writes | Workspace governance violation | `check_governance.py` |

---

## 7. Acceptance Criteria for Remediation

| Criterion | Verification Method |
|-----------|---------------------|
| **All 14 failed tests pass** | `pytest <specific_test_files> -v` |
| **All 36 errors resolved** | `pytest <specific_test_files> --tb=short` → 0 errors |
| **Coverage ≥ 80%** | `pytest --cov=.devin --cov-fail-under=80` |
| **No governance violations** | `python tools/check_governance.py` → exit 0 |
| **No junk files** | `python tools/junk_file_scanner.py` → 0 findings |
| **Security hooks pass** | `pytest tests/test_pre_tool_use.py tests/test_schema_gate.py tests/test_approval_gate.py -v` |
| **CVE remediation verified** | `pytest tests/test_cve_remediation_phase2.py tests/test_cve_remediation_phase3.py -v` |
| **Windows compatibility** | All symlink-dependent tests skip gracefully (not fail) |

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Fixing tests masks production bugs | Medium | High | Run full suite + penetration tests after remediation |
| Coverage gate hides untested critical paths | High | Medium | Review `term-missing` output; prioritize security-critical modules |
| Windows symlink skips reduce coverage | High | Medium | Add Windows-compatible fallback tests |
| `filelock` version drift | Low | Critical | Pin `<3.13` in `pyproject.toml` + `requirements-lock.txt` |
| HMAC key missing in CI | Medium | High | Document `OPENCODE_HMAC_KEY` requirement; skip gracefully |

---

## 9. References

- **SECURITY.md** — Project security policy
- **WORKSPACE_GOVERNANCE.md** — File placement, plan/act contract, provider isolation
- **pytest.ini** — Test discovery, coverage gate, hypothesis config
- **pyproject.toml** — Dependencies, coverage config, tool config
- **DORA Article 25** — ICT testing programme requirements
- **FFIEC V.B Testing** — Testing methodology, production data controls
- **Azure Well-Architected Security Testing** — Control validation, adversary simulation
- **PCI DSS v4.0** — Vulnerability management, penetration testing
- **NIST SP 800-160** — Data sanitization, trustworthy systems

---

*This ledger is the authoritative constraint reference for the test remediation task. All remediation work must comply with every "MUST" and "SHALL" item above.*