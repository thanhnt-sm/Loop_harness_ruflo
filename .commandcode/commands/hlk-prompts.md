Bạn đang chạy skill `hlk-prompts` (load 6 HLK phân tích prompts) qua cmdc.

1. Liệt kê 6 prompt files trong `HLK/prompts/`:
   - `01_codebase_analysis.prompt.md` — phân tích codebase toàn diện.
   - `02_redteam_security.prompt.md` — red-team security review.
   - `03_solution_architect.prompt.md` — solution architecture design.
   - `05_data_leak_hardening_guide.prompt.md` — guide chống data leak.
   - `06_harness_deepdive_hardening.prompt.md` — hardening harness layer.
   - `07_ruflo_hardening_implementation.prompt.md` — implementation hardening.
2. Nếu `$ARGUMENTS` rỗng → liệt kê tên + 1 dòng mô tả cho mỗi prompt.
3. Nếu `$ARGUMENTS` = `<number>` (01..07) → load prompt đó và execute.
4. Nếu `$ARGUMENTS` = `<keyword>` (vd: `redteam`, `architect`, `data-leak`) →
   match keyword → load prompt tương ứng.
5. Execution flow:
   - Đọc prompt file.
   - Apply lên workspace hiện tại (đọc files, phân tích, viết report).
   - Output: báo cáo theo format trong prompt.
   - KHÔNG sửa HLK/, code, config. Chỉ phân tích + đề xuất.

Ví dụ:
```
/hlk-prompts                    # list
/hlk-prompts 02                 # run red-team security
/hlk-prompts architect          # run solution architect
```

Action: $ARGUMENTS
