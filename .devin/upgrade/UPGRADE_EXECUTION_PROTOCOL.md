# Upgrade Execution Protocol

> **Quy tắc thực thi upgrade plan qua nhiều session, đảm bảo không drift, không thiếu, không sai.**
>
> **Mục tiêu**: 40 upgrades thực thi đúng thứ tự, đúng spec, verify được, trace được, rollback được.
> **Principle**: "Trust the tracker, verify the work, never assume state."

---

## 1. Khởi động session thực thi upgrade

### Step 1: Đọc tracker

```powershell
# Luôn đọc tracker ĐẦU TIÊN — không bao giờ giả định trạng thái
$tracker = Get-Content .devin/upgrade/UPGRADE_TRACKER.json | ConvertFrom-Json
```

### Step 2: Xác định upgrade tiếp theo

```
1. Tìm upgrade có status = "pending" với priority cao nhất (P0 > P1 > P2 > P3)
2. Check dependencies — tất cả dependencies phải có status = "done"
3. Nếu dependency chưa done → chuyển sang upgrade có dependency thỏa
4. Nếu tất cả P0 pending có dependency chưa done → báo user, không tự ý skip
```

### Step 3: Đọc spec

```
1. Mở HLK/docs/UPGRADE_PLAN.md
2. Tìm section "## UXX" (ID của upgrade tiếp theo)
3. Đọc toàn bộ spec: Problem, Solution, Files, AC, Verification
4. Không bắt đầu cho đến khi hiểu toàn bộ spec
```

### Step 4: Ghi nhận bắt đầu

```powershell
# Update tracker: status → "in_progress", started_date → today
$upgrade = $tracker.upgrades | Where-Object { $_.id -eq "UXX" }
$upgrade.status = "in_progress"
$upgrade.started_date = Get-Date -Format "yyyy-MM-dd"
$tracker | ConvertTo-Json -Depth 10 | Set-Content .devin/upgrade/UPGRADE_TRACKER.json
```

---

## 2. Thực thi upgrade

### Quy tắc 1: Một upgrade per commit

- **KHÔNG** gộp nhiều upgrade trong 1 commit
- Commit format: `fix(upgrade): UXX <title> [P0|P1|P2|P3]`
- Commit message body: tóm tắt thay đổi, reference REDTEAM_REPORT finding

### Quy tắc 2: Theo spec đúng

- Tạo/sửa file ĐÚNG như spec mô tả
- Nếu spec cần thay đổi → tạo UPR (Upgrade Proposal Review):
  ```
  # UPR-UXX-YYYYMMDD
  ## Lý do thay đổi spec
  ## Spec cũ
  ## Spec mới
  ## Impact
  ```
  Lưu UPR trong `.devin/upgrade/UPRs/` và update tracker notes

### Quy tắc 3: Không skip acceptance criteria

- Mỗi AC phải check ✓
- Nếu AC không pass → KHÔNG mark done → fix cho đến khi pass
- Nếu AC không thể pass (external dependency) → mark "blocked" với lý do

### Quy tắc 4: Chạy verification steps

- Verification steps trong spec phải được chạy
- Output verification phải được ghi vào tracker notes
- Không chỉ "looks done" — phải "verified done"

### Quy tắc 5: Preserve existing functionality

- Chạy `verify-workspace.ps1` trước và sau upgrade
- Nếu verify-workspace fail sau upgrade → upgrade broke something → fix hoặc rollback
- Không break existing tests/hooks/scripts

---

## 3. Hoàn tất upgrade

### Step 1: Chạy verification

```powershell
# Chạy tất cả verification steps trong spec
# Ghi output vào notes
```

### Step 2: Update tracker

```powershell
$upgrade = $tracker.upgrades | Where-Object { $_.id -eq "UXX" }
$upgrade.status = "done"
$upgrade.completed_date = Get-Date -Format "yyyy-MM-dd"
$upgrade.verifier = "<agent/model name>"
$upgrade.commit_hash = "<git commit hash>"
$upgrade.notes = "<verification output summary>"

# Update phase_summary
$phase = $upgrade.phase
$tracker.phase_summary.$phase.done++
$tracker.phase_summary.$phase.pending--
$tracker.phase_summary.$phase.in_progress = 0

# Update metrics_current (nếu upgrade affects metrics)
# Ví dụ U01: always_on_context_tokens giảm từ 53225 → ~12000

$tracker | ConvertTo-Json -Depth 10 | Set-Content .devin/upgrade/UPGRADE_TRACKER.json
```

