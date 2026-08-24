# Competitive Analysis: Fixing 14 Failed + 36 Error Pre-existing Tests

**Context**: 50 total failures (14 failed tests + 36 collection errors) across test modules: `test_cost_guard (3)`, `test_apply_ahd_patch_verify (1)`, `test_coverage_boost3 (3)`, `test_coverage_boost5 (1)`, `test_targeted_coverage_boost (3)`, `test_cve_remediation_phase2 (1)`, `test_harness_architecture_supreme (1)`, `test_import_smoke (1)`, `test_opencode_harness (1)`, `test_targeted_coverage_low_modules (30 errors)`. Root causes: **missing functions**, **fixture mismatches**, **test logic errors** — all pre-existing, not caused by refactor.

---

## Executive Summary

This is a **test debt remediation** problem, not a flakiness problem. The failures are deterministic (collection errors, missing fixtures, wrong assertions), not intermittent. Industry patterns show this requires **systematic error grouping → root cause analysis → prioritized fixing** rather than retry/quarantine strategies used for flaky tests.

---

## Approach Comparison Matrix

| Approach | Best For | Pros | Cons | Key Tools/Techniques |
|----------|----------|------|------|---------------------|
| **Smart Error Grouping + Systematic Fix** (Tessl/jbvc pattern) | Deterministic pre-existing failures grouped by root cause | • Fixes infrastructure first (imports, fixtures)<br>• Clear prioritization (impact → dependency order)<br>• Verifiable progress per group | • Requires upfront analysis<br>• Manual root cause identification | `pytest --collect-only`, error categorization, `git diff` for recent changes |
| **AI-Assisted Test Repair** (TaRGET/UTFix) | Large-scale assertion failures, signature mismatches | • 66% exact match accuracy (TaRGET)<br>• Handles assertion + coverage gaps<br>• Automates mechanical fixes | • Needs failure context (logs, slices)<br>• May miss semantic intent<br>• Requires LLM integration | TaRGET, UTFix, static/dynamic slices, change impact analysis |
| **Characterization/Golden Master Testing** (Feathers, TechDebt.repair) | Legacy code with no tests, unknown behavior | • Captures actual behavior safely<br>• Enables safe refactoring<br>• Documents bugs separately | • Not for fixing existing broken tests<br>• Scaffolding, not long-term strategy | Golden master, approval testing, mutation testing validation |
| **Test Impact Analysis + Selection** (Shopify, Faire, Adyen, Google) | Large suites needing faster CI | • 30x test reduction (Adyen)<br>• 75% compute reduction (Google)<br>• Risk-weighted guardrails | • Doesn't fix broken tests<br>• Requires coverage infrastructure<br>• Complex setup | Coverage mapping, call graphs, risk-weighted packs, AI ranking |
| **Fixture Architecture Remediation** (pytest-conftest hierarchy patterns) | Fixture mismatch, scope issues, collection errors | • Root cause fix for 30+ errors<br>• Prevents regression<br>• Scales to monorepos | • Requires conftest restructuring<br>• Package `__init__.py` discipline | `--import-mode=importlib`, `__init__.py` packaging, `pytest --trace-config` |
| **CI Pipeline Hardening** (GitHub, Dropbox Athena, Okta AutoGuardian) | Flaky + broken test mix at scale | • Auto-quarantine with tracking<br>• Bisect for breakage detection<br>• 18x flaky reduction (GitHub) | • Overkill for deterministic failures<br>• Infrastructure investment | Retry classification, flip-rate tracking, quarantine with TTL |

---

## Root Cause Analysis: Your Specific Error Types

### 1. **Missing Functions** (likely in `test_targeted_coverage_low_modules` 30 errors)
- **Pattern**: Tests reference functions/classes that don't exist or were renamed
- **Industry Fix**: 
  - **Tessl pattern**: Group all `ImportError`/`AttributeError` first — fix infrastructure before logic
  - **UTFix approach**: Use static analysis (AST) to find all references to missing symbols, map to actual implementations
  - **pytest-specific**: Run `pytest --collect-only -q` to surface all collection errors without running tests

### 2. **Fixture Mismatches** (likely in `test_cost_guard`, `test_coverage_boost*`, `test_targeted_coverage_boost`)
- **Pattern**: Scope mismatch (session vs function), missing conftest visibility, parametrization errors
- **Industry Fix**:
  - **Latchkey/QASkills pattern**: Use `pytest --fixtures` + `--trace-config` to audit fixture registry
  - **conftest hierarchy fix**: Add `__init__.py` to test directories, use `--import-mode=importlib`
  - **Scope alignment**: Factory pattern for complex fixtures, proper scoping (session/module/function)

### 3. **Test Logic Errors** (assertion failures in `test_apply_ahd_patch_verify`, `test_harness_architecture_supreme`, etc.)
- **Pattern**: Wrong expected values, type mismatches, async not awaited, object equality issues
- **Industry Fix**:
  - **OneUpTime pattern**: Systematic debugging — read error, verify expected value, check types, add diagnostics
  - **UTFix/TaRGET**: Feed failure logs + static/dynamic slices to LLM for repair suggestions
  - **Assertion best practices**: `pytest.approx()` for floats, deep equality for objects, `have.members()` for unordered lists

---

## Recommended Hybrid Strategy for Your Case

### Phase 1: Triage & Grouping (30-60 min)
```bash
# 1. Collect all errors without running tests
pytest --collect-only -q 2>&1 | head -100

# 2. Group by error type
pytest -v 2>&1 | grep -E "(FAILED|ERROR)" | awk '{print $1}' | sort | uniq -c | sort -rn

# 3. Categorize:
# - Collection errors (ImportError, ModuleNotFoundError, fixture not found) → INFRASTRUCTURE
# - AssertionError → LOGIC
# - Other runtime errors → RUNTIME
```

