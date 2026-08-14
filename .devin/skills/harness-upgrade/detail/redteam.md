# harness-upgrade — Detail: RED-TEAM & ROOT-CAUSE REMEDIATION (`--red-team`)

> **HARNESS RED-TEAM & ROOT-CAUSE REMEDIATION PROTOCOL v2.0**
> Iteration #: [ĐIỀN SỐ] | Chế độ: TRIỆT ĐỂ — CẤM QUICK-FIX

> **V5 UPGRADE**: Sau GĐ0-6 này, chạy tiếp **V5 CONTINUOUS RED-TEAM STEP** (`detail/redteam-v5.md`):
> Protocol v5.0 (thay thế v4.0) với identity/delegation lifecycle, MCP pack, evaluation transfer,
> human oversight, observability/resilience, fail-closed và technology refresh. v2.0 = quét cấu trúc
> nhanh; v5.0 = deep red-team bounded. Xem routing cuối file này.
> Payload v5.0 nằm ở `detail/v5-redteam-prompt.md` (load-on-demand).

> **Chế độ TRIỆT ĐỂ.** Mục tiêu KHÔNG phải "sửa được nhiều lỗi" mà là **"sửa ĐÚNG GỐC những lỗi
> quan trọng nhất"**. Một Critical finding sửa tận gốc còn giá trị hơn 20 finding vá bề mặt.

⚠️ **NGUYÊN TẮC TỐI THƯỢNG — KHÔNG được phép**:
- Dừng sau patch triệu chứng mà chưa xử lý nguyên nhân gốc.
- Tuyên bố "hoàn thành" không có bằng chứng đo lường + regression test.
- Ưu tiên việc dễ làm trước việc quan trọng.
- Đưa finding Critical/High vào "deferred".

## 7.0 Ưu tiên số 1: log lần chạy trước
Nếu tồn tại `harness-upgrade-log.md`: đọc kỹ **"Câu hỏi mở"** và **"Deferred list"** — ĐÂY LÀ ƯU
TIÊN SỐ 1 của lần chạy này, **không phải tìm lỗi mới**.

## GĐ0 — KIỂM KÊ TOÀN DIỆN (Component Map)
Lập bản đồ đầy đủ mọi thành phần: **Skills, Agents/Subagents, Rules/Instruction files, Flows,
Config, Hooks, MCP/Tool registry, Memory/Persistence, Permission model.**

Với MỖI thành phần, truy vết:
- "Dòng/quy tắc này tồn tại để khắc phục lỗi thật nào đã từng xảy ra?" → không trả lời được cụ thể
  → **[UNVERIFIED-ASPIRATIONAL]**.
- "Nếu con người biết X nhưng agent không có X trong bất kỳ file nào, đó là information-parity gap"
  → **[PARITY-GAP]**.
→ Xuất Component Map, gắn nhãn nghi vấn (không xóa vội — xử lý GĐ4).

## GĐ1 — TẤN CÔNG (Red-Team)
Adversary không thiện chí. Vector:
- **A. Prompt/Instruction** — injection, jailbreak, rule conflict, override.
- **B. Tool/Permission** — abuse, escalation, confused deputy, credential leak.
- **C. Hook/Config** — bypass, drift, race condition.
- **D. Memory/State** — poisoning, leakage giữa session.
- **E. Supply-chain** — skill/plugin/MCP bên thứ ba không kiểm chứng.
- **F. Governance** — silent failure, audit trail bị xóa, vòng lặp vô hạn.
- **G. Context/Token** — context rot, stale instruction giết accuracy, tool idle phình context, lock-in dependency.
- **H. Reliability** — one-shot problem, declare-done-sai, drift sau nhiều turn.

Mỗi khai thác thành công → **KHÔNG dừng ở "khai thác được"**, phải trả lời:
**"Đây là lỗi cấu hình đơn lẻ, hay hậu quả của thiết kế sai ở tầng kiến trúc?"** Ghi rõ giả thuyết kiến trúc, không chỉ hiện tượng.
→ Xuất **Attack Report**: `Vector | Thành phần | PoC | Severity | Giả thuyết root cause ở tầng kiến trúc (không phải chỉ hiện tượng)`.

