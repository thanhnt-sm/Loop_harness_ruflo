# SECURITY REMEDIATION IMPLEMENTATION PLAN
**Version**: 1.0  
**Date**: 2026-08-14  
**Target**: Agent Harness Deploy (AHD) — Zero Critical Vulnerabilities

---

## PHASE 1: CRITICAL FIXES (Week 1-2) — BLOCKING RELEASE

### Task 1.1: Fix Session Confusion in Plan Enforcement
**CVE**: CVE-2026-AHD-001  
**Files**: `.devin/hooks/plan_enforce.py`  
**Owner**: Security Engineer  

**Changes**:
```python
# REMOVE fallback to newest session state file
# STRICT session_id binding — reject if missing or state file not found
# ADD session ownership verification (PID + start_time + nonce)
```

**Implementation**:
1. Modify `_get_session_state()` to require valid `session_id` and existing state file
2. Add session metadata verification: `session_id`, `pid`, `start_time`, `nonce` in state
3. On hook entry, verify current process matches session metadata
4. Fail closed (exit 2) on any mismatch

**Tests**:
- Parallel sessions with same task_slug → attacker blocked
- Session state file deletion → new session starts fresh (no inheritance)
- Malformed session_id → blocked

---

### Task 1.2: State Router Schema Validation
**CVE**: CVE-2026-AHD-002  
**Files**: `.devin/scripts/state_router.py`, new `.devin/scripts/state_schema.py`  
**Owner**: Platform Engineer  

**Changes**:
```python
# ADD Pydantic model for StateSchema
# REJECT unknown fields (fail-closed)
# VALIDATE state on every route() call
```

**Implementation**:
1. Create `StateSchema` Pydantic model with all allowed fields + types
2. In `_normalize_state()`: parse with `StateSchema.model_validate()` 
3. Reject extra fields: `model_config = ConfigDict(extra='forbid')`
4. Add HMAC signature verification for state transitions

**Tests**:
- Inject `approved: true` → rejected
- Inject unknown field `malicious: true` → rejected
- Valid state transitions → allowed
- HMAC tampering → rejected

---

### Task 1.3: Idempotency Lock Fail-Closed
**CVE**: CVE-2026-AHD-003  
**Files**: `.devin/scripts/idempotency.py`, `.devin/scripts/dag_executor.py`  
**Owner**: Platform Engineer  

**Changes**:
```python
# REMOVE fallback to filelock — make it hard dependency
# FAIL CLOSED on lock acquisition failure (raise, don't proceed)
# ADD distributed lock support (Redis) for multi-node
```

**Implementation**:
1. Add `filelock` to `pyproject.toml` dependencies (required)
2. In `register()`: if lock acquisition fails → raise `RuntimeError` (block)
3. Remove try/except that allows unlocked execution
4. Add `redis-lock` optional extra for distributed deployments

**Tests**:
- Two parallel `register()` same key → second blocks until first completes
- Lock service unavailable → both block (fail closed)
- Lock timeout → clear error, no duplicate execution

---

### Task 1.4: Checkpoint Path Traversal Fix
**CVE**: CVE-2026-AHD-004  
**Files**: `.devin/scripts/checkpoint.py`  
**Owner**: Security Engineer  

**Changes**:
```python
# REJECT '..' sequences BEFORE sanitization
# USE Path.resolve() + relative_to(root) AFTER sanitization
# CHROOT all operations to .devin/checkpoints/
```

**Implementation**:
1. In `_sanitize_workflow_id()` and `_sanitize_step_id()`:
   - Check for `..` in raw input → reject immediately
   - After sanitization: `resolved = (root / sanitized).resolve()`
   - Verify `resolved.is_relative_to(root)` → reject if not
2. Apply to all file operations: save, load, list, restore

**Tests**:
- `workflow_id: "../../../etc/passwd"` → rejected
- `step_id: "..\\..\\HLK\\config"` → rejected
- Normal IDs → work correctly
- Symlink escape attempts → blocked

---

### Task 1.5: Schema Gate Full Secret Scan
**CVE**: CVE-2026-AHD-005  
**Files**: `.devin/hooks/schema_gate.py`, integrate `HLK/security/sanitizer.js`  
**Owner**: Security Engineer  

**Changes**:
```python
# REMOVE SCAN_TRUNCATE_CHARS limit — stream scan entire output
# USE HLK sanitizer patterns as single source of truth
# ADD entropy-based detection for unknown secret formats
```

