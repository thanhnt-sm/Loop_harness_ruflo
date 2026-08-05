# RED TEAM COUNCIL REPORT v2 — Loop Harness toàn diện

> **Ngày**: 2026-08-05
> **Hội đồng**: 6 chuyên gia (Security, Performance, Architecture, Quality, Flow, Nuwa)
> **Phương pháp**: Adversarial analysis + online research + codebase exploration
> **Mục tiêu**: Tìm điểm nâng cấp, tối ưu token, đối chiếu Devin.ai, đảm bảo thực thi lâu dài

---

## TÓM TẮT CHO NGƯỜI DÙNG (EASY TO UNDERSTAND)

### Chuyện gì đang xảy ra
Hệ thống loop-harness (bộ khung tự động hóa cho AI agent) đã hoàn thành 50/50 nâng cấp 
từ phase trước. Tuy nhiên, hội đồng chuyên gia đã kiểm tra kỹ và phát hiện hệ thống vẫn 
còn nhiều điểm yếu, đặc biệt là:

1. **Lỗ hổng bảo mật**: Có cách bypass (vượt qua) bộ lọc an toàn bằng mã hóa hex/unicode
2. **Chỉ "nói" không "làm"**: Nhiều quy tắc được viết ra nhưng không được thực thi tự động
3. **Phí token**: Hệ thống nạp quá nhiều nội dung (50,000+ tokens) mỗi phiên làm việc
4. **Chưa dùng hết Devin**: Hệ thống chưa tận dụng nhiều tính năng mạnh của Devin CLI

### Đã làm gì
Hội đồng đã nghiên cứu toàn bộ tài liệu Devin.ai chính thức, khám phá toàn bộ codebase, 
và tấn công hệ thống từ 6 góc độ chuyên gia khác nhau.

### Kết quả
- **3 vấn đề CRITICAL** (nghiêm trọng): encoding bypass, verification không thực thi, BOOT không thực thi
- **8 vấn đề HIGH** (cao): fail-open timeout, permission rộng, token overhead, component nhiều, slop/comment checker thủ công, loop không thực thi, không antifragile
- **14 vấn đề MEDIUM** (trung bình): sanitizer thiếu pattern, race condition, I/O thừa, config rải rác, coupling, fable-judge thủ công, skill không tự động, state write không verify, memory không verify, Commander không thực thi, cascading failure, minimal mode chưa test, honest limit chưa define
- **6 vấn đề LOW** (thấp): MCP startup, single point of failure, complexity vs capability

### Giờ cần gì
Cần thực thi Upgrade Plan v2 (U51-U70) — 20 nâng cấp mới, chia 4 phase:
- **P4 CRITICAL** (U51-U55): Sửa 3 critical + 2 high security
- **P5 ENFORCEMENT** (U56-U62): Biến documentation → mechanical enforcement
- **P6 OPTIMIZATION** (U63-U67): Tối ưu token + performance
- **P7 DEVIN COMPAT** (U68-U70): Tương thích hoàn toàn Devin CLI

---

## PHẦN 1: ĐỐI CHIẾU DEVIN.AI VS LOOP HARNESS

### 1.1 Bảng đối chiếu tính năng

