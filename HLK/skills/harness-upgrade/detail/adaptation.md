# harness-upgrade — Detail: WEAK-MODEL & SMALL-CONTEXT ADAPTATION

> ⚠️ **Skill này dành cho AI kém thông minh + context nhỏ. Nhưng nếu đọc full skill file — chính
> model yếu sẽ fail** (exponential decay theo IFScale 2507.11538, lost-in-the-middle theo
> Liu et al. 2024). Do đó tuân thủ file này TRƯỚC TIÊN khi model yếu / context nhỏ.

## A. Chế độ TỐI GIẢN (mặc định khuyến nghị cho model yếu / context < 50K)
KHÔNG tuân theo toàn skill. Chỉ giữ:
1. **5 rule tối thượng** (đặt ở ĐẦU prompt, tránh lost-in-middle):
   1. Sửa đúng gốc, không vá triệu chứng.
   2. Giảm input context là ưu tiên số 1 (bottleneck model yếu).
   3. Verify deterministic sau mỗi thay đổi (chạy script, không tự đoán).
   4. Smallest coherent diff; không scope creep.
   5. Không destructive; HLK/.env không đụng (trừ khi task chính là nâng cấp HLK được chỉ định rõ).
2. **1 upgrade tại một thời điểm** (tránh one-shot problem, giảm rework ~59%).
3. **Few-shot 2-3 mẫu** thay vì dài dòng: cho model yếu xem ví dụ input→output đúng thay vì 10 rule.
4. **Chunk workflow**: làm xong Phase 1 → báo → mới sang Phase 2. Không bơm cả 5 phase 1 lần.
5. Output **rất ngắn**: `what changed | what verified | what risk`, mỗi mục ≤1 dòng.

## B. Ngưỡng instruction density (kiểm tra trước khi thực thi)
- Đếm số instruction phải tuân cùng lúc trong 1 task. Nếu **> 20 instruction** trên model yếu
  → **tách thành chain prompts** (mỗi bước ≤5-8 instruction) hoặc delegate subagent cho từng phần.
- Nghiên cứu: model yếu exponential decay sau ~rất ít instruction (IFScale 2507.11538);
  thông tin giữa context bị mất (Liu 2024). → Chỉ giữ instruction tối thiểu ở ĐẦU.

## C. Self-audit (skill phải áp dụng tiêu chuẩn nó đề ra)
Trước khi kết thúc phiên, tự hỏi:
- Skill/canon/hook vừa tạo có dài + dày instruction cho model yếu không?
- Có 1 dòng prose thừa nào cần cắt không? Có section nào cần chuyển lazy-load không?
- Nếu model yếu phải đọc nó, có fail lost-in-the-middle không?
→ Nếu có, áp dụng U-H7 (progressive load) / U-H4 (slop removal) lên chính artifact vừa tạo.

**Đây là test chất lượng cuối cùng: skill phải tự áp dụng tiêu chuẩn nó đề ra.**