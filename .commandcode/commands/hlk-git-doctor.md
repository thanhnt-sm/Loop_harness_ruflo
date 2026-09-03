Bạn đang chạy skill `hlk-git-doctor` (HLK git pre-flight check) qua cmdc.

1. Chạy:
   ```bash
   node HLK/git-tools/hlk-git-doctor.mjs
   ```
2. Tool sẽ kiểm tra:
   - Working tree clean / uncommitted changes.
   - Branch sync với remote.
   - HLK integrity (sanity check nhanh).
   - core.hooksPath có trỏ đúng không.
   - Không có file cấm bị track.
3. Nếu PASS → echo "ready to commit/push".
4. Nếu FAIL → liệt kê vấn đề + gợi ý fix (KHÔNG tự fix).
5. Nếu user muốn tiếp commit/push → dùng `/hlk-git-tools commit "<msg>"` hoặc
   `/hlk-git-tools push`.

Lưu ý: tool này READ-ONLY trên git state, không commit/push.

Action: $ARGUMENTS