| Devin CLI Feature | Harness có? | Trạng thái | Gap |
|-------------------|-------------|-----------|-----|
| **Adaptive Model Router** | ❌ | Không | U68: Thêm adaptive routing |
| **Smart Permission Mode** | ❌ | Không | U69: Smart mode integration |
| **Hook: SessionStart** | ❌ | Không | U56: BOOT enforcement hook |
| **Hook: SessionEnd** | ❌ | Không | U57: Session lifecycle hook |
| **Hook: UserPromptSubmit** | ❌ | Không | U58: Prompt injection hook |
| **Hook: PostCompaction** | ❌ | Không | U63: Compaction tracking |
| **Hook: PermissionRequest** | ❌ | Không | U69: Permission decision hook |
| **Hook type: prompt** (LLM eval) | ❌ | Không | U70: LLM prompt hooks |
| **Skill triggers: [user, model]** | ✅ | Có | OK — đã cấu hình đúng |
| **Skill: model override** | ❌ | Không | U68: Model pin per skill |
| **Skill: subagent: true** | ❌ | Không | U70: Skill-as-subagent |
| **Skill: permissions override** | ❌ | Không | U70: Skill permissions |
| **Subagent: max-nesting** | ❌ | Không | U70: Nesting control |
| **Subagent: model pinning** | ✅ | Có | OK — lightning-executor, glm-executor |
| **MCP: dedicated config file** | ✅ | Có | OK — mcp_config.json |
| **MCP: HTTP transport** | ❌ | Không | spark/deepwiki/devin dùng plugin |
| **MCP: prompts as slash commands** | ❌ | Không | U70: MCP prompts |
| **MCP: disabledTools per server** | ❌ | Không | U69: Tool disable |
| **Plugin system** | ✅ | Có | OK — yellow-devin, spark-mcp |
| **Plugin governance** | ❌ | Không | U69: Required/forbidden plugins |
| **Permission: Smart mode** | ❌ | Không | U69: Smart mode |
| **Permission: Autonomous mode** | ❌ | Không | U69: Sandbox mode |
| **Config: read_config_from** | ❌ | Không | U70: Cross-tool import |
| **Rules: AGENTS.local.md** | ❌ | Không | U70: Personal rules |
| **Free models: GLM-5.2** | ✅ | Có | OK — glm-executor |
| **Free models: SWE-1.7** | ✅ | Có | OK — lightning-executor |
| **Free models: Kimi K2.7** | ❌ | Không | U68: Kimi executor |
| **Adaptive default model** | ❌ | Không | U68: Adaptive routing |

### 1.2 Đánh giá tương thích

**Tương thích: 12/27 tính năng (44%)**

**Đã tận dụng tốt:**
- GLM-5.2 free tier (glm-executor)
- SWE-1.7 Lightning (lightning-executor)
- Subagent model pinning
- MCP stdio (aide-memory)
- Plugin system (yellow-devin, spark-mcp)
- Skill triggers [user, model]
- Hook system (PreToolUse, PostToolUse, Stop)

**Chưa tận dụng (15 gaps):**
- Adaptive Model Router — Devin mặc định, harness không dùng
- Smart Permission Mode — AI đánh giá safety, harness không có
- SessionStart/SessionEnd/UserPromptSubmit/PostCompaction hooks — 4 hook events chưa dùng
- Hook type: prompt (LLM evaluation) — chưa dùng
- Skill model override — chưa dùng
- Skill subagent mode — chưa dùng
- Skill permissions override — chưa dùng
- Subagent max-nesting — chưa dùng
- MCP prompts as slash commands — chưa dùng
- MCP disabledTools — chưa dùng
- Plugin governance — chưa dùng
- Autonomous/sandbox mode — chưa dùng
- read_config_from (cross-tool import) — chưa dùng
- AGENTS.local.md — chưa dùng
- Kimi K2.7 free model — chưa dùng

---

## PHẦN 2: PHÂN TÍCH TOKEN CONSUMPTION

### 2.1 Always-on context breakdown

| Component | Size (bytes) | Tokens (~) | % of total |
|-----------|-------------|------------|------------|
| AGENTS.md (root) | 27,451 | 6,863 | 13.5% |
| CLAUDE.md (root) | 2,050 | 512 | 1.0% |
| .devin/AGENTS.md | 5,588 | 1,397 | 2.7% |
| **Canon files (15)** | **188,141** | **47,035** | **92.7%** |
| **Config files (5)** | **14,937** | **3,734** | **7.3%** |
| **Total always-on** | **203,078** | **50,770** | **100%** |

### 2.2 Top 5 canon files tiêu token nhất

