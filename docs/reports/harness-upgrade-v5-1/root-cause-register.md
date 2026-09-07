# Root Cause Register — V5 Iteration 1

**Generated**: 2026-09-04
**Mode**: AUDIT_ONLY (static analysis)

---

## Root Cause Analysis (5 Whys per Critical/High)

### RC-001: No Revocation Infrastructure (ATT-001) — **STRUCTURAL**

```
1. Vì sao agent không bị thu hồi quyền khi human revoke consent?
   → Không có identity service quản lý token lifecycle

2. Vì sao không có identity service?
   → Harness thiết kế permission model tĩnh (hook-based), không dynamic delegation

3. Vì sao chọn model tĩnh thay vì dynamic?
   → Ưu tiên đơn giản, deterministic, không phụ thuộc external service

4. Vì sao không thêm revocation check vào hook chain?
   → Hook chain chỉ validate governance, không validate token lifecycle

5. Vì sao không thiết kế token lifecycle từ đầu?
   → **NGUYÊN NHÂN GỐC**: Permission model thiếu khái niệm "delegation với expiry/revocation". Mọi permission được coi là vĩnh viễn trong session. Cần redesign: permission = (actor, resource, action, scope, expiry, revocation_source).
```

**Classification**: **STRUCTURAL** — cần redesign permission model kiến trúc.

**Risk Matrix**: Impact=Critical (unbounded access), Likelihood=Medium (session compromise) → **Critical**

**Definition of Done**:
- [ ] Permission model redesign: add expiry, revocation_source, delegation chain
- [ ] Identity service (local) hoặc hook check revocation_list
- [ ] Re-attack ATT-001: simulate revocation → agent blocked
- [ ] No regression on existing hook chain
- [ ] Auto-test: revocation bound test case

---

### RC-002: Unpinned Critical Dependencies Not Enforced (ATT-002) — **MECHANICAL**

```
1. Vì sao filelock 3.13+ và pydantic-core mismatch không bị chặn?
   → `tools/check_deps.py` tồn tại nhưng không chạy trong pre-commit hook chain

2. Vì sao check_deps.py không trong hook chain?
   → Pre-commit hook chỉ chạy: redaction, junk scanner, gitignore audit, governance
   → Không có gate "dependency pin verification"

3. Vì sao không có gate dependency pin?
   → Ưu tiên governance gates trước, dependency gate chưa implement

4. Vì sao comment trong pyproject.toml không đủ?
   → Comment là documentation, không phải enforcement. Machine không đọc comment.

5. Vì sao không enforce hash-pinned lockfile ở gate cài đặt?
   → **NGUYÊN NHÂN GỐC**: Thiếu enforcement hook cho `uv pip install` / `pip install` verify hash-pinned lockfile. Lockfile sinh ra nhưng không verify khi dùng.
```

**Classification**: **MECHANICAL** — cần enforcement hook.

**Risk Matrix**: Impact=Critical (hook timeout break, resolution impossible), Likelihood=High (dep update common) → **Critical**

**Definition of Done**:
- [ ] Add `check_deps.py` to pre-commit hook (gate 5)
- [ ] Add `check_deps.py` to pre_tool_use hook for pip/uv commands
- [ ] Re-attack ATT-002: try install filelock 3.13+ → blocked
- [ ] No regression on legitimate installs
- [ ] Auto-test: dependency pin violation test case

---

### RC-003: Tool Poisoning via Skill Registration (ATT-003) — **STRUCTURAL**

```
1. Vì sao skill độc hại có thể đăng ký trigger tùy ý?
   → skill_index.json không validate trigger strings

2. Vì sao không validate trigger?
   → Skill system tin tưởng skill authors, không có trigger allowlist

3. Vì sao không có trigger allowlist?
   → Trigger được coi là free-text để flexible cho Nuwa distillation

4. Vì sao flexible trigger quan trọng hơn security?
   → Nuwa skill distillation cần tạo trigger mới cho perspective skills

5. Vì sao không tách trusted vs untrusted skill namespace?
   → **NGUYÊN NHÂN GỐC**: Skill system không phân biệt "core skills" (trusted, validated) vs "dynamic skills" (Nuwa-generated, cần review). Cần namespace phân quyền.
```

**Classification**: **STRUCTURAL** — cần skill namespace + trigger schema.

**Risk Matrix**: Impact=High (task hijack), Likelihood=Medium (skill write access) → **High**

**Definition of Done**:
- [ ] Define skill trigger schema (regex allowlist)
- [ ] Core skills namespace: `.devin/skills/core/` (validated)
- [ ] Dynamic skills namespace: `.devin/skills/dynamic/` (review required)
- [ ] Hook validates trigger on skill load
- [ ] Re-attack ATT-003: malicious skill trigger → blocked
- [ ] No regression on Nuwa skill creation

---

### RC-004: Memory Poisoning Validation Not Automated (ATT-004) — **MECHANICAL**