**Implementation**:
1. Create Python wrapper for HLK sanitizer (or port patterns to Python)
2. In `_gate_secret_scan()`: read output in 64KB chunks, scan each
3. Replace `SECRET_PATTERNS` with imported HLK patterns
4. Add Shannon entropy check (>4.5 bits/char + length >20 = potential secret)

**Tests**:
- Secret at position 300K in 500K output → detected
- All HLK patterns (AWS, JWT, OAuth, DB, etc.) → detected
- High-entropy unknown format → flagged for review
- Performance: <100ms for 1MB output

---

## PHASE 2: HIGH SEVERITY FIXES (Week 3-4)

### Task 2.1: Approval Gate Cryptographic Signatures
**CVE**: CVE-2026-AHD-006  
**Files**: `.devin/scripts/approval_gate.py`, `HLK/config/hlk.config.json`  
**Owner**: Security Engineer  

**Changes**:
```python
# REQUIRE Ed25519 signature from authorized reviewer
# STORE reviewer public keys in HLK config (immutable)
# AUDIT LOG all approvals to append-only telemetry
```

**Implementation**:
1. Add `reviewer_keys` to `hlk.config.json`:
   ```json
   "security_rules": {
     "reviewer_keys": ["<ed25519_pubkey_1>", "<ed25519_pubkey_2>"]
   }
   ```
2. In `cmd_approve()`: require `signature` parameter (base64 Ed25519 sig over plan_hash + reviewer + timestamp)
3. Verify signature against allowlisted keys
4. Write approval with signature to state file
5. Append to `.devin/telemetry/approvals.jsonl` (immutable)

**Tests**:
- Valid signature → approval recorded
- Invalid/forged signature → rejected
- Missing signature → rejected
- Key rotation → works

---

### Task 2.2: Encoding Bypass Detection Order Fix
**CVE**: CVE-2026-AHD-007  
**Files**: `.devin/hooks/pre_tool_use.py`  
**Owner**: Security Engineer  

**Changes**:
```python
# RUN detect_encoding_bypass() on NORMALIZED command (after decode)
# ADD shell AST parsing via shlex for metacharacter analysis
# INTEGRATE HLK sanitizer for unified detection
```

**Implementation**:
1. Move encoding detection to AFTER `normalize_command()`
2. Add `shlex.split()` analysis: detect unquoted metacharacters, nested quotes
3. Import HLK sanitizer patterns for secret detection in commands
4. Block if detection finds bypass OR shell AST shows suspicious structure

**Tests**:
- Double-encoded `rm -rf \\x2f` → blocked
- UTF-7 `+ADw-script+AD4-` → blocked
- Punycode `xn--malicious` → blocked
- Legitimate commands with escapes → allowed

---

### Task 2.3: SSRF DNS Pinning
**CVE**: CVE-2026-AHD-008  
**Files**: `.devin/hooks/pre_tool_use.py`  
**Owner**: Platform Engineer  

**Changes**:
```python
# PIN DNS resolution at hook time (resolve + store IP)
# AT EXECUTION: verify resolved IP matches pinned IP
# USE curl --resolve or equivalent
```

**Implementation**:
1. In `_check_ssrf_gate()`: resolve hostname → store `(url, resolved_ips)` in session state
2. In `post_tool_use.py` (or wrapper): before Bash execution, re-resolve and compare
3. For curl/wget: inject `--resolve <host>:<port>:<pinned_ip>` automatically
4. Cache DNS results with TTL (configurable, default 60s)

**Tests**:
- DNS rebinding attack → blocked (IP mismatch)
- Legitimate domain with stable IP → allowed
- DNS failure at execution → blocked (fail closed)
- IPv6 support → works

---

### Task 2.4: REQ ID Cross-Reference with SDD
**CVE**: CVE-2026-AHD-009  
**Files**: `.devin/scripts/plan_quality_check.py`, `.devin/scripts/plan_fsm/state_machine.py`  
**Owner**: Platform Engineer  

**Changes**:
```python
# SDD must be signed (hash) at approval
# PLAN must reference signed SDD hash
# REJECT plans with REQ IDs not in approved SDD
```

**Implementation**:
1. In `approval_gate.py` (SDD approval): compute SHA-256 of SDD, store in approval state
2. In `plan_quality_check.py` `_parse_req_ids()`: load approved SDD, extract REQ IDs from SDD
3. Cross-reference: plan REQ IDs must be subset of SDD REQ IDs
4. New D1 check: "All plan REQ IDs trace to approved SDD"

**Tests**:
- Plan with extra REQ-999 not in SDD → D1 FAIL
- Plan with subset of SDD REQs → PASS
- SDD modified after approval → hash mismatch → plan rejected