| File | Tokens | Cần luôn-load? |
|------|--------|----------------|
| VERIFICATION_PROTOCOL.md | 11,166 | ❌ On-demand |
| REDLINES.md | 6,200 | ✅ Top 5 redlines only |
| HARNESS_ENGINEERING.md | 5,078 | ❌ On-demand |
| MEMORY_PROTOCOL.md | 4,575 | ❌ On-demand |
| LOOP_PROACTIVE.md | 4,289 | ❌ On-demand (U46 merged) |

### 2.3 Hook execution overhead

| Hook | Tokens (code) | Overhead/call |
|------|---------------|---------------|
| ahd_session.py | 4,443 | Không nạp context |
| post_tool_use.py | 4,120 | 200-500ms + file I/O |
| pre_tool_use.py | 3,090 | 200-500ms + regex |
| stop.py | 1,142 | Session-end only |
| **Total hooks** | **12,794** | **400-1000ms/tool call** |

### 2.4 Vấn đề token chính

1. **Canon 47K tokens always-on** — gấp 3x target 16KB (~4K tokens)
2. **AGENTS.md 6.8K tokens** — root AGENTS.md quá lớn (27KB)
3. **VERIFICATION_PROTOCOL 11K tokens** — lớn nhất, chỉ cần on-demand
4. **Double-read context_flags** — post_tool_use đọc 2 lần mỗi call
5. **Prompt hook LLM call** — mỗi PreToolUse tốn 50-100 tokens cho LLM eval
6. **Skills 116K tokens total** — nhưng on-demand nên OK

### 2.5 Ước lượng tiết kiệm nếu tối ưu

| Tối ưu | Tiết kiệm tokens | % giảm |
|--------|-----------------|--------|
| Canon lazy-load enforcement | -35,000 | -69% |
| AGENTS.md trim | -3,000 | -5.9% |
| Remove double-read | -50/call | -0.1%/call |
| Remove prompt hook (L0/L1) | -100/call | -0.2%/call |
| **Total** | **-38,150** | **-75%** |

---

## PHẦN 3: RED TEAM FINDINGS (6 CHUYÊN GIA)

### 3.1 Security Red Teamer

