<!--
  V5 RED-TEAM STEP — hướng dẫn CHẠY prompt v5.0 (payload: detail/v5-redteam-prompt.md).
  v5.0 kế thừa + thay thế v4.0. Chỉ nạp payload khi thực thi bước; KHÔNG load ở BOOT / không load
  chung "load all detail files". Tuân detail/adaptation.md nếu model yếu / context < 50K.
-->
# harness-upgrade — Detail: V5 CONTINUOUS RED-TEAM STEP (Protocol v5.0)

> **BƯỚC NÀY chạy prompt `HARNESS CONTINUOUS RED-TEAM, ROOT-CAUSE REMEDIATION & TECHNOLOGY
> REFRESH PROTOCOL v5.0` (payload: `detail/v5-redteam-prompt.md`) như một iteration bounded.**
> v5.0 **thay thế** v4.0 (canonical mới nhất); v2.0 GĐ0-6 = quét cấu trúc nhanh, v5.0 = deep
> red-team: identity/delegation lifecycle, MCP pack, evaluation transfer, human oversight,
> resilience/observability, fail-closed + technology refresh.

## 0. Điểm mới v5.0 vs v4.0 (và cạm bẫy cần kiểm soát)
| Mới trong v5.0 | Cạm bẫy khi chạy ở harness này | Cách xử lý (đã mã hóa dưới đây) |
|---|---|---|
| Identity/delegation chain + registry + `REVOCATION_BOUND` (§3) | Thiếu identity-service/token infra | Nếu không có infra → ghi `BLOCKED`/`UNKNOWN`, không giả vờ |
| MCP mandatory pack (§11) | Cần server MCP thật + token/SDK | Test local stdio trước, remote HTTP ghi `UNKNOWN` nếu không có server |
| Evaluation transfer cross-model (§13) | Harness chỉ có ít model (glm/kimi free, lightning) | Ghi `BLOCKED`/`NOT_APPLICABLE` cho combos không chạy được |
| Human oversight / approval_binding_hash (§7) | `APPROVER=NONE` thì high-risk phải HOLD | `STOPPED_SAFELY` + human review |
| Observability/resilience spans (§17) | Có thể không có OTel đầy đủ | Telemetry outage → fail-closed, ghi `BLOCKED` |
| 27 artifacts + dataset/solver/scorer hash (§12,18) | Token bloat | Chunk theo phase, tối thiểu artifact bắt buộc |
| `risk score` (§7,16) chưa định nghĩa | Mơ hồ → dễ bị game | Dùng rubric risk-score deterministic bên dưới |

## 1. Khi nào chạy bước này
| Invocation | Chạy V5? | Ghi chú |
|---|---|---|
| *(mặc định)* / `full` / `--red-team` | ✅ | Chạy sau v2.0 GĐ0-6, trước COMPENSATION |
| `--check` / `--no-apply` | ✅ audit-only | `CHANGE_MODE = AUDIT_ONLY`: chỉ PHASE 1-16 + kết luận `AUDIT_ONLY_COMPLETE`; KHÔNG patch |
| `--no-red-team` | ❌ | Bỏ bước này + bỏ redteam.md |
| `--apply` | ⚠️ | Chỉ dùng lại artifact v5 từ lần `--check` trước, không red-team mới |

## 2. Điều kiện tiên quyết (nếu thiếu → BLOCKED, không active red-team)
Chỉ active red-team khi **tất cả** placeholder sau có giá trị thật trong `scope-manifest.json`:
`WORKSPACE_PATH | AUTHORIZED_TARGETS_AND_PATHS | EXCLUDED_TARGETS | ENVIRONMENT | CHANGE_MODE |
ONLINE_RESEARCH | MAX_WALL_TIME | MAX_TEST_COST | APPROVER`.

- `ENVIRONMENT` không có sandbox/staging → chỉ static analysis + safe mock + plan.
- `CHANGE_MODE` không cho sửa → không patch.
- `APPROVER = NONE` → mọi action High-risk/irreversible phải `HOLD`/`STOPPED_SAFELY`.
- Thiếu placeholder bất kỳ → xuất `BLOCKED_PREREQUISITES`, tiếp tục bằng static analysis an toàn.

