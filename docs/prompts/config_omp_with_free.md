Bạn hãy đóng vai trò là Senior AI Systems Engineer. Hãy tự động quét danh mục model hiện có trên hệ thống OMP và thiết lập cấu hình Model Miễn Phí (Zero-Cost

/ Free Tier) tối ưu nhất (Best Practice) cho workspace hiện tại theo các tiêu chuẩn kỹ thuật sau:

### 1. Nguyên tắc an toàn &amp; Phạm vi (Scope &amp; Isolation)

- **Chỉ cấu hình cấp Project**: Mọi thiết lập chỉ được ghi vào file `.omp/config.yml` tại thư mục gốc của workspace.

- **Tuyệt đối không can thiệp toàn cục**: Không sửa đổi `~/.omp/agent/`, không ghi đè cấu hình global.

- **Bảo mật &amp; Clean**: Không lưu API key/secrets vào `.omp/`, không sửa `.gitignore`, không tạo file cấu hình thừa (như `models.yml` ở project).

- **Phân định lưu trữ Role**: Bắt buộc đặt `modelRoleStorage: project` để mọi thay đổi role sau này được ghi nhận cục bộ trong repository.

### 2. Quy trình thực hiện tự động (Automated Workflow)

1. **Quét và phát hiện (Discovery)**:

   - Chạy lệnh `omp models find free --json` (hoặc truy vấn danh mục model có `cost.input == 0` và `cost.output == 0`).

   - Tổng hợp danh sách đầy đủ các model selector miễn phí từ tất cả các provider đã kích hoạt trên máy (Command Code, OpenCode, OpenRouter, Together, Groq,

Ollama/Local, v.v.).

2. **Thiết lập Allow-List `enabledModels`)**:

   - Ghi toàn bộ selector đầy đủ của các model 0-cost vừa tìm thấy vào mục `enabledModels`.

   - Đảm bảo danh sách này hoạt động như một bức tường lửa (firewall) chặn hoàn toàn các model có phí.

3. **Phân bổ vai trò tối ưu (Role Mapping Best Practices)**:

   - **Heavy / Reasoning Roles** `default`, `plan`, `slow`, `task`, `advisor`, `designer`): Gán cho model miễn phí có context window lớn nhất và khả năng

suy luận mạnh nhất (ví dụ: MiniMax M3, GLM-5.2, Kimi K2.7, DeepSeek-V3/R1).

   - **Fast / Compact Roles** `smol`, `tiny`, `commit`): Gán cho model nhẹ hơn, tốc độ phản hồi nhanh hơn (ví dụ: MiniMax M2.7, Llama-3-8B-free, v.v.).

   - **Vision Role** `vision`): Chỉ gán nếu trong danh sách free có model hỗ trợ `input: ["image"]`. Nếu không có model miễn phí nào hỗ trợ hình ảnh, BỎ QUA

không cấu hình role này.

4. **Tạo file `.omp/config.yml`**:

   - Ghi cấu hình dạng YAML mapping chuẩn, tường minh, không dùng alias hoặc bare model ID.

5. **Xác minh đa tầng (Multi-layered Verification)**:

   - Chạy `omp config get enabledModels --json` để xác nhận danh sách whitelist.

   - Chạy `omp config get modelRoleStorage --json` và `omp config get modelRoles --json` để xác nhận các role đã trỏ đúng model.

   - Chạy lệnh kiểm tra chi phí để bảo đảm 100% các model được gán đều có `cost.input == 0` và `cost.output == 0`.

### 3. Đầu ra yêu cầu

- Báo cáo bảng danh sách các model miễn phí tìm thấy kèm thông số (Context window, Max tokens, Provider).

- Nội dung file `.omp/config.yml` hoàn chỉnh.

- Kết quả đối chiếu verification thực tế từ terminal.