| # | Severity | Issue | File | Fix |
|---|----------|-------|------|-----|
| S1 | **CRITICAL** | Encoding bypass (hex/octal/unicode/variable) | pre_tool_use.py:52-82 | U51: normalize_command v2 |
| S2 | **HIGH** | Fail-open timeout (attacker craft slow command) | pre_tool_use.py:283-302 | U52: fail-closed default |
| S3 | **HIGH** | Broad permission wildcards (scripts/*) | config.json:10-30 | U53: explicit allowlist |
| S4 | **MEDIUM** | Sanitizer missing Twilio/SendGrid/Datadog | sanitizer.js:26-49 | U54: expand patterns |
| S5 | **MEDIUM** | Race condition in hook chain | config.json:108-127 | U55: stop_on_error |
| S6 | PASS | Fail-closed mode available | pre_tool_use.py:235 | OK |

### 3.2 Performance Engineer

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| P1 | **HIGH** | Always-on 50K tokens (target 16K) | U63: canon lazy-load enforcement |
| P2 | **MEDIUM** | Hook overhead 400-1000ms/call | U64: combine hooks + cache |
| P3 | **MEDIUM** | Double-read context_flags | U64: in-memory cache |
| P4 | PASS | Git rev-parse cache (U47) | OK |
| P5 | **LOW** | MCP startup 500-1000ms | U38: daemon (documented) |

### 3.3 Architecture Critic

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| A1 | **HIGH** | 60+ files, should be 20-30 | U65: merge files |
| A2 | **MEDIUM** | 8 config files (config sprawl) | U65: consolidate config |
| A3 | **MEDIUM** | Tight coupling (hooks→ahd_session→scripts) | U66: interface definitions |
| A4 | **LOW** | Single points of failure | U67: circuit breakers |
| A5 | PASS | Via negativa (U26) simplified loops | OK |

### 3.4 Quality Auditor

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| Q1 | **CRITICAL** | Verification protocol not enforced | U56: verification hook |
| Q2 | **HIGH** | Slop detector manual only | U57: auto-invoke on Write/Edit |
| Q3 | **HIGH** | Comment checker manual only | U57: auto-invoke on Write/Edit |
| Q4 | **MEDIUM** | Fable-judge not automatic on "done" | U58: done-detection hook |
| Q5 | **MEDIUM** | Skills documented but not invoked | U59: skill auto-router |
| Q6 | PASS | Risk contract exists | OK |

### 3.5 Flow Analyst

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| F1 | **CRITICAL** | BOOT protocol not enforced | U60: SessionStart hook |
| F2 | **HIGH** | Loop protocol not enforced | U61: loop enforcement hook |
| F3 | **MEDIUM** | Session state write not verified | U62: write verification |
| F4 | **MEDIUM** | Memory recall not verified | U62: memory confidence |
| F5 | **LOW** | Commander pattern not enforced | U59: dispatch detection |
| F6 | PASS | Loop memory sync exists | OK |

### 3.6 Nuwa Cognitive Reviewer

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| N1 | **HIGH** | Robust, not antifragile | U67: failure-driven learning |
| N2 | **MEDIUM** | Cascading failure modes | U67: isolation boundaries |
| N3 | **MEDIUM** | Minimal mode (U40) not tested | U67: failure injection tests |
| N4 | **LOW** | Honest limit not defined | U62: threshold definition |
| N5 | **LOW** | Complexity vs capability | U65: production profile |

---

## PHẦN 4: UPGRADE PLAN v2 (U51-U70)

### Tổng quan

| Phase | Upgrades | Ưu tiên | Effort |
|-------|----------|---------|--------|
| **P4 CRITICAL** | U51-U55 | SecurityCritical | 5 ngày |
| **P5 ENFORCEMENT** | U56-U62 | Quality+Flow | 7 ngày |
| **P6 OPTIMIZATION** | U63-U67 | Perf+Arch | 5 ngày |
| **P7 DEVIN COMPAT** | U68-U70 | Devin alignment | 3 ngày |
| **Total** | **20** | | **20 ngày** |

### P4 — CRITICAL SECURITY (U51-U55)

#### U51: Encoding bypass fix (normalize_command v2)
- **Expert**: Security Red Teamer
- **Severity**: CRITICAL (S1)
- **Problem**: hex/octal/unicode/variable expansion bypass
- **Fix**: 
  - Add `\xNN` hex decode, `\NNN` octal decode
  - Add `\uNNNN` unicode decode
  - Add `$VAR` and `${VAR}` expansion simulation
  - Broader base64 detection (all shell variants)
- **AC**: 
  1. `\x72\x6d\x20\x2d\x72\x66` → detected as `rm -rf`
  2. `$CMD` where CMD="rm -rf" → flagged
  3. `base64 -d|sh` → detected
- **Files**: pre_tool_use.py
- **Token impact**: +200 tokens (regex patterns)

#### U52: Fail-closed default (timeout)
- **Expert**: Security Red Teamer
- **Severity**: HIGH (S2)
- **Problem**: Timeout fails open (allows tool call)
- **Fix**:
  - Default: fail-closed (exit 2 on timeout)
  - `AHD_FAIL_OPEN=1` for opt-in fail-open
  - Add slow-pattern deny list
- **AC**:
  1. Timeout → exit 2 (blocked) by default
  2. `AHD_FAIL_OPEN=1` → exit 0 (allowed)
  3. Slow regex patterns denied
- **Files**: pre_tool_use.py
- **Token impact**: +50 tokens

#### U53: Narrow permission wildcards
- **Expert**: Security Red Teamer
- **Severity**: HIGH (S3)
- **Problem**: `Exec(python scripts/*)` allows any script
- **Fix**:
  - Replace `scripts/*` with explicit script names
  - Add SHA-256 allowlist for scripts
  - Move script execution to L3 (ask)
- **AC**:
  1. `python scripts/evil.py` → blocked (not in allowlist)
  2. `python scripts/verify.py` → allowed (in allowlist)
  3. Unknown script → ask
- **Files**: config.json
- **Token impact**: +100 tokens

#### U54: Expand sanitizer patterns (round 2)
- **Expert**: Security Red Teamer
- **Severity**: MEDIUM (S4)
- **Problem**: Missing Twilio, SendGrid, Datadog, Firebase, AWS session
- **Fix**: Add 5 new patterns
- **AC**: 5 new secret types detected
- **Files**: sanitizer.js, hlk.config.json
- **Token impact**: +150 tokens

#### U55: Hook chain atomicity
- **Expert**: Security Red Teamer
- **Severity**: MEDIUM (S5)
- **Problem**: Hook chain partial execution
- **Fix**: Add `stop_on_error` to hook config
- **AC**: If HLK hook fails, remaining hooks don't run
- **Files**: config.json
- **Token impact**: +30 tokens

### P5 — MECHANICAL ENFORCEMENT (U56-U62)

#### U56: SessionStart hook — BOOT enforcement
- **Expert**: Flow Analyst
- **Severity**: CRITICAL (F1)
- **Problem**: BOOT protocol not enforced
- **Fix**:
  - New hook: `.devin/hooks/session_start.py`
  - Verify BOOT steps completed
  - Set `boot_complete` in session_state
  - Block work tools until BOOT complete
- **AC**:
  1. Session starts → BOOT hook runs
  2. `boot_complete=false` → work tools blocked
  3. BOOT steps verified → `boot_complete=true`
- **Files**: hooks/session_start.py, config.json
- **Token impact**: +400 tokens

#### U57: PostToolUse auto-invoke slop + comment checker
- **Expert**: Quality Auditor
- **Severity**: HIGH (Q2, Q3)
- **Problem**: Quality checks manual only
- **Fix**:
  - PostToolUse on Write/Edit → auto-run slop-detector
  - PostToolUse on Write/Edit → auto-run comment_checker
  - Add slop_score + comment_score to session_state
  - Block "done" if score > threshold
- **AC**:
  1. Write tool → slop_detector runs automatically
  2. Write tool → comment_checker runs automatically
  3. High slop score → warning in session_state
- **Files**: post_tool_use.py
- **Token impact**: +700 tokens

#### U58: Done-detection hook (fable-judge auto)
- **Expert**: Quality Auditor
- **Severity**: MEDIUM (Q4)
- **Problem**: "done" claims not verified
- **Fix**:
  - PostToolUse: detect "done", "complete", "finished" in output
  - Auto-invoke fable-judge on detection
  - Block task complete until VERIFIED
- **AC**:
  1. Agent says "done" → fable-judge auto-invokes
  2. fable-judge returns VERIFIED → task complete
  3. fable-judge returns FAIL → task blocked
- **Files**: post_tool_use.py
- **Token impact**: +250 tokens

#### U59: Skill auto-router
- **Expert**: Quality Auditor + Flow Analyst
- **Severity**: MEDIUM (Q5, F5)
- **Problem**: Skills not auto-invoked
- **Fix**:
  - Add skill trigger patterns to config
  - PostToolUse: match tool output to skill triggers
  - Auto-invoke matching skills
  - Track skill usage in session_state
- **AC**:
  1. Code edit → harness-sensor auto-invokes
  2. Prose output → slop-detector auto-invokes
  3. Skill usage tracked
- **Files**: post_tool_use.py, config.json
- **Token impact**: +500 tokens

#### U60: Loop enforcement hook
- **Expert**: Flow Analyst
- **Severity**: HIGH (F2)
- **Problem**: Loop stop conditions not enforced
- **Fix**:
  - PostToolUse: check budget cap, time limit, convergence
  - Block tool if budget exceeded
  - Block tool if time limit exceeded
  - Require state write every N iterations
- **AC**:
  1. Budget exceeded → tools blocked
  2. Time limit exceeded → tools blocked
  3. State not written in N iterations → warning
- **Files**: post_tool_use.py
- **Token impact**: +350 tokens

#### U61: Session state write verification
- **Expert**: Flow Analyst
- **Severity**: MEDIUM (F3)
- **Problem**: State write not verified
- **Fix**:
  - Read-back after write
  - Write failure counter
  - Escalate if failure > threshold
- **AC**:
  1. Write → read-back verifies
  2. Write failure → counter increments
  3. Counter > 3 → escalate to human
- **Files**: ahd_session.py
- **Token impact**: +100 tokens

#### U62: Memory confidence + honest limit
- **Expert**: Flow Analyst + Nuwa
- **Severity**: MEDIUM (F4, N4)
- **Problem**: Memory not verified, honest limit undefined
- **Fix**:
  - Memory source tracking
  - Memory confidence score (0-100)
  - Honest limit thresholds (uncertainty > 30% → escalate)
  - Auto-escalation on breach
- **AC**:
  1. Memory recall includes source + confidence
  2. Uncertainty > 30% → auto-escalate
  3. Honest limit documented + enforced
- **Files**: ahd_session.py, VERIFICATION_PROTOCOL.md
- **Token impact**: +200 tokens

### P6 — OPTIMIZATION (U63-U67)

#### U63: Canon lazy-load enforcement
- **Expert**: Performance Engineer
- **Severity**: HIGH (P1)
- **Problem**: Canon 47K tokens always-on
- **Fix**:
  - Move canon to `.devin/canon-ref/` (not auto-read)
  - BOOT loads only: CORE_CANON + REDLINES top 5 + BOOT_PROTOCOL
  - Other canon loaded via explicit `read` call
  - Track loaded canon in session_state
- **AC**:
  1. BOOT payload < 16KB (~4K tokens)
  2. Canon loaded on-demand only
  3. Loaded canon tracked in session_state
- **Files**: BOOT_PROTOCOL.md, canon/*.md
- **Token impact**: -35,000 tokens (-69%)

#### U64: Hook performance optimization
- **Expert**: Performance Engineer
- **Severity**: MEDIUM (P2, P3)
- **Problem**: 400-1000ms/call, double-read
- **Fix**:
  - Cache context_flags in memory (read once)
  - Batch session_state writes (every 5th call)
  - Remove prompt hook for L0/L1 tools
  - Combine HLK + pre_tool_use into single process
- **AC**:
  1. Hook overhead < 200ms/call
  2. No double-read of context_flags
  3. L0/L1 tools skip prompt hook
- **Files**: pre_tool_use.py, post_tool_use.py
- **Token impact**: -200 tokens/call

#### U65: File consolidation (via negativa v2)
- **Expert**: Architecture Critic
- **Severity**: HIGH (A1, A2)
- **Problem**: 60+ files, 8 config files
- **Fix**:
  - Merge LOOP_TIME_BASED + LOOP_PROACTIVE into LOOP_PROTOCOL (already U46 but files remain)
  - Merge 8 config files into 2 (config.json + config.minimal.json)
  - Merge memory_config + risk_contract + tool_registry into config.json sections
  - Remove HANDOFF_LETTER (rarely used)
  - Target: 30 files total
- **AC**:
  1. File count < 35
  2. Config files = 2 (main + minimal)
  3. No broken references
- **Files**: canon/*.md, .devin/*.json
- **Token impact**: -5,000 tokens

#### U66: Interface definitions (decoupling)
- **Expert**: Architecture Critic
- **Severity**: MEDIUM (A3)
- **Problem**: Tight coupling
- **Fix**:
  - Define JSON schemas for hook I/O
  - Version interfaces (v1, v2)
  - Dependency injection for ahd_session
- **AC**:
  1. Hook I/O schema defined
  2. Interface versioned
  3. ahd_session injectable
- **Files**: .devin/schemas/*.json
- **Token impact**: +500 tokens

#### U67: Antifragility + circuit breakers
- **Expert**: Nuwa Cognitive Reviewer
- **Severity**: HIGH (N1, N2, N3)
- **Problem**: Robust but not antifragile
- **Fix**:
  - Failure mode tracking (what, when, why)
  - Adaptive timeouts (adjust based on history)
  - Circuit breakers (disable failing components)
  - Failure injection tests
  - Minimal mode auto-detection
- **AC**:
  1. Failure tracked in session_state
  2. Circuit breaker trips on 3 failures
  3. Minimal mode auto-activates on component failure
  4. Test script validates minimal mode
- **Files**: ahd_session.py, scripts/test_minimal_mode.py
- **Token impact**: +600 tokens

### P7 — DEVIN COMPATIBILITY (U68-U70)

#### U68: Adaptive model routing + Kimi executor
- **Expert**: Performance Engineer
- **Severity**: MEDIUM (Devin gap)
- **Problem**: No adaptive routing, no Kimi K2.7
- **Fix**:
  - Add `agent.model: "adaptive"` to config
  - Create kimi-executor subagent profile
  - Add model override per skill
  - Document model selection guide
- **AC**:
  1. Adaptive model in config
  2. kimi-executor/AGENT.md exists
  3. Skill model override documented
- **Files**: config.json, agents/kimi-executor/AGENT.md
- **Token impact**: +300 tokens

#### U69: Smart permission mode + plugin governance
- **Expert**: Security Red Teamer
- **Severity**: MEDIUM (Devin gap)
- **Problem**: No smart mode, no plugin governance
- **Fix**:
  - Document smart mode usage
  - Add plugin governance (required/forbidden)
  - Add MCP disabledTools config
  - Document autonomous/sandbox mode
- **AC**:
  1. Smart mode documented
  2. Plugin governance in config
  3. MCP disabledTools supported
- **Files**: config.json, AGENTS.md
- **Token impact**: +200 tokens

#### U70: Full Devin feature alignment
- **Expert**: Architecture Critic
- **Severity**: MEDIUM (Devin gap)
- **Problem**: 15 Devin features not used
- **Fix**:
  - Add SessionEnd hook
  - Add UserPromptSubmit hook (context injection)
  - Add PostCompaction hook (memory save)
  - Add hook type: prompt (LLM eval)
  - Add skill subagent mode
  - Add skill permissions override
  - Add subagent max-nesting
  - Add MCP prompts as slash commands
  - Add AGENTS.local.md support
  - Add read_config_from (cross-tool import)
- **AC**:
  1. 10+ Devin features newly supported
  2. All hooks events covered
  3. Cross-tool import enabled
- **Files**: config.json, hooks/*.py, AGENTS.md
- **Token impact**: +1,000 tokens

---

## PHẦN 5: ĐÁNH GIÁ CHẤT LƯỢNG OUTPUT

### 5.1 Hiện trạng

| Aspect | Score | Đánh giá |
|--------|-------|----------|
| **Security** | 6/10 | Có hook nhưng bypass được, fail-open |
| **Verification** | 4/10 | Documented 612 lines nhưng không enforce |
| **Token efficiency** | 3/10 | 50K always-on, gấp 3x target |
| **Component count** | 4/10 | 60+ files, quá phức tạp |
| **Skill automation** | 3/10 | 20+ skills nhưng manual only |
| **Loop enforcement** | 3/10 | Documented nhưng không enforce |
| **Devin compatibility** | 5/10 | 12/27 features (44%) |
| **Antifragility** | 4/10 | Robust nhưng không adapt |
| **Overall** | **4.0/10** | Cần nâng cấp |

### 5.2 Target sau U51-U70

| Aspect | Target | Cải thiện |
|--------|--------|-----------|
| **Security** | 9/10 | +3 (encoding fix, fail-closed, narrow perms) |
| **Verification** | 8/10 | +4 (auto-enforce, done-gate, memory verify) |
| **Token efficiency** | 8/10 | +5 (lazy-load, hook optimize, consolidate) |
| **Component count** | 7/10 | +3 (merge files, consolidate config) |
| **Skill automation** | 8/10 | +5 (auto-router, auto-invoke) |
| **Loop enforcement** | 8/10 | +5 (budget/time/convergence hooks) |
| **Devin compatibility** | 9/10 | +4 (27/27 features) |
| **Antifragility** | 7/10 | +3 (circuit breakers, failure learning) |
| **Overall** | **8.0/10** | **+4.0** |

---

## PHẦN 6: ĐẢM BẢO THỰC THI LÂU DÀI

### 6.1 Nguyên tắc thực thi

1. **Mỗi upgrade phải có AC (acceptance criteria) measurable**
2. **Mỗi upgrade phải có verification script**
3. **Mỗi upgrade phải commit + push ngay sau khi verify**
4. **Tracker JSON cập nhật sau mỗi upgrade**
5. **verify-workspace.ps1 phải pass 60/60 sau mỗi upgrade**

### 6.2 Anti-regression

- Hook integrity (U41) — SHA256 baseline phát hiện tampering
- verify-workspace.ps1 — 60 checks sau mỗi thay đổi
- health-check.ps1 — 20 checks health score
- Risk contract (U28) — critical files protected
- Log rotation (U44) — audit trail preserved

### 6.3 Thực thi qua nhiều vòng

```
Round 1: P4 (U51-U55) → verify → commit → push
Round 2: P5 (U56-U62) → verify → commit → push
Round 3: P6 (U63-U67) → verify → commit → push
Round 4: P7 (U68-U70) → verify → commit → push
Round 5: Final redteam → score 8.0/10 → done
```

### 6.4 Monitoring liên tục

- `pwsh tools/health-check.ps1` — health score mỗi session
- `python .devin/scripts/hook_integrity.py --verify` — integrity check
- `pwsh tools/verify-workspace.ps1` — workspace verification
- `python tools/cross_platform.py health-check` — cross-platform check

---

## PHẦN 7: KẾT LUẬN

### 7.1 Phát hiện quan trọng nhất

1. **"Documentation without enforcement is theater"** — 3/3 CRITICAL issues đều là 
   "documented but not enforced". Hệ thống có 612 dòng verification protocol nhưng 
   0 hooks thực thi nó.

2. **Token overhead 3x target** — 50K tokens always-on thay vì 16K. Canon files 
   (47K tokens) nên on-demand nhưng không có cơ chế enforce.

3. **Devin compatibility 44%** — 15/27 tính năng Devin chưa được tận dụng. 
   Đặc biệt Adaptive Router (mặc định Devin), Smart Mode, 4 hook events, 
   prompt-type hooks, skill model override.

4. **Free models exploited well** — GLM-5.2 + SWE-1.7 đã dùng tốt qua 
   glm-executor + lightning-executor. Thiếu Kimi K2.7.

5. **Antifragility gap** — Hệ thống robust (fallback, minimal mode) nhưng 
   không antifragile (không học từ failure, không adaptive).

### 7.2 Đề xuất ưu tiên

**Ngay lập tức (P4):**
- U51: Fix encoding bypass (CRITICAL security)
- U52: Fail-closed default (HIGH security)

**Tuần tới (P5):**
- U56: BOOT enforcement (CRITICAL flow)
- U57: Auto quality checks (HIGH quality)

**Tuần 2 (P6):**
- U63: Canon lazy-load (HIGH token savings -35K)

**Tuần 3 (P7):**
- U68-U70: Devin full compatibility

### 7.3 Score hiện tại vs target

| Metric | Hiện tại | Target U70 | 
|--------|----------|------------|
| Red team score | 4.0/10 | 8.0/10 |
| Always-on tokens | 50,770 | 12,000 |
| Hook overhead | 400-1000ms | <200ms |
| Devin compatibility | 44% | 100% |
| Security bypass vectors | 5+ | 0 |
| Enforced protocols | 0/3 | 3/3 |
| File count | 60+ | <35 |

---

**Hết báo cáo. Upgrade plan v2 sẵn sàng thực thi.**
