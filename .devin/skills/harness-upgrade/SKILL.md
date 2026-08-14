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
argument-hint: "[<focus-area> | <repo-id> | full | --red-team]"
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
5. **Không destructive**; HLK/.env không đụng.

> ⚠️ **Nếu model yếu / context < 50K**: chỉ giữ 5 rule trên, **1 upgrade 1 lần**, dùng few-shot
> 2-3 mẫu, làm xong Phase 1 → báo → mới sang Phase 2 (xem `detail/adaptation.md`).

## Cách gọi
```
/harness-upgrade                      # MẶC ĐỊNH: FULL pipeline (dry-run trước → apply sau)
/harness-upgrade --check              # Chỉ dry-run: review + đo + đề xuất, KHÔNG apply
/harness-upgrade --apply              # Chỉ apply (dùng plan lần --check trước)
/harness-upgrade <focus-area>         # FULL, giới hạn 1 vùng (canon|skills|scripts|hooks|context|repos)
/harness-upgrade <repo-id>            # FULL, học 1 repo trong REPOS.md
/harness-upgrade --red-team           # Chế độ triệt để: red-team + root-cause remediation
```

## Flow tổng quan (full pipeline)
```
PREFLIGHT (scripts song song) → REVIEW (đo token/context) → LEARN (repos+web)
  → [apply] UPGRADE từng candidate → VERIFY (token-delta + regression)
  → REPORT → HARNESS_UPGRADE_REPORT.md
```
- Mọi upgrade **M+** đi qua `/full-power` (Plan→Approve→Execute). **S-tier** (1 file, <5 dòng) sửa trực tiếp.
- Max parallel subagents (SCOUT/ARCHITECT/personas/VERIFIER) theo Commander mode.

## Load chi tiết theo nhu cầu (2-phase — U-H7)
| Khi cần | Đọc file |
|---------|----------|
| Model yếu / context nhỏ → cách tối giản | `detail/adaptation.md` |
| Muốn đạt chất lượng top-tier → compensation | `detail/compensation.md` |
| Token-efficiency playbook (giảm token) | `detail/compensation.md` (phần A-D) |
| REVIEW chi tiết + đo token + slop scan | `detail/review.md` |
| LEARN: nguồn học 2026 + websearch + upstream check | `detail/learn.md` |
| Red-team + root cause remediation (--red-team) | `detail/redteam.md` |
| Upgrade template library (U-H1..U-H16) | `detail/upgrade.md` |
| VERIFY + token-delta + REPORT format | `detail/verify.md` |

## Guardrails (top 5, cho model yếu)
1. Smallest coherent diff; preserve user changes.
2. No destructive ops (hooks chặn rm -rf / force-push / drop).
3. Token savings KHÔNG làm giảm correctness/safety.
4. Mọi output quan trọng phải có deterministic gate — cấm model yếu tự verify chính nó.
5. Harness là thước đo sức mạnh, không phải model — model yếu output kém → bổ sung compensation layer, không đổ lỗi model.

## Mode map
| Invocation | dry-run | apply |
|------------|:---:|:---:|
| *(mặc định)* / `full` | ✅ | ✅ |
| `--check` | ✅ | ❌ |
| `--apply` | ❌ (dùng plan cũ) | ✅ |
| `--red-team` | GĐ0-3 | GĐ4-6 |
| model yếu / context<50K | **tối giản 5 rule** (detail/adaptation.md) | tối giản |

TASK: <task sẽ được inject khi gọi skill>