## GĐ2 — ROOT CAUSE ANALYSIS (bắt buộc, có phương pháp)
> Giai đoạn quan trọng nhất — **KHÔNG được rút gọn**.

Với MỌI finding Critical/High, áp dụng **5 Whys** (hoặc fishbone nếu phức tạp hơn 1 nguyên nhân),
viết đủ 5 lớp, không dừng ở lớp 1-2. Ví dụ mẫu bắt buộc theo:
```
1. Vì sao lỗi X xảy ra? → [nguyên nhân bề mặt]
2. Vì sao [nguyên nhân bề mặt] tồn tại? → [nguyên nhân sâu hơn]
3. Vì sao [...] tồn tại? → [...]
4. Vì sao [...] tồn tại? → [...]
5. Vì sao [...] tồn tại? → [NGUYÊN NHÂN GỐC KIẾN TRÚC — đây mới là thứ cần sửa]
```
**Quy tắc kiểm tra**: nếu "nguyên nhân gốc" sửa được bằng "thêm một dòng rule nhắc agent làm đúng"
→ CHƯA PHẢI gốc, đào tiếp. Gốc thật thường ở: thiếu tách quyền, thiếu validation tầng tool-call,
thiếu deterministic gate, thiếu isolation giữa agent, thiếu schema/contract rõ ràng giữa các flow.

Phân loại mọi root cause vào 1 trong 2 nhóm:
- **[STRUCTURAL]** — cần redesign kiến trúc/flow/permission model.
- **[MECHANICAL]** — cần enforcement cứng (hook/validator) thay rule mềm.

→ Xuất **Root Cause Register** + **Risk Matrix (Impact × Likelihood)**, so với baseline các lần trước
đo **xu hướng giảm root-cause tồn đọng qua thời gian** (không phải số lượng patch đã làm).

## GĐ3 — NGHIÊN CỨU ONLINE (bắt buộc web search, theo root cause)
Nghiên cứu KHÔNG theo từng triệu chứng mà theo **từng root cause đã xác định ở GĐ2**. Với mỗi
root cause STRUCTURAL/MECHANICAL:
1. Giải pháp kiến trúc/kỹ thuật mới nhất đang được ngành dùng cho đúng LOẠI vấn đề (không phải triệu chứng cụ thể).
2. GitHub repo/framework mạnh nhất, đang maintain tích cực, có tài liệu/eval công khai, giải quyết root cause ở tầng thiết kế.
3. So sánh ≥2-3 phương án: phương án nào sửa TẬN GỐC (loại bỏ hoàn toàn khả năng tái diễn) vs chỉ giảm xác suất.
4. Đối chiếu chuẩn ngành (**OWASP LLM Top 10, NIST AI 100-2, MITRE ATLAS**) để không tự chế lại cái đã có chuẩn.
→ Xuất **Solution Matrix**, mỗi dòng bắt buộc có cột **"Đây có loại bỏ root cause hoàn toàn, hay chỉ giảm nhẹ triệu chứng?"**.
Bất kỳ giải pháp trả lời "chỉ giảm nhẹ" → loại, quay lại tìm tiếp.

## GĐ4 — LẬP KẾ HOẠCH (ưu tiên theo ROOT CAUSE, KHÔNG theo effort)
**CẤM** công thức ưu tiên có mẫu số là effort. Sắp xếp theo:
- **Tier 1 — BẮT BUỘC XỬ LÝ TRONG PHIÊN NÀY, KHÔNG NGOẠI LỆ**: mọi root cause Critical, dù effort cao.
  Quá lớn → chia milestone CÓ THỜI HẠN cụ thể trong log, KHÔNG đưa vào "deferred" chung.
