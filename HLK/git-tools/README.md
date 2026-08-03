# HLK Git Tools

> Bộ công cụ git an toàn cho workspace Ruflo: chẩn đoán, commit, push, đồng bộ.

---

## Các script

| Script | Mục đích |
|--------|----------|
| `hlk-git-doctor.mjs` | Kiểm tra và tự động sửa vấn đề git thường gặp |
| `hlk-git-commit.mjs` | Commit an toàn với kiểm tra secret/sensitive files |
| `hlk-git-push.mjs` | Push an toàn, set upstream, không force |
| `hlk-git-safe-sync.mjs` | Chạy doctor → commit → push liên tiếp |

---

## Cách dùng

### Kiểm tra sức khỏe repo

```bash
node HLK/git-tools/hlk-git-doctor.mjs
```

Tự động sửa vấn đề an toàn:

```bash
node HLK/git-tools/hlk-git-doctor.mjs --fix
```

Không hỏi xác nhận:

```bash
node HLK/git-tools/hlk-git-doctor.mjs --fix --yes
```

### Commit an toàn

```bash
node HLK/git-tools/hlk-git-commit.mjs -m "feat: update HLK"
```

Script sẽ:

- Kiểm tra file nhạy cảm đang staged.
- Kiểm tra secret trong staged files.
- Kiểm tra file >100MB.
- Từ chối commit nếu phát hiện lỗi.

### Push an toàn

```bash
node HLK/git-tools/hlk-git-push.mjs
```

Script sẽ:

- Kiểm tra divergence với remote.
- Đề xuất pull/rebase nếu behind.
- Set upstream nếu chưa có.
- **Không bao giờ** dùng `--force`.

### Safe sync (một lệnh duy nhất)

```bash
node HLK/git-tools/hlk-git-safe-sync.mjs -m "feat: ..."
```

Tương đương:

```bash
node hlk-git-doctor.mjs --fix
node hlk-git-commit.mjs -m "feat: ..."
node hlk-git-push.mjs
```

---

## Các vấn đề được xử lý

| Vấn đề | Hành động |
|--------|-----------|
| Branch `master` | Đề xuất đổi thành `main` |
| Không có remote | Báo lỗi, hướng dẫn thêm |
| Không track remote | Set upstream |
| Detached HEAD | Báo lỗi, offer checkout `main` |
| Merge conflict | Báo lỗi, offer abort |
| File nhạy cảm staged | Unstage, cảnh báo |
| Secret trong staged | Unstage, cảnh báo |
| File lớn >100MB | Báo lỗi |
| Embedded git repo | Báo lỗi, offer đổi tên `.git` |
| Divergent branch | Đề xuất pull --rebase |

---

## Lưu ý quan trọng

- Các script **không force push**.
- Không tự động xóa file nhạy cảm đã track trong history.
- Các thao tác nguy hiểm (abort merge, rename branch, set upstream) cần xác nhận.