### Phase 2: Fix Infrastructure First (Highest Impact)
| Error Group | Fix Strategy | Tools |
|-------------|--------------|-------|
| **30 collection errors** (`test_targeted_coverage_low_modules`) | Add missing `__init__.py`, fix imports, install package (`pip install -e .`), align conftest hierarchy | `pytest --trace-config`, `--import-mode=importlib` |
| **Fixture mismatches** (cost_guard, coverage_boost*) | Audit with `pytest --fixtures`, move fixtures to common ancestor conftest, fix scope | Factory pattern, proper scoping |
| **Missing functions** | Map via AST/grep, implement stubs or fix imports | `grep -r "function_name" tests/`, `git log --oneline -20` |

### Phase 3: Fix Logic Errors (AssertionError)
- **Per-test diagnosis**: Add diagnostic output to see actual vs expected
- **Type mismatches**: Convert before compare (`str()`, `int()`, `pytest.approx()`)
- **Async issues**: Add `await` where missing
- **Object equality**: Implement `__eq__` or use deep comparison

### Phase 4: Verification & Guardrails
```bash
# Run fixed groups in isolation first
pytest tests/test_cost_guard.py -v
pytest tests/test_coverage_boost3.py -v
# ... per module

# Full suite verification
pytest -x --tb=short

# Add CI guardrails
# - pytest-xdist for parallel (if not already)
# - pytest-rerunfailures ONLY for known flaky (not for these deterministic failures)
# - Coverage gate: --fail-under=current_coverage (never decrease)
```

---

## Tool Recommendations by Category

| Category | Tool | Purpose | Cost/Complexity |
|----------|------|---------|-----------------|
| **Error Grouping** | `pytest --collect-only`, custom script | Categorize 50 failures by root cause | Low |
| **Fixture Debugging** | `pytest --fixtures -v`, `--trace-config` | Audit fixture registry, find scope mismatches | Low |
| **Import/Collection** | `pytest --import-mode=importlib`, `__init__.py` packaging | Fix conftest hierarchy, namespace issues | Low-Medium |
| **AI-Assisted Repair** | UTFix/TaRGET pattern (custom LLM prompt) | Fix assertion failures, signature mismatches | Medium (needs LLM) |
| **Coverage Analysis** | `pytest-cov`, `coverage.py` | Find uncovered lines for characterization tests | Low |
| **Mutation Testing** | `mutmut` | Validate characterization tests catch bugs | Medium |
| **CI Optimization** | Test selection (if suite grows) | Reduce CI time post-fix | High (later phase) |

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It Fails Here | Better Alternative |
|--------------|-------------------|-------------------|
| **Retry/quarantine** | These are deterministic errors, not flaky | Fix root cause, don't mask |
| **Skip/mark xfail** | Technical debt accumulates, no safety net | Fix or delete; characterization test if behavior unknown |
| **Broad refactor** | Scope creep, breaks more tests | Smallest coherent diff per error group |
| **Fix logic before infrastructure** | Fixture/import errors cascade into false logic failures | Infrastructure → API → Logic order |
| **Ignore 30 errors in one module** | `test_targeted_coverage_low_modules` likely has systemic issue | Analyze pattern: all same error type? |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Collection errors** | 0 | `pytest --collect-only` exits clean |
| **Failed tests** | 0 | `pytest -x` passes full suite |
| **Coverage** | ≥ current (no regression) | `pytest --cov --fail-under=X` |
| **CI time** | ≤ current | GitHub Actions workflow duration |
| **Flaky rate** | <2% (if any remain) | Flip-rate tracking over 20 runs |

---

## References

1. **Tessl/jbvc test-fixing skill** — Smart error grouping methodology
2. **TaRGET (IEEE TSE 2025)** — Automated test repair with LLMs, 66.1% exact match
3. **UTFix (arXiv 2025)** — Change-aware unit test repair with static/dynamic slices
4. **GitHub flaky test reduction (18x)** — Retry classification, impact scoring, auto-assignment
5. **Okta AutoGuardian** — Automated flaky detection + quarantine + ticket creation
6. **Dropbox Athena** — Build health automation, bisect for breakage detection
7. **pytest conftest hierarchy (PTD, Latchkey, QASkills)** — Fixture visibility, import modes, packaging
8. **Shopify Test Budget** — Time-constrained CI, prioritization criteria (failure_rate, churn, coverage)
9. **Faire Test Avoidance** — Configuration-based selection, 67% skip rate, dry-run validation
10. **Adyen Test Selection** — 30x test reduction, coverage + static analysis + rules
11. **TechDebt.repair / Feathers** — Characterization tests for legacy, golden master
12. **CI/CD Watch / Augment Code** — Flip-rate, failure-rate, age-of-last-green classification

---

## Next Steps

1. **Run triage script** to categorize all 50 failures by error type
2. **Fix conftest hierarchy** (add `__init__.py`, set `importlib` mode) — likely resolves 30+ collection errors
3. **Audit fixtures** with `pytest --fixtures -v` — resolve scope mismatches
4. **Map missing functions** via grep/AST — implement or fix imports
5. **Fix assertion logic** per test with diagnostic output
6. **Add coverage gate** to prevent regression
7. **Document decisions** in `docs/plans/<slug>/EXECUTION_REPORT.md`

---

*Analysis compiled from 15+ industry sources covering pytest internals, test repair automation, CI optimization, and legacy test remediation patterns.*