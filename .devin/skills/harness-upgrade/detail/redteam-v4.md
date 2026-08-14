<!--
  V4 RED-TEAM STEP — hướng dẫn CHẠY prompt v4.0 (payload: detail/v4-redteam-prompt.md).
  Chỉ nạp payload khi thực thi bước; KHÔNG load ở BOOT / không load chung "load all detail files".
  Tuân detail/adaptation.md nếu model yếu / context < 50K.
-->
# harness-upgrade — Detail: V4 CONTINUOUS RED-TEAM STEP (nâng cấp Protocol v2.0 → v4.0)

> **BƯỚC NÀY chạy prompt `HARNESS CONTINUOUS RED-TEAM, ROOT-CAUSE REMEDIATION & TECHNOLOGY
> REFRESH PROTOCOL v4.0` (payload: `detail/v4-redteam-prompt.md`) như một iteration bounded.**
> Nó KHÔNG thay thế hoàn toàn GĐ0-6 v2.0 — v2.0 = quét cấu trúc nhanh; v4.0 = deep red-team có
> evidence ledger, role separation, control/data plane, fail-closed và technology refresh.

## 1. Khi nào chạy bước này
| Invocation | Chạy V4? | Ghi chú |
|---|---|---|
| *(mặc định)* / `full` / `--red-team` | ✅ | Chạy sau v2.0 GĐ0-6, trước COMPENSATION |
| `--check` / `--no-apply` | ✅ audit-only | `CHANGE_MODE = AUDIT_ONLY`: chỉ chạy PHASE 0-8 + kết luận `AUDIT_ONLY_COMPLETE`; KHÔNG patch |
| `--no-red-team` | ❌ | Bỏ bước này + bỏ redteam.md |
| `--apply` | ⚠️ | Chỉ dùng lại artifact v4 từ lần `--check` trước, không red-team mới |

## 2. Điều kiện tiên quyết (nếu thiếu → BLOCKED, không active red-team)
Bước này chỉ active red-team khi **tất cả** các placeholder sau có giá trị thật trong
`scope-manifest.json` (từ `preflight.md`):
`WORKSPACE_PATH | AUTHORIZED_TARGETS_AND_PATHS | EXPLICITLY_EXCLUDED_TARGETS | ENVIRONMENT |
CHANGE_MODE | ONLINE_RESEARCH | MAX_WALL_TIME | MAX_TEST_COST | APPROVER`.

Nếu `ENVIRONMENT` không có sandbox/staging → chỉ static analysis + safe mock + plan, không active red-team.
Nếu `CHANGE_MODE` không cho phép sửa → không patch. Nếu thiếu bất kỳ placeholder → xuất
`BLOCKED_PREREQUISITES`, tiếp tục bằng static analysis an toàn, KHÔNG gọi target ngoài local.

## 3. Nạp payload + fill placeholder (bắt buộc)
1. Đọc `detail/v4-redteam-prompt.md`.
2. THAY mọi `{{PLACEHOLDER}}` bằng giá trị Runtime Manifest đã xác nhận (KHÔNG tự suy đoán).
   - Không có giá trị → GIỮ placeholder và đánh dấu `BLOCKED_PREREQUISITES`.
   - `ITERATION_ID` = lần chạy kế tiếp trong `harness-upgrade-log.md` (tăng từ lần trước).
   - `CURRENT_DATE_TIMEZONE` = giờ hiện tại; `PREVIOUS_ITERATION_ID` = lần trước (hoặc NONE).
   - `ARTIFACT_ROOT` = thư mục artifact của phiên (mặc định: thư mục harness-upgrade).
   - `LOG_PATH` = `harness-upgrade-log.md` (đã ghi trong prompt).
3. Sau khi fill, chạy nguyên văn prompt đã fill trong context. Không cắt bỏ mục trừ khi
   `--no-apply`/`--check` (thì `CHANGE_MODE=AUDIT_ONLY`, chỉ thực thi tới PHASE 8 rồi kết luận).

## 4. Runtime Manifest map (placeholder → nguồn trong harness này)
| Prompt placeholder | Nguồn giá trị |
|---|---|
| `WORKSPACE_PATH`, scope, excludes | `scope-manifest.json` từ `preflight.md` (PHASE 0) |
| `ENVIRONMENT` | `SANDBOX` nếu có sandbox/worktree; ngược lại `NO_PRODUCTION_ACCESS` |
| `CHANGE_MODE` | `--no-apply`/`--check` → `AUDIT_ONLY`; mặc định → `APPLY_WITH_APPROVAL` (M+ qua `/full-power`) |
| `ONLINE_RESEARCH` | `ENABLED` nếu websearch có sẵn + được phép; ngược lại `DISABLED` |
| `MAX_WALL_TIME` / `MAX_TEST_COST` | budget trong argument / user; mặc định hữu hạn |
| `APPROVER` | `HUMAN` (cần xác nhận gate High/Critical); nếu không → ghi NONE + require human |
| `BASELINE_COMMANDS` | lệnh baseline ở `detail/verify.md` (hook_integrity, context_projection, pytest) |
| `AUTHORIZED_TOOLS` | allowlist tool từ permissions của skill + `tools/` đã verify |
| `AUTHORIZED_NETWORK_DESTINATIONS` | chỉ URL trong `docs/` + REPOS.md đã verify; mặc định rỗng |
| `MAX_SOURCE_AGE_DAYS` | SLA freshness (mặc định 180) |

## 5. Bounded iteration (chống vòng lặp vô hạn)
- Bước V4 = **MỘT iteration** đi qua state machine trong prompt
  `INIT → ... → LOGGED → HANDOFF`. Không tự lặp thêm vòng; nếu chưa hết Critical → giữ
  `OPEN_CRITICAL` + milestone có hạn, ghi vào log, kết thúc iteration (không tự chạy tiếp).
- Tuân `MAX_WALL_TIME`, `MAX_TEST_COST`, `MAX_CONCURRENCY`; dừng khi hết budget → `STOPPED_SAFELY`
  với `NEXT_SAFE_ACTION`.
- Dừng ngay (fail-closed) khi: scope/authorization conflict, phát hiện secret/PII/prod side effect
  ngoài kế hoạch, sandbox escape / permission escalation, audit trail mất / verifier không tái lập,
  hoặc fix làm giảm containment/rollback/observability.

## 6. Separation of duties (tương thích Commander + executors)
| Vai trò v4.0 | Bản đồ sang harness này |
|---|---|
| SCOUT | SCOUT worker (read-only inventory, snapshot, drift) |
| THREAT MODELER | ARCHITECT / persona architect |
| ATTACKER | persona saboteur + security_auditor trong sandbox/fixture |
| ROOT-CAUSE ANALYST | persona code_reviewer + systematic_debugging (5 Whys) |
| RESEARCHER | websearch + `detail/learn.md` + update_from_repos |
| IMPLEMENTER | lightning/glm/kimi executor (M+ qua `/full-power`) |
| INDEPENDENT VERIFIER | persona new_hire + fable-judge + claim-grader + verifier worker (read-only, corpus đã khóa) |
| RELEASE GATEKEEPER | approval_gate + human approver (High/Critical) |

- Nếu runtime chỉ 1 agent → mô phỏng: artifact riêng mỗi role, hash đầu vào/đầu ra, verifier dùng
  read-only context, corpus/test manifest khóa hash, human approval cho High/Critical.
- **KHÔNG coi Implementer tự chấm là independent verification.**

## 7. Ngưỡng token / model yếu (đọc `detail/adaptation.md` trước)
- Nếu model yếu / context < 50K: **KHÔNG** nạp full payload 1 lần. Chia prompt thành các chunk
  theo phase (0-2, 3-5, 6-8, 9-11), mỗi chunk ≤5-8 instruction, làm tuần tự, sau mỗi chunk báo.
- Ưu tiên: chỉ giữ invariant tối thiểu + state machine + fail-closed + kết luận bắt buộc (Section XXI).
  Các phase nặng (XII eval science, XV research) → chỉ tóm tắt nếu budget hẹp, ghi rõ đã lược bớt.
- Luôn giữ Section XXI (kết luận bắt buộc) nguyên vẹn ở cuối.

## 8. Đầu ra bước V4
Ghi vào `ARTIFACT_ROOT` (xem Section XX prompt — 23 artifact; tối thiểu bắt buộc):
`scope-manifest.json`, `baseline.json`, `component-map.md`, `attack-report.md`,
`root-cause-register.md`, `technology-candidates.md`, `change-manifest.md`,
`verification-report.md`, `release-gate.md`, `evidence-ledger.jsonl`, `executive-summary.md`.
Kết luận phải bắt đầu bằng một trạng thái ở Section XXI; Critical còn mở nêu **câu đầu tiên**.

## 9. Routing trong skill
- Chạy ngay sau `RED-TEAM + ROOT-CAUSE (v2.0, GĐ0-6)` và trước `COMPENSATION`.
- `--no-red-team` → bỏ bước này + bỏ redteam.md.
- `--check` / `--no-apply` → chỉ `AUDIT_ONLY` (PHASE 0-8), kết luận `AUDIT_ONLY_COMPLETE`, không patch.
- `--red-team` → nhấn mạnh V4: đủ PHASE 0-11 + re-attack + verifier độc lập.
- Mọi fix High/Critical M+ → qua `/full-power`. S-tier (1 file, <5 dòng) sửa trực tiếp + re-attack ngay.
- Sau bước V4 → quay về main flow để chạy COMPENSATION → REPORT → APPLY như bình thường.