- **Tier 2 — High**: xử lý toàn bộ nếu còn ngân sách sau Tier 1. Chưa xong → ghi % tiến độ + kế hoạch
  lần kế. **KHÔNG đóng iteration nếu Tier 1 chưa 100% xong.**
- **Tier 3 — Medium/Low**: chỉ ghi nhận, không bắt buộc xử lý ngay.

Mỗi hạng mục Tier 1/2 định nghĩa **Definition of Done cụ thể, đo được**:
- [ ] Root cause được redesign/enforce (không phải patch).
- [ ] Re-attack (GĐ1 lặp lại trên đúng vector này) → không còn khai thác được.
- [ ] Không sinh regression ở thành phần khác.
- [ ] Có eval/test case tự động phát hiện tái diễn trong tương lai.

## GĐ5 — TRIỂN KHAI TRIỆT ĐỂ
Thực thi TOÀN BỘ Tier 1. Với mỗi hạng mục:
1. **[STRUCTURAL]** → redesign component/flow/permission model — không chấp nhận giải pháp "thêm 1 rule nhắc nhở".
2. **[MECHANICAL]** → chuyển rule mềm thành enforcement cứng (hook chặn, validator, schema check, guardrail deterministic).
3. **NGAY SAU KHI SỬA XONG MỖI HẠNG MỤC** (không dồn lại cuối phiên): chạy lại đúng vector tấn công tương ứng
   ở GĐ1 → xác nhận bằng chứng cụ thể đã bịt được, dán log/trace vào báo cáo.
4. Fix làm lộ vấn đề mới → thêm ngay vào Tier 1 phiên này, không đợi lần sau.
5. KHÔNG chuyển hạng mục tiếp theo nếu DoD chưa đủ 4 tick ở GĐ4.

**CẤM TUYỆT ĐỐI** (tự-kiểm tra trước khi báo "done"):
- ❌ Thêm comment/warning/instruction mà không có cơ chế chặn thật.
- ❌ Sửa 1 file cấu hình đơn lẻ khi root cause nằm ở nhiều nơi (phải quét toàn hệ thống tìm mọi chỗ cùng pattern lỗi).
- ❌ Bỏ qua re-attack vì "chắc là đã sửa rồi".
- ❌ Gắn nhãn Critical thành Medium để dễ đưa vào deferred.

## GĐ6 — GHI LOG + KIỂM TOÁN TIẾN ĐỘ THẬT
Cập nhật `harness-upgrade-log.md`:
- Root Cause Register: cái nào bịt TẬN GỐC (có bằng chứng re-attack), cái nào chỉ giảm nhẹ (ghi rõ, không giả vờ đã xong).
- Xu hướng qua các lần chạy: tổng root cause tồn đọng **TĂNG hay GIẢM** — chỉ số thành công thật, không phải "số patch".
- Danh sách repo/công nghệ mới đã tích hợp thực sự vào kiến trúc.
- Câu hỏi mở cho lần sau, ưu tiên root cause chưa xử lý hết Tier 1/2.

**KẾT THÚC**: còn Tier 1 chưa xong → **NÊU RÕ ĐIỀU NÀY ĐẦU TIÊN** ở báo cáo tổng kết, không chôn cuối.
**KHÔNG kết luận "phiên thành công" nếu Tier 1 còn tồn đọng.**

## Routing
- `--red-team --check` → GĐ0-3 → Solution Matrix, KHÔNG deploy.
- `--red-team` → GĐ0-6. Fix M+ đi qua `/full-power`. S-tier fix (1 file, <5 dòng) sửa trực tiếp + re-attack ngay.
- **→ SAU GĐ0-6 (mọi chế độ red-team được bật): chạy `detail/redteam-v5.md` (Protocol v5.0, thay v4.0).**
  `--check`/`--no-apply` → `AUDIT_ONLY` (PHASE 1-16); `--red-team` → đủ PHASE 1-19.
  `--no-red-team` → KHÔNG chạy v2.0 lẫn v5.0.