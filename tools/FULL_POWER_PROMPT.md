# FULL_POWER_PROMPT — One-shot trigger cho full harness chain

> **Cách dùng**: Copy toàn bộ nội dung dưới đây, dán vào Devin CLI, thay `<TASK>` bằng task của bạn.
>
> **Kết quả**: Harness tự động BOOT → inventory → decompose → dispatch parallel subagents → integrate → verify → report.

---

## Prompt (copy từ đây trở xuống)

```
[FULL_POWER_MODE]

Bạn đang chạy trong workspace có Agent Harness Deploy (AHD) làm động cơ chính. Thực hiện đầy đủ chain dưới đây — không skip, không rút gọn.

## Bước 1: BOOT
Đọc và thực hiện `.devin/canon/BOOT_PROTOCOL.md` — 3-tier lazy-load model (U04):
- **Tier S** (task <30 min): Steps 1-8 only (entry file, registry, profile, session_id, context flags, crashed check, start work)
- **Tier M** (task 30min-2h): Steps 1-12 (adds pre-task audit, GoalSpec, registry update)
- **Tier L/XL** (task 2h+): All steps 1-17 (adds deep-memory, large-repo init, gap-scan, interview-mode)
- Nếu unclear → default M. Upgrade nếu scope grows.
- Đọc `.devin/AGENTS.md` (entry file, 5KB summary — KHÔNG load AGENTS_full.md 186KB)
- Đọc `.agents/loop_state.md` (registry)
- Đọc `.agents/user_profile.md` (preferences)
- Output GoalSpec (M/L/XL only)

## Bước 2: INVENTORY
Kiểm tra khả dụng:
- Skills: `ls .devin/skills/` — ghi nhận tất cả skills khả dụng
- Agents: `ls .devin/agents/` — ghi nhận COMMANDER + personas + workers + executors
- MCP servers: đọc `.devin/mcp_config.json` — ghi nhận aide-memory + spark-memory + deepwiki + devin
- Hooks: `ls .devin/hooks/` — xác nhận pre_tool_use + post_tool_use + stop + ahd_session
- Canon: `ls .devin/canon/` — xác nhận 10 protocol files

## Bước 3: COMMANDER MODE
Vào vai **Commander** (xem `.devin/agents/COMMANDER.md`):
- Bạn là main thread — quyết định, dispatch, integrate, verify
- Bạn KHÔNG tự grep toàn repo, KHÔNG đọc 10+ files, KHÔNG batch-edit, KHÔNG verify output của chính mình
- Bạn decompose task → dispatch workers → đọc reports → integrate

## Bước 4: TASK FRAMING
Phân tích task dưới đây, output GoalSpec:
- Objective: (1 câu)
- Acceptance criteria: (checklist có thể verify)
- Constraints: (scope, style, dependencies)
- Verification needs: (cần check gì để confirm done)
- Risk level: S / M / L / XL (theo JUDGMENT_RUBRICS.md)

TASK:
<TASK>

## Bước 5: GAP SCAN
Chạy `.devin/skills/gap-scan.md` — scan 1-2 scope angles cho blind spots mà GoalSpec chưa cover.

## Bước 6: DECOMPOSE + DISPATCH
Nếu task > S-tier:
1. Chạy `python .devin/scripts/plan_dispatch.py` để analyze dependency graph + file ownership
2. Decompose thành subtasks disjoint (không overlap write sets)
3. Dispatch **parallel subagents** dùng `run_subagent`:

### Pattern dispatch (chọn theo task):

**Research-heavy task** →
- SCOUT (profile: subagent_explore, background: true) — scan codebase, map dependencies, find patterns
- Đợi SCOUT report → mới dispatch BUILDER

**Implementation task** →
- SCOUT (subagent_explore, background: true) — research cần thiết
- BUILDER (lightning-executor hoặc glm-executor, background: true) — implement sau khi SCOUT done
- AUDITOR (subagent_explore, background: true) — review diff sau khi BUILDER done

**Multi-file parallel task** →
- N×BUILDER (lightning-executor, background: true) — mỗi worker 1 file set disjoint
- 1×VERIFIER (subagent_explore, background: true) — fresh-context verify sau khi tất cả BUILDER done

**Security/quality review task** →
- AUDITOR (subagent_explore, background: true) — adversarial 8-angle audit
- SCOUT (subagent_explore, background: true) — gather evidence

### Model selection per subtask:
- Research/exploration → `subagent_explore` (cheap)
- Code changes fast → `lightning-executor` (SWE-1.7 Lightning, 1000 tok/s)
- Code changes free → `glm-executor` (GLM-5.2 High, free tier)
- High-stakes reasoning → `glm-executor` (GLM-5.2 capable tier)
- Verification → `subagent_explore` (fresh context, cheap)

### Dispatch contract (mỗi subagent phải có):
1. Goal & motivation (tại sao task này tồn tại)
2. Acceptance criteria (checklist verify được)
3. Report format (expected output structure)

## Bước 7: INTEGRATE
Đọc reports từ tất cả workers:
- SCOUT → tổng hợp findings
- BUILDER → inspect diff độc lập (treat report as evidence, not proof)
- AUDITOR → review adversarial findings
- VERIFIER → confirm acceptance criteria met

Nếu conflict → ưu tiên VERIFIER (fresh context) > AUDITOR > BUILDER.

## Bước 8: VERIFY
Theo `.devin/canon/VERIFICATION_PROTOCOL.md`:
- Maker ≠ checker — KHÔNG tự verify output của chính mình
- Chạy `python .devin/hooks/pre_tool_use.py` style checks
- Chạy build/lint/typecheck nếu có
- Nếu task liên quan code → chạy `python .devin/scripts/plan_dispatch.py` verify file ownership
- SHA discipline: ghi hash của files changed

## Bước 9: NUWA COGNITIVE VERIFICATION (optional, cho L/XL tasks)
Dùng `.devin/skills/nuwa-skill/` cho adversarial cognitive review:
- **Munger perspective** — check cho cognitive biases trong design decisions
- **Feynman perspective** — check có explain được đơn giản không
- **Taleb perspective** — check robustness against black swans, tail risks

## Bước 10: CLAIM GRADING
Chạy `.devin/skills/claim-grader.md` — grade mọi claim trong final report:
- [fact] — có file:line evidence
- [inference] — logic deduction từ facts
- [unverified-guess] — cần verify thêm

## Bước 11: SLOP CHECK
Chạy `.devin/skills/slop-detector.md` + `.devin/skills/comment_checker.md`:
- Detect AI-generated filler (delve, leverage, seamless, robust)
- Detect slop comments (restating code, over-explaining)
- Remove nếu tìm thấy

## Bước 12: MEMORY WRITE-BACK
Gọi MEMORY_KEEPER worker (hoặc tự làm nếu task nhỏ):
- `python .devin/scripts/memory_audit.py` — merge candidate memories vào knowledge_distill.md
- `python .devin/scripts/loop_memory_sync.py` — update loop_state.md registry
- Nếu có lessons reusable → store vào aide-memory: `mcp__aide-memory__aide_remember`
- Nếu task completed → append handoff letter (nếu có decisions worth recording)

## Bước 13: REPORT
Output final report theo format:
```
## GoalSpec
- Objective: ...
- Acceptance criteria: [✓/✗] each item
- Risk level: S/M/L/XL

## What changed
- Files: (list with brief description)
- Diff stat: (insertions/deletions)

## Verification
- Build: ✓/✗ (command + result)
- Lint: ✓/✗
- Tests: ✓/✗ (count pass/fail)
- Claim grades: N fact, N inference, N unverified

## Subagents dispatched
- SCOUT: (findings summary)
- BUILDER: (changes summary)
- AUDITOR: (issues found / clean)
- VERIFIER: (criteria confirmed)

## Residual risks
- (anything not fully verified)

## Next steps (optional)
- (follow-up tasks if any)
```

## Stop conditions (LUÔN áp dụng)
- Budget cap: nếu quá 15 iterations → stop, report progress
- Convergence: nếu 2 iterations liên tiếp không có progress → stop, hỏi user
- Stuck: nếu 2 resume cùng executor không tiến triển → stop, hỏi user
- Red line: nếu task violate bất kỳ rule trong REDLINES.md → stop, hỏi user

## Bắt đầu
Thực hiện Bước 1 (BOOT) ngay. Output GoalSpec trước, rồi mới decompose + dispatch.
```

---

## Cách dùng nhanh

```bash
# Option 1: Interactive
cd <project-dir>
devin
# Paste toàn bộ prompt trên + thay <TASK>

# Option 2: Non-interactive (one-liner)
devin -p -- "[FULL_POWER_MODE] ... <TASK>"

# Option 3: Copy prompt từ file
Get-Content tools/FULL_POWER_PROMPT.md | Select-String -Pattern '^\[' | ForEach-Object { $_.Line }
```

## Khi nào dùng FULL_POWER vs đơn giản?

| Task complexity | Dùng |
|----------------|------|
| S-tier (<5 lines, 1 file, no verification) | Trực tiếp, skip harness |
| M-tier (1-3 files, simple logic) | `/lightning <task>` hoặc `/glm <task>` |
| L-tier (multiple files, needs research) | FULL_POWER_PROMPT |
| XL-tier (architecture change, security-critical) | FULL_POWER_PROMPT + Nuwa cognitive verification |