```
1. Vì sao knowledge_distill có thể chứa pattern sai?
   → memory_audit.py validate nhưng không bắt buộc chạy trước ghi

2. Vì sao memory_audit.py không bắt buộc?
   → Distillation chạy trong Memory Keeper worker, không có gate

3. Vì sao Memory Keeper không có gate?
   → Worker pattern: dispatcher tin tưởng worker output

4. Vì sao không có verification gate cho worker output?
   → Maker≠checker principle chưa áp dụng cho memory worker

5. Vì sao không áp dụng maker≠checker cho memory?
   → **NGUYÊN NHÂN GỐC**: Memory pipeline thiếu independent verifier. Producer (Memory Keeper) cũng là verifier. Cần fable-judge hoặc claim-grader gate cho memory writes.
```

**Classification**: **MECHANICAL** — cần verification gate cho memory writes.

**Risk Matrix**: Impact=Medium (wrong patterns), Likelihood=Medium (distillation errors) → **High**

**Definition of Done**:
- [ ] Add memory write gate: `fable-judge` or `claim-grader` validates trigger+action+counter
- [ ] Hook memory_audit.py into post_tool_use for knowledge_distill writes
- [ ] Re-attack ATT-004: invalid pattern → rejected
- [ ] No regression on valid distillations

---

### RC-005: Vendored Skill No Provenance Verification (ATT-005) — **STRUCTURAL**

```
1. Vì sao nuwa-skill vendored không verify provenance?
   → Vendoring process manual: copy files, update REPOS.md

2. Vì sao không có automated provenance check?
   → Không có supply chain gate trong update_from_repos skill

4. Vì sao update_from_repos không verify SBOM/signature?
   → Skill chỉ cherry-pick files, không verify cosign/SBOM

5. Vì sao supply chain gate chưa implement?
   → **NGUYÊN NHÂN GỐC**: Supply chain security được coi là "optional" cho internal skills. Cần mandatory: SBOM + signature + provenance verification trước khi vendor.
```

**Classification**: **STRUCTURAL** — cần supply chain gate.

**Risk Matrix**: Impact=High (upstream compromise), Likelihood=Low (trusted upstream) → **High**

**Definition of Done**:
- [ ] update_from_repos skill: add cosign verify + SBOM check before vendor
- [ ] REPOS.md: add provenance field (sig, sbom, commit hash)
- [ ] Re-attack ATT-005: tampered vendor → blocked
- [ ] No regression on legitimate updates

---

### RC-006: Drift Detection Not in Hook Chain (ATT-006) — **MECHANICAL**

```
1. Vì sao drift_detect.py không chạy tự động?
   → Hook chain không include drift_detect

2. Vì sao hook chain không include?
   → Drift detection được coi là "optional monitoring", không governance

3. Vì sao coi là optional?
   → Model behavior drift chậm, không immediate risk như secret leak

4. Vì sao không có continuous drift monitoring?
   → **NGUYÊN NHÂN GỐC**: Thiếu drift detection gate trong governance model. Drift = silent degradation, cần continuous monitoring hook.
```

**Classification**: **MECHANICAL** — cần hook integration.

**Risk Matrix**: Impact=Medium (silent degradation), Likelihood=Medium (model updates) → **High**

**Definition of Done**:
- [ ] Add drift_detect.py to post_tool_use hook chain
- [ ] Drift alert → context_flags + session_state
- [ ] Re-attack ATT-006: simulate model drift → detected
- [ ] No regression on normal operations

---

### RC-007: Tool Permissions Not Task-Scoped (ATT-007) — **STRUCTURAL**

```
1. Vì sao task có quyền write khi chỉ cần read?
   → Tool registry global, plan_enforce chỉ check plan existence

2. Vì sao plan_enforce không check least-privilege?
   → Plan enforce chỉ verify plan approved, không verify tool scope

3. Vì sao tool permissions không scoped per-task?
   → Tool registry thiết kế cho simplicity: 7 tools global

4. Vì sao simplicity ưu tiên hơn least-privilege?
   → Harness thiết kế cho "model yếu + context nhỏ", tool ít = ít context

5. Vì sao không có task-scoped permission model?
   → **NGUYÊN NHÂN GỐC**: Permission model = global tool registry. Cần task-scoped permissions: task declares required tools, plan_enforce validates subset.
```

**Classification**: **STRUCTURAL** — cần task-scoped permission model.

**Risk Matrix**: Impact=High (over-privilege), Likelihood=High (every task) → **High**

**Definition of Done**:
- [ ] Task spec adds `required_tools: []` field
- [ ] plan_enforce validates task tools ⊆ approved tools
- [ ] Tool registry supports task-scoped permissions
- [ ] Re-attack ATT-007: task requests write, only read approved → blocked
- [ ] No regression on existing tasks

---

## Summary

| Root Cause | Type | Severity | DoD Status |
|------------|------|----------|------------|
| RC-001: No revocation infrastructure | STRUCTURAL | Critical | ⬜ Not started |
| RC-002: Dep pins not enforced | MECHANICAL | Critical | ⬜ Not started |
| RC-003: Skill trigger validation | STRUCTURAL | High | ⬜ Not started |
| RC-004: Memory write gate | MECHANICAL | High | ⬜ Not started |
| RC-005: Supply chain provenance | STRUCTURAL | High | ⬜ Not started |
| RC-006: Drift detection hook | MECHANICAL | High | ⬜ Not started |
| RC-007: Task-scoped permissions | STRUCTURAL | High | ⬜ Not started |

**Trend**: 2 Critical, 5 High — all from this iteration (no previous baseline).

---

## Next Phase

→ Research solutions per root cause → Solution Matrix → Plan