## 3. Nạp payload + fill placeholder (bắt buộc)
1. Đọc `detail/v5-redteam-prompt.md`.
2. THAY mọi `{{PLACEHOLDER}}` bằng giá trị Runtime Manifest đã xác nhận (KHÔNG tự suy đoán).
   - Không có giá trị → GIỮ placeholder + đánh dấu `BLOCKED_PREREQUISITES`.
   - `ITERATION_ID` = lần kế tiếp trong `harness-upgrade-log.md`; `PREVIOUS_ITERATION_ID` = lần trước (hoặc NONE).
   - `CURRENT_DATE_TIMEZONE` = giờ hiện tại; `ARTIFACT_ROOT` = thư mục artifact phiên; `LOG_PATH` = `harness-upgrade-log.md`.
3. Sau khi fill, chạy nguyên văn prompt đã fill. `--check`/`--no-apply` → `CHANGE_MODE=AUDIT_ONLY`, chỉ thực thi PHASE 1-16 rồi kết luận.

## 4. Runtime Manifest map (placeholder → nguồn trong harness này)
| Prompt placeholder | Nguồn giá trị |
|---|---|
| `WORKSPACE_PATH`, scope, excludes | `scope-manifest.json` từ `preflight.md` (PHASE 8) |
| `ENVIRONMENT` | `SANDBOX` nếu có sandbox/worktree; ngược lại `NO_PRODUCTION_ACCESS` |
| `CHANGE_MODE` | `--no-apply`/`--check` → `AUDIT_ONLY`; mặc định → `APPLY_WITH_APPROVAL` (M+ qua `/full-power`) |
| `ONLINE_RESEARCH` | `ENABLED` nếu websearch sẵn + được phép; ngược lại `DISABLED` |
| `MAX_WALL_TIME` / `MAX_TEST_COST` / `MAX_CONCURRENCY` | budget trong argument/user; mặc định hữu hạn |
| `APPROVER` | `HUMAN` nếu cần xác nhận gate High/Critical; nếu không → NONE + require human |
| `BASELINE_COMMANDS` | lệnh ở `detail/verify.md` (hook_integrity, context_projection, pytest) |
| `AUTHORIZED_TOOLS` | allowlist tool từ permissions skill + `tools/` đã verify |
| `AUTHORIZED_NETWORK_DESTINATIONS` | chỉ URL trong `docs/` + REPOS.md đã verify; mặc định rỗng |
| `MODEL_RUNTIME_ALLOWLIST` | các executor đã đăng ký (lightning/glm/kimi) + version |
| `MAX_SOURCE_AGE_DAYS` | SLA freshness (mặc định 180) |

## 5. Bounded iteration + budget (chống vòng lặp vô hạn)
- Bước V5 = **MỘT iteration** qua state machine `INIT → PREFLIGHT → BASELINE_LOCKED → INVENTORIED →
  THREAT_MODEL_LOCKED → ATTACKED → RCA_COMPLETE → RESEARCHED → PLAN_APPROVED → IMPLEMENTED →
  VERIFIED → RELEASE_GATE → LOGGED → HANDOFF`. Không tự lặp thêm vòng.
- Chưa hết Critical → giữ `OPEN_CRITICAL` + milestone có hạn, ghi log, kết thúc iteration (không tự chạy tiếp).
- Dừng ngay (fail-closed) khi: scope/authorization conflict; secret/PII/prod side effect ngoài kế hoạch;
  sandbox escape / permission escalation; audit trail mất / verifier không tái lập; budget hết; fix làm
  giảm containment/rollback/observability.

## 6. Separation of duties (map vai trò v5.0 → harness)
| Vai trò v5.0 | Bản đồ sang harness này |
|---|---|
| SCOUT | SCOUT worker (read-only inventory, snapshot, drift, registry) |
| THREAT_MODELER | ARCHITECT / persona architect |
| ATTACKER | persona saboteur + security_auditor trong sandbox/fixture |
| ROOT_CAUSE_ANALYST | persona code_reviewer + systematic_debugging (5 Whys + counterfactual) |
| RESEARCHER | websearch + `detail/learn.md` + update_from_repos |
| IMPLEMENTER | lightning/glm/kimi executor (M+ qua `/full-power`) |
| INDEPENDENT_VERIFIER | persona new_hire + fable-judge + claim-grader + verifier worker (read-only, corpus/scorer đã khóa) |
| RELEASE_GATEKEEPER | approval_gate + human approver (High/Critical) |

- Runtime chỉ 1 agent → mô phỏng: artifact riêng mỗi role, hash đầu vào/đầu ra, verifier dùng read-only
  context, dataset/solver/scorer khóa hash, human approval cho High/Critical.
- **KHÔNG coi Implementer tự chấm là independent verification.**

