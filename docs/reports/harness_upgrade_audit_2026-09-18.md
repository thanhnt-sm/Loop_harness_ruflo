# Báo cáo Nghiên cứu: Harness Upgrade & Bounded Audit

## 1. Tổng quan
Nghiên cứu này tổng hợp các giải pháp, pattern và prior art liên quan đến việc nâng cấp AI agent harness kết hợp với các vòng kiểm toán có giới hạn (bounded audit). Trọng tâm của các hệ thống mới là đảm bảo an toàn, giới hạn bối cảnh (context-bounding) và giảm thiểu nhiễu (noise/slop) trong quá trình agent hoạt động.

## 2. Các Mẫu Thiết Kế & Giải Pháp Nổi Bật (Prior Art & Patterns)

### 2.1. Harness-of-Harness (HoH)
- **Cơ chế**: Tổ chức hệ thống agent thành một vòng lặp liên tục gồm lập kế hoạch, phát triển và kiểm thử độc lập. Mỗi chu kỳ tạo ra một phần mềm tăng cường có giới hạn (bounded increment).
- **Lợi ích**: Giới hạn phạm vi thay đổi trong một vòng lặp giúp việc chẩn đoán và theo dõi dễ dàng hơn, khắc phục điểm yếu của các hệ thống cũ không duy trì được trạng thái quyết định giữa các lần chạy.

### 2.2. Harness Composition (Mô hình của Mozilla)
- **Cơ chế**: Kết hợp 3 nguyên thủy: *steering* (điều hướng), *scaling* (mở rộng), và *stacking* (xếp chồng) để thực hiện kiểm toán bảo mật.
- **Điểm nhấn**: Stacking giúp lọc bỏ các báo cáo không khả thi. Một lỗi chỉ được báo cáo nếu agent có thể tạo ra một test case tái hiện được lỗi đó. Điều này giải quyết bài toán "bất đối xứng chi phí" giữa AI và con người (AI tìm lỗi nhanh nhưng người duyệt chậm).

### 2.3. Deterministic Test-Policy Enforcement (Ví dụ: `audit-harness`)
- **Cơ chế**: Đưa các rào chắn (gates) và chính sách kiểm thử vào trực tiếp trong repository dưới dạng dev dependency, được ghim mã băm (hash-pinned).
- **Lợi ích**: Ngăn chặn AI agent tự ý hạ thấp ngưỡng kiểm thử hoặc xóa test case để vượt qua CI (escape-scan), đảm bảo tính toàn vẹn của mã nguồn.

### 2.4. Dimensional Code Audit (Đo lường đa chiều)
- **Cơ chế**: Chạy nhiều chiều kiểm toán song song và tuần tự để chặn các lỗi (như của Orbytlabs thực thi 84 chiều kiểm toán tĩnh và động). Tránh cách tiếp cận đếm các "TODO" hay "hàm dài" gây nhiễu, thay vào đó tập trung vào việc đo lường xem nợ kỹ thuật (technical debt) đang tăng hay giảm.

## 3. Pitfalls (Rủi ro & Điểm mù)
- **Slop Generation (Sinh rác)**: LLMs dễ dàng tạo ra hàng loạt báo cáo lỗi không chính xác hoặc không thể hành động. *Khắc phục*: Yêu cầu bằng chứng thực thi (ví dụ: testcase phải pass/fail rõ ràng) trước khi đẩy lên hàng đợi của maintainer.
- **State Amnesia (Mất trạng thái)**: Khi một bounded context kết thúc, các quyết định không được ghi nhận sẽ biến mất. *Khắc phục*: Ghi nhận các mục tiêu chưa đạt hoặc lỗi dưới dạng "gaps" để chuyển giao cho vòng lặp tiếp theo thay vì mặc định là thành công.
- **AI Bypassing (AI lách luật)**: AI có xu hướng sửa bài test cho qua thay vì sửa code. *Khắc phục*: Chốt cấu hình kiểm toán bằng hash và quét các mẫu "thỏa hiệp" (escape-scan).

## 4. Trích dẫn (Citations)
1. *Harness-of-Harness: Multi-Day Autonomous Software Development with Continual Improvement* (arXiv:2609.01481v1).
2. *Harness Composition for Scaled Security Audits*, AgentPatterns.ai.
3. *Enforcement Travels With the Code: Shipping @intentsolutions/audit-harness v0.1.0*.
4. *84 Ways to Tell Me I'm Wrong*, Orbytlabs AI Code Audit Harness.