---

### Task 2.5: Coverage Matrix File Hash Verification
**CVE**: CVE-2026-AHD-010  
**Files**: `.devin/scripts/coverage_matrix.py`, `.devin/scripts/approval_gate.py`  
**Owner**: Platform Engineer  

**Changes**:
```python
# RECORD file hashes (SHA-256) at plan approval time
# VERIFY hashes match at coverage verification
# USE immutable artifact store for approved plan files
```

**Implementation**:
1. In `approval_gate.py` (plan approval): for each file in plan, compute SHA-256, store in approval state
2. In `coverage_matrix.py` `verify_matrix()`: before `_file_exists()`, check stored hash matches current file
3. If hash mismatch → status = `FAIL` with evidence "file modified since approval"
4. Store approved plan files in `.devin/artifacts/<plan_hash>/` (immutable copy)

**Tests**:
- File replaced after approval → verification FAIL
- File unchanged → verification PASS
- Symlink swap → detected (hash of target changes)
- Large files → chunked hash (performance)

---

## PHASE 3: MEDIUM + ARCHITECTURAL (Week 5-8)

### Task 3.1: HLK Sanitizer Health Check & Warning
**CVE**: CVE-2026-AHD-011  
**Files**: `HLK/security/sanitizer.js`  
**Owner**: Security Engineer  
**Effort**: 3h

**Changes**:
- Log warning (not silent) on config failure
- Add `healthCheck()` export: returns `{patternsLoaded: N, configValid: bool, errors: []}`
- Fail closed if critical patterns missing (configurable via `security_rules.failClosedOnConfigError`)

---

### Task 3.2: Vault Bridge Precedence Reversal
**CVE**: CVE-2026-AHD-012  
**Files**: `HLK/security/vault-bridge.js`  
**Owner**: Security Engineer  
**Effort**: 2h

**Changes**:
- Configurable precedence: `security_rules.secretPrecedence: "file>env" | "env>file"`
- Default to `file>env` (more secure)
- Audit log secret source on each `getSecret()` call

---

### Task 3.3: Cost Cap Append-Only Ledger
**CVE**: CVE-2026-AHD-013  
**Files**: `.devin/hooks/pre_tool_use.py`, `.devin/hooks/post_tool_use.py`, new `.devin/scripts/cost_ledger.py`  
**Owner**: Platform Engineer  
**Effort**: 8h

**Changes**:
- New `cost_ledger.py`: append-only JSONL with HMAC-signed entries
- Each entry: `{session_id, tool, cost, cumulative, timestamp, hmac}`
- HMAC key stored in HLK vault (not in repo)
- `pre_tool_use` reads from ledger (not session state)
- `post_tool_use` appends to ledger
- Global cost tracker per org/repo (aggregates across sessions)

---

### Task 3.4: Reflection Gate Structured Output
**CVE**: CVE-2026-AHD-014  
**Files**: `.devin/hooks/pre_tool_use.py`, `.devin/scripts/reflection_gate.py`  
**Owner**: Platform Engineer  
**Effort**: 4h

**Changes**:
- Define JSON schema for reflection verdict: `{block: bool, reason: string, human_confirm_required: bool}`
- Use structured output (OpenAI `response_format` or equivalent)
- Sanitize command input: remove potential prompt injections before LLM call
- Run reflection gate in isolated subprocess (no tool access)

---

### Task 3.5: Candidate Memory Validation
**CVE**: CVE-2026-AHD-015  
**Files**: `.devin/hooks/post_tool_use.py`  
**Owner**: Platform Engineer  
**Effort**: 3h

**Changes**:
- Allowlist of valid "correct_action" patterns
- Rate limit: max 5 candidate memories per session per hour
- Human confirmation required for promotion to long-term memory
- Log all candidate memories to telemetry for audit

---

### Task 3.6: Formal FSM Verification (TLA+)
**Architectural**  
**Files**: New `specs/plan_orchestrator.tla`, `specs/state_router.tla`  
**Owner**: Architecture Team  
**Effort**: 16h

**Changes**:
- Write TLA+ spec for Plan Orchestrator FSM (15 states, transitions)
- Write TLA+ spec for State Router conditional edges
- Model check with TLC: verify no deadlocks, no livelocks, safety properties
- Generate Python code from spec (or add runtime assertions from spec)

**Properties to Verify**:
- `Safety`: Never reach EXECUTE without approved plan
- `Liveness`: Every INIT eventually reaches DONE or ESCALATE
- `Convergence`: Revision/QC/Enhance loops eventually terminate