**Map PDP/PEP/scorer v5.0 → thành phần harness hiện có** (để invariant không thành aspirational):
- `PDP` → policy engine/hook hiện có (pre_tool_use, plan_enforce, approval_gate) hoặc OPA nếu có.
- `PEP` → schema_gate, coverage_enforce, hook chặn (chặn destructive), sandbox, egress allowlist.
- `Scorer/Oracle` → coverage_matrix, fable-judge, claim-grader (rule-based trước, model-grader sau).
- `Dataset/Corpus hash` → hash `tests/` + test manifest trước khi chạy.
- `Sandbox` → worktree/snapshot (từ `scripts/worktree` / snapshot) + fixture synthetic.
- Nếu map được → invariant có thể đạt `VERIFIED`; không map được → `UNENFORCED_POLICY`, ghi rõ.

## 7. Risk-score rubric (vì §7/§16 dùng "risk score" chưa định nghĩa)
Tính `risk = Permission_Tier(0-4) × Automation × Trust × DataSensitivity`, trong đó:
- Permission tier theo `REDLINES.md` L0-L4 (L0=0 … L4=4). Unclassified = 4 (deny).
- High-risk nếu `risk ≥ 3` HOẶC thuộc danh sách High-risk bất kể số dòng: permission/secret boundary,
  network egress, shell/code executor, memory isolation, audit trail, policy engine, model router,
  MCP authorization, production path.
- Ghi risk score vào từng action + receipt; nếu đổi binding (target/params/audience/schema/policy/
  identity/env) → `approval_binding_hash` đổi → re-approval bắt buộc.

## 8. MCP pack + transfer: ghi BLOCKED/UNKNOWN khi thiếu infra
- MCP tests (§11): nếu không có MCP server thật / SDK / token infra → test local stdio nếu có; remote
  HTTP / SSRF / token passthrough / redirect → ghi `UNKNOWN`/`BLOCKED` (không giả vờ pass).
- Evaluation transfer (§13): chỉ test trên model/schema/scenario hiện có; các combo khác → `NOT_APPLICABLE`
  hoặc `UNKNOWN`, ghi "chưa kiểm tra". KHÔNG mang payload nguy hiểm ra ngoài fixture.
- Cross-model: tối đa trên các executor sẵn có (glm/kimi/lightning); không có model khác → ghi rõ.

## 9. Ngưỡng token / model yếu (đọc `detail/adaptation.md` trước)
- Model yếu / context < 50K: **KHÔNG** nạp full payload 1 lần. Chunk theo phase:
  `1-4 | 5-7 | 8-11 | 12-14 | 15-16 | 17-19`, mỗi chunk ≤5-8 instruction, làm tuần tự, sau mỗi chunk báo.
- Ưu tiên giữ: §1 mục tiêu, §2 fail-closed, §6 fail-closed/PEP, §16 DoD, §19 kết luận bắt buộc.
  Các phase nặng (§10 matrix, §12 eval science, §15 research) → tóm tắt nếu budget hẹp, ghi rõ đã lược bớt.
- Luôn giữ §19 (kết luận bắt buộc) nguyên vẹn ở cuối.

## 10. Đầu ra bước V5
Ghi vào `ARTIFACT_ROOT` (Section 18 prompt — 27 artifact; tối thiểu bắt buộc):
`scope-manifest.json`, `baseline.json`, `registry.json`, `component-map.md`, `identity-delegation-map.md`,
`attack-report.md`, `evaluation-manifest.json`, `dataset-hash.txt`, `solver-hash.txt`, `scorer-hash.txt`,
`evidence-ledger.jsonl`, `root-cause-register.md`, `technology-candidates.md`, `change-manifest.md`,
`verification-report.md`, `release-gate.md`, `resilience-report.md`, `executive-summary.md`.
Kết luận phải bắt đầu bằng một trạng thái ở §19; Critical còn mở nêu **câu đầu tiên**.

## 11. Routing trong skill
- Chạy ngay sau `RED-TEAM + ROOT-CAUSE (v2.0, GĐ0-6)` và trước `COMPENSATION`.
- `--no-red-team` → bỏ bước này + bỏ redteam.md.
- `--check` / `--no-apply` → chỉ `AUDIT_ONLY` (PHASE 1-16), kết luận `AUDIT_ONLY_COMPLETE`, không patch.
- `--red-team` → nhấn mạnh V5: đủ PHASE 1-19 + re-attack + verifier độc lập + registry/identity + MCP pack.
- Mọi fix High/Critical M+ → qua `/full-power`. S-tier (1 file, <5 dòng) sửa trực tiếp + re-attack ngay.
- Sau bước V5 → quay về main flow để chạy COMPENSATION → REPORT → APPLY như bình thường.