### Step 3: Commit

```powershell
git add -A
git commit -m "fix(upgrade): UXX <title> [P0]

<brief description of changes>

Verification: <AC count>/<AC count> passed
Tracker: .devin/upgrade/UPGRADE_TRACKER.json updated

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"
```

### Step 4: Check dependents

```
1. Đọc tracker → tìm upgrades có dependency = UXX vừa done
2. Nếu dependent có tất cả dependencies done → unblock (status pending → pending, có thể thực thi)
3. Nếu dependent vẫn có dependency chưa done → giữ pending
```

### Step 5: Update metrics_current

Sau mỗi phase hoàn tất (P0, P1, P2, P3), update `metrics_current` trong tracker:

```powershell
$tracker.metrics_current.date = Get-Date -Format "yyyy-MM-dd"
# Update các metrics affected by phase
# Ví dụ sau P0:
$tracker.metrics_current.always_on_context_tokens = 12000
$tracker.metrics_current.always_on_context_pct = 6.0
$tracker.metrics_current.security_critical_vulns = 0
$tracker.metrics_current.boot_cold_start_s = "1-2"
$tracker.metrics_current.disaster_recovery = $true
$tracker.metrics_current.rollback_deploy = $true
$tracker.metrics_current.human_in_loop_count = 6
```

---

## 4. Drift prevention mechanisms

### Mechanism 1: Tracker là source of truth

- **Không bao giờ** giả định upgrade đã done dựa trên memory/context
- **Luôn** đọc tracker để xác định trạng thái
- **Nếu** tracker nói "pending" nhưng bạn nhớ đã làm → trust tracker, verify lại

### Mechanism 2: Acceptance criteria checklist

- Mỗi upgrade có AC count trong tracker
- Khi mark done, ghi rõ: "AC: X/Y passed"
- Nếu X < Y → không mark done

### Mechanism 3: Verification output recorded

- Verification steps output phải được ghi vào tracker notes
- Không chỉ "passed" — ghi actual output (e.g., "AGENTS.md = 5.2KB, 10 canon refs found")
- Future sessions có thể verify lại bằng cách re-run verification steps

### Mechanism 4: Commit hash tracing

- Mỗi upgrade commit hash ghi vào tracker
- Future sessions có thể `git show <hash>` để xem chính xác gì đã làm
- Nếu upgrade bị revert/modify sau này, hash vẫn trace được

### Mechanism 5: Phase gate review

- Sau khi hoàn tất tất cả P0 → phase gate review trước khi sang P1
- Review: chạy `verify-workspace.ps1`, check tất cả P0 ACs, update metrics_current
- Nếu bất kỳ P0 upgrade chưa pass AC → không sang P1

### Mechanism 6: UPR cho spec changes

- Nếu cần thay đổi spec khi đang thực thi → tạo UPR
- UPR lưu trong `.devin/upgrade/UPRs/UPR-UXX-YYYYMMDD.md`
- Tracker notes reference UPR
- Không silently thay đổi spec

---

## 5. Rollback nếu upgrade breaks

### Khi nào rollback

- `verify-workspace.ps1` fail sau upgrade
- Existing hooks/scripts break
- New regression introduced

### Cách rollback

```powershell
# 1. Revert commit
git revert <commit_hash>

# 2. Update tracker
$upgrade = $tracker.upgrades | Where-Object { $_.id -eq "UXX" }
$upgrade.status = "rolled_back"
$upgrade.notes = "Rolled back: <reason>. Commit <hash> reverted."

# 3. Commit rollback
git commit -m "revert(upgrade): UXX rolled back — <reason>

Reverts <commit_hash>
Tracker updated: status → rolled_back

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"
```

### Sau rollback

- Upgrade status = "rolled_back" (không phải "pending" — cần review trước khi retry)
- Tạo UPR để fix spec nếu cần
- Re-run sau khi fix spec

---

## 6. Multi-session continuity

### Session N bắt đầu

```
1. git pull (nếu remote có updates)
2. Đọc UPGRADE_TRACKER.json
3. Tìm upgrade tiếp theo (như Step 2 ở trên)
4. Đọc spec trong UPGRADE_PLAN.md
5. Bắt đầu thực thi
```

### Session N kết thúc

```
1. Nếu upgrade đang in_progress → ghi notes về progress hiện tại
2. Commit tracker (nếu có thay đổi)
3. Push (nếu user yêu cầu)
4. Ghi handoff letter:
   - "Upgrade UXX: in_progress, <what done>, <what remaining>"
   - "Next session: tiếp tục UXX hoặc chuyển UYY"
```

### Session N+1 resume

```
1. Đọc handoff letter
2. Đọc tracker → verify handoff letter matches tracker
3. Nếu mismatch → trust tracker
4. Continue upgrade in_progress hoặc start new
```

---

## 7. Quality gates

### Gate 0: Pre-upgrade

- [ ] Tracker đọc và understood
- [ ] Upgrade tiếp theo identified
- [ ] Dependencies all done
- [ ] Spec đọc và understood
- [ ] `verify-workspace.ps1` pass (baseline)

### Gate 1: Post-implementation

- [ ] All files created/modified per spec
- [ ] No unrelated changes
- [ ] Code follows existing conventions
- [ ] No secrets hardcoded

### Gate 2: Post-verification

- [ ] All acceptance criteria checked
- [ ] All verification steps run
- [ ] Verification output recorded in tracker
- [ ] `verify-workspace.ps1` still pass

### Gate 3: Post-commit

- [ ] Commit hash recorded in tracker
- [ ] Tracker status = "done"
- [ ] Dependents checked for unblock
- [ ] Metrics_current updated (if applicable)

### Gate 4: Phase completion

- [ ] All upgrades in phase done
- [ ] `verify-workspace.ps1` pass
- [ ] Metrics_current updated for phase
- [ ] Phase gate review documented
- [ ] Ready for next phase

---

## 8. Anti-patterns (KHÔNG LÀM)

| Anti-pattern | Tại sao sai | Correct approach |
|--------------|-------------|------------------|
| Skip AC vì "looks done" | "Looks done" ≠ verified | Chạy verification steps, record output |
| Gộp 2+ upgrades trong 1 commit | Khó trace, khó rollback | 1 upgrade per commit |
| Không update tracker | Future session không biết trạng thái | Update tracker sau mỗi upgrade |
| Thay đổi spec không UPR | Spec drift, không trace được | Tạo UPR, update tracker notes |
| Giả định upgrade done dựa trên memory | Memory có thể sai | Trust tracker, verify lại |
| Skip dependencies | Upgrade có thể break | Đợi dependencies done |
| Không chạy verify-workspace | Có thể break existing | Chạy trước và sau upgrade |
| Mark done khi AC chưa pass | False completion | Fix cho đến khi pass hoặc mark blocked |
| Push mà không commit tracker | Tracker remote mismatch | Commit tracker cùng upgrade |

---

## 9. Quick reference card

```
┌─────────────────────────────────────────────────────────────────┐
│ UPGRADE EXECUTION QUICK CARD                                     │
├─────────────────────────────────────────────────────────────────┤
│ 1. READ tracker → find next pending upgrade (P0 > P1 > P2 > P3) │
│ 2. CHECK dependencies → all must be "done"                       │
│ 3. READ spec in UPGRADE_PLAN.md (## UXX)                         │
│ 4. RUN verify-workspace.ps1 (baseline)                           │
│ 5. SET tracker status → "in_progress"                            │
│ 6. IMPLEMENT per spec (files, code)                              │
│ 7. RUN verification steps → record output                        │
│ 8. CHECK all acceptance criteria → all must pass                 │
│ 9. RUN verify-workspace.ps1 (must still pass)                    │
│ 10. UPDATE tracker → status "done", commit_hash, notes           │
│ 11. COMMIT: "fix(upgrade): UXX <title> [P0]"                     │
│ 12. CHECK dependents → unblock if ready                          │
│ 13. UPDATE metrics_current (if phase complete)                   │
└─────────────────────────────────────────────────────────────────┘
```