---

### Task 3.7: Supply Chain Integrity (SBOM + Cosign)
**Architectural**  
**Files**: `package.json`, `pyproject.toml`, `.github/workflows/`  
**Owner**: Platform Engineer  
**Effort**: 12h

**Changes**:
- Generate SBOM (CycloneDX) for all dependencies (npm + pip)
- Sign all releases with cosign (keyless via GitHub OIDC)
- Verify signatures in CI before deploy
- Pin all dependencies with hashes (`pip install --require-hashes`, `npm ci`)
- Add `renovate.json` for automated dependency updates with PR approval

---

### Task 3.8: Prompt Template Engine
**Architectural**  
**Files**: `.devin/agents/`, `.devin/scripts/plan_fsm/missions.py`, new `.devin/scripts/prompt_template.py`  
**Owner**: Architecture Team  
**Effort**: 12h

**Changes**:
- New `prompt_template.py`: Jinja2-like engine with strict variable interpolation
- All agent prompts use templates: `{{task_description | escape}}`
- Auto-escape all user inputs (HTML, JS, shell, SQL contexts)
- Sandbox LLM calls: no tool access, restricted system prompt
- Prompt injection detection: heuristic + ML classifier on input

---

### Task 3.9: Loop Harness Hardening
**Architectural**  
**Files**: `.devin/scripts/dag_executor.py`, `.devin/scripts/state_router.py`, `.devin/scripts/loop_memory_sync.py`  
**Owner**: Platform Engineer  
**Effort**: 16h

**Changes**:
- Hard max iterations: `MAX_LOOP_ITERATIONS = 100` (configurable, default 50)
- Dead man's switch: external watchdog process monitors loop heartbeats
- Immutable state log: append-only Merkle tree (`.devin/telemetry/state_log.jsonl`)
- Namespace isolation: `loop_id` prefix on all state files
- Signed telemetry: Ed25519 sign each telemetry entry

---

## TESTING STRATEGY

### Unit Tests (Per Task)
- Each fix includes targeted unit tests
- Run in CI on every PR
- Coverage target: >90% for security-critical modules

### Integration Tests
```bash
# Full 3-phase flow with malicious inputs
python -m pytest tests/security/ -v

# Specific scenarios:
tests/security/test_plan_enforce_bypass.py
tests/security/test_state_router_injection.py
tests/security/test_idempotency_race.py
tests/security/test_checkpoint_traversal.py
tests/security/test_schema_gate_secrets.py
tests/security/test_approval_forge.py
tests/security/test_ssrf_rebinding.py
tests/security/test_reqid_injection.py
tests/security/test_coverage_toctou.py
```

### Fuzz Tests
- AFL++ on hook input parsing (JSON, command strings)
- Property-based testing on FSM transitions (Hypothesis)
- Network fuzzing on SSRF/DNS resolution

### Penetration Test (Quarterly)
- Red team exercise against full deployed system
- Focus: chaining vulnerabilities, supply chain, agent prompt injection
- Report findings → immediate patch cycle

---

## MONITORING & ALERTING

### Security Events to Alert On
| Event | Severity | Action |
|-------|----------|--------|
| Plan enforcement block | INFO | Log only |
| Plan enforcement bypass attempt | CRITICAL | Page on-call |
| State router malformed input | HIGH | Alert + block session |
| Idempotency lock failure | HIGH | Alert + investigate |
| Checkpoint path traversal attempt | CRITICAL | Page on-call |
| Secret detected in output | HIGH | Alert + quarantine session |
| Forged approval attempt | CRITICAL | Page on-call |
| SSRF block | HIGH | Alert |
| REQ ID injection detected | HIGH | Alert |
| Coverage hash mismatch | HIGH | Alert + block deploy |
| Loop iteration limit reached | HIGH | Alert + pause loop |

### Dashboards
- Security events timeline (Grafana)
- Hook latency percentiles
- Cost cap utilization
- Loop convergence metrics
- Approval gate audit trail

---

## ROLLBACK PLAN

If any fix causes regression:
1. Feature flag each fix: `AHD_SECURITY_FIX_<CVE_ID>=1|0`
2. Canary deploy to 5% of sessions
3. Monitor error rates, latency, false positives
4. Rollback: set flag to 0, redeploy (≤5 min)
5. Post-mortem within 24h

---

## SIGN-OFF

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Security Lead | | | |
| Platform Lead | | | |
| Architecture Lead | | | |
| Engineering Director | | | |

---
*This plan is a living document. Update as vulnerabilities are discovered and fixes validated.*