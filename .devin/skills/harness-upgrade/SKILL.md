---
name: harness-upgrade
description: >-
  Skill rà soát + nâng cấp + tự-tăng-cường workspace này thành best harness cho
  AI model kém thông minh + context nhỏ: tối đa token-efficiency, tối thiểu
  always-on context, chất lượng output cao nhất (mục tiêu: đạt tầm Opus/GPT-5/Fable).
  Launcher nhỏ gọn cho model yếu — chi tiết load-on-demand theo file detail.
  Output: HARNESS_UPGRADE_REPORT.md + applied upgrades.
triggers:
  - "nâng cấp harness"
  - "upgrade harness"
  - "tối ưu harness"
  - "cải thiện workspace"
  - "make workspace better"
  - "token optimization"
  - "giảm context"
  - "self-improve harness"
  - "best harness"
  - "harness review"
  - "rà soát workspace"
  - "phát triển workspace"
  - "harness optimizer"
  - "small context"
  - "kém thông minh"
  - "red-team"
  - "root cause"
  - "triệt để"
  - "sửa gốc"
  - "attack test"
  - "security audit harness"
  - "tăng cường workspace"
  - "đạt chất lượng top-tier"
argument-hint: "[] — MẶC ĐỊNH FULL CHAIN (không cần tham số). Tùy chọn giới hạn: <focus-area> | <repo-id> | --check | --apply | --no-red-team | --no-apply | --red-team"
permissions:
  allow:
    - Read
    - Edit
    - Glob
    - Grep
    - Bash
---

# harness-upgrade — Tự rà soát + nâng cấp workspace thành best harness

> Mục tiêu: biến workspace này thành **harness tối ưu cho AI yếu + context nhỏ** — output
> chất lượng cao nhất (tầm Opus/GPT-5/Fable) trong khi tiêu tốn tối thiểu token.

## 5 RULE TỐI THƯỢNG (đặt ở đầu — model yếu nhớ đầu, tránh lost-in-middle)
1. **Sửa đúng gốc**, không vá triệu chứng.
2. **Giảm input context là ưu tiên số 1** (bottleneck model yếu).
3. **Verify deterministic sau mỗi thay đổi** (chạy script, không tự đoán).
4. **Smallest coherent diff**; không scope creep.
5. **Không destructive**; HLK/.env không đụng (trừ khi task chính là nâng cấp HLK được chỉ định rõ).

> ⚠️ **Nếu model yếu / context < 50K**: chỉ giữ 5 rule trên, **1 upgrade 1 lần**, dùng few-shot
> 2-3 mẫu, làm xong Phase 1 → báo → mới sang Phase 2 (xem `detail/adaptation.md`).

## Cách gọi
```
/harness-upgrade                      # MẶC ĐỊNH = FULL CHAIN HOÀN CHỈNH (không cần tham số):
                                      #   PREFLIGHT → REVIEW → LEARN → UPGRADE → VERIFY → RED-TEAM →
                                      #   ROOT-CAUSE REMEDIATION → COMPENSATION → REPORT → APPLY
/harness-upgrade --check              # Chỉ dry-run: review + đo + đề xuất, KHÔNG apply (bỏ GĐ apply/red-team apply)
/harness-upgrade --apply              # Chỉ apply (dùng plan lần --check trước)
/harness-upgrade --no-red-team        # FULL nhưng BỎ phase red-team/root-cause
/harness-upgrade --no-apply           # FULL phân tích + report, KHÔNG apply (dry-run thuần)
/harness-upgrade <focus-area>         # FULL CHAIN, giới hạn phạm vi 1 vùng (canon|skills|scripts|hooks|context|repos)
/harness-upgrade <repo-id>            # FULL CHAIN, ưu tiên học 1 repo trong REPOS.md
/harness-upgrade --red-team           # FULL CHAIN + nhấn mạnh chế độ triệt để red-team (mặc định đã chạy)
```

> **Mặc định KHÔNG cần tham số.** Gọi trần `/harness-upgrade` = chạy **đầy đủ mọi thứ**: toàn bộ
> flow, toàn bộ option, toàn bộ phase, toàn bộ chi tiết. Các tham số chỉ dùng để **giới hạn/điều
> chỉnh** khi user cần, không phải để kích hoạt.

## Flow tổng quan (FULL CHAIN — chạy mọi phase, mặc định)
```
PREFLIGHT (scripts song song)
  → REVIEW (đo token/context + slop scan)
  → LEARN (repos + web research 2026)
  → UPGRADE từng candidate
  → VERIFY (token-delta + regression, deterministic gate)
  → RED-TEAM + ROOT-CAUSE REMEDIATION (Protocol v2.0, GĐ0-6)
  → V5 CONTINUOUS RED-TEAM (Protocol v5.0 — identity/delegation, MCP pack, eval transfer, human oversight, resilience)
  → COMPENSATION (frontier-quality, C1-C7)
  → REPORT → HARNESS_UPGRADE_REPORT.md
  → APPLY (M+ qua /full-power; S-tier sửa trực tiếp)
```
- **Mặc định = MAX POWER + FULL COVERAGE**: KHÔNG cắt phase nào, KHÔNG skip red-team, KHÔNG skip compensation.
- Mọi upgrade **M+** đi qua `/full-power` (Plan→Approve→Execute). **S-tier** (1 file, <5 dòng) sửa trực tiếp.
- Max parallel subagents (SCOUT/ARCHITECT/personas/VERIFIER) theo Commander mode.
- Model yếu / context <50K: vẫn chạy đủ chain nhưng tuần tự từng phase, giữ 5 rule + few-shot
  (xem `detail/adaptation.md`) — KHÔNG bỏ phase.

## Load chi tiết (FULL CHAIN = load tất cả detail files)
| Đọc file | Mục đích |
|----------|----------|
| `detail/adaptation.md` | Cách tối giản cho model yếu / context nhỏ |
| `detail/compensation.md` | Frontier-quality compensation (C1-C7) + token-efficiency playbook |
| `detail/review.md` | REVIEW chi tiết + đo token + slop scan |
| `detail/learn.md` | LEARN: nguồn học 2026 + websearch + upstream check |
| `detail/redteam.md` | RED-TEAM + root cause remediation Protocol v2.0 |
| `detail/redteam-v5.md` | V5 RED-TEAM STEP: chạy Protocol v5.0 (identity/delegation, MCP pack, eval transfer) |
| `detail/v5-redteam-prompt.md` | **LOAD-ON-DEMAND** payload v5.0 — CHỈ nạp khi bước V5 chạy, KHÔNG load chung |
| `detail/upgrade.md` | Upgrade template library (U-H1..U-H16) |
| `detail/verify.md` | VERIFY + token-delta + REPORT format |

> Mặc định đọc **TẤT CẢ** các file trên (full flow, full option). Chỉ bỏ bớt khi user gọi
> `--no-red-team` (bỏ redteam.md + redteam-v5.md) hoặc context cực nhỏ (adaptation.md hướng dẫn ưu tiên).
> ⚠️ `detail/v5-redteam-prompt.md` là payload load-on-demand — **KHÔNG** load chung ở đây; chỉ nạp
> khi bước V5 (`detail/redteam-v5.md`) thực thi.

## Guardrails (top 5, cho model yếu)
1. Smallest coherent diff; preserve user changes.
2. No destructive ops (hooks chặn rm -rf / force-push / drop).
3. Token savings KHÔNG làm giảm correctness/safety.
4. Mọi output quan trọng phải có deterministic gate — cấm model yếu tự verify chính nó.
5. Harness là thước đo sức mạnh, không phải model — model yếu output kém → bổ sung compensation layer, không đổ lỗi model.
6. HLK/ & .env không đụng (trừ khi task chính là nâng cấp HLK được chỉ định rõ — xem detail/upgrade.md quy trình HLK).

## Mode map
| Invocation | Flow đầy đủ | dry-run | apply | red-team |
|------------|:---:|:---:|:---:|:---:|
| *(mặc định)* / `full` | ✅ FULL CHAIN | ✅ | ✅ | ✅ |
| `--check` | một phần | ✅ | ❌ | chỉ GĐ0-3 |
| `--apply` | một phần | ❌ (plan cũ) | ✅ | ❌ |
| `--no-red-team` | FULL, bỏ red-team | ✅ | ✅ | ❌ |
| `--no-apply` | FULL phân tích | ✅ | ❌ | ✅ |
| `--red-team` | FULL CHAIN, nhấn triệt để | ✅ | ✅ | ✅ |
| model yếu / context<50K | FULL CHAIN tuần tự | ✅ | ✅ | ✅ (tối giản) |

> **Invocation mặc định (không tham số) = FULL CHAIN: toàn bộ flow + toàn bộ option + toàn bộ
> phase + toàn bộ detail files, gồm cả red-team/root-cause (v2.0 + v5.0) lẫn compensation/apply.**
>
> **V5 RED-TEAM** = bước chạy Protocol v5.0 (payload `detail/v5-redteam-prompt.md`) như iteration
> bounded sau v2.0 GĐ0-6; v5.0 thay thế v4.0. `--check`/`--no-apply` → `AUDIT_ONLY` (chỉ PHASE 1-16).
> `--no-red-team` → bỏ v2.0 + v5.0. Nếu thiếu Runtime Manifest (scope/environment/approver...) →
> `BLOCKED`, chỉ static analysis, không active red-team.

TASK: <task sẽ được inject khi gọi skill>