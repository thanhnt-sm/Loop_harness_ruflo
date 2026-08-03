# 06 — Checklist, checkpoint và khắc phục sự cố

> Các checklist thực thi, checkpoint đảm bảo chất lượng, và hướng dẫn khắc phục sự cố thường gặp.

---

## 1. Checklist khởi tạo dự án

Dùng khi clone repo lần đầu hoặc setup máy mới.

| # | Hạng mục | Lệnh / Kiểm tra | Đạt |
|---|----------|-----------------|-----|
| 1 | Node.js >= 20 | `node --version` | ☐ |
| 2 | Git remote origin trỏ thanhnt-sm/Loop_harness_ruflo | `git remote -v` | ☐ |
| 3 | `hlk.config.json` tồn tại | `cat HLK/config/hlk.config.json` | ☐ |
| 4 | `hlk_enabled: true` | `jq '.hlk_enabled' HLK/config/hlk.config.json` | ☐ |
| 5 | All features = true | `jq '.features' HLK/config/hlk.config.json` | ☐ |
| 6 | `.gitignore` bao gồm `HLK/config/secrets.*` | `grep 'secrets' .gitignore` | ☐ |
| 7 | `HLK/config/secrets.env` tồn tại | `ls HLK/config/secrets.env` | ☐ |
| 8 | Không có secret trong tracked files | `git grep -n 'sk-\|ghp_\|BEGIN PRIVATE KEY'` | ☐ |
| 9 | `.claude/settings.json` gọi `hlk-hook-bridge.mjs` | `grep 'hlk-hook-bridge' .claude/settings.json` | ☐ |
| 10 | MCP server dùng `ruflo-hlk-mcp.mjs` | `grep 'ruflo-hlk-mcp' .claude/settings.json` | ☐ |
| 11 | `.gitattributes` có `merge=ours` cho HLK | `grep 'merge=ours' .gitattributes` | ☐ |
| 12 | `git status` sạch | `git status --short` | ☐ |

---

## 2. Checklist trước khi commit

| # | Hạng mục | Lệnh / Kiểm tra | Đạt |
|---|----------|-----------------|-----|
| 1 | `git status` xem file thay đổi | `git status` | ☐ |
| 2 | `git diff` xem nội dung | `git diff` | ☐ |
| 3 | Không có `.env`, `.rvf`, `.db` trong staged | `git diff --cached --name-only | grep -E '\.env|\.rvf|\.db'` | ☐ |
| 4 | Không có secret mới | `grep -R 'sk-\|ghp_\|BEGIN PRIVATE KEY' HLK/ .claude/ 2>/dev/null` | ☐ |
| 5 | `hlk-verify-integrity` pass | `node HLK/wrappers/hlk-verify-integrity.js` | ☐ |
| 6 | HLK loop hoàn thành | `node HLK/loop/hlk-loop.mjs --status` | ☐ |
| 7 | Test redact | `node HLK/wrappers/ruflo-hlk.mjs memory store -k demo -v "sk-abc..."` | ☐ |
| 8 | Commit message rõ ràng | `git commit -m "type: description"` | ☐ |

---

## 3. Checklist bảo mật (security hardening)

| # | Hạng mục | Lệnh / Kiểm tra | Đạt |
|---|----------|-----------------|-----|
| 1 | Repo GitHub private | `gh repo view --json visibility` | ☐ |
| 2 | AI training opt-out user | Vào settings Copilot của tài khoản GitHub | ☐ |
| 3 | AI training opt-out repo | Vào settings của repo `thanhnt-sm/Loop_harness_ruflo` | ☐ |
| 4 | Copilot content exclusion | Repo settings → Copilot → Content exclusion | ☐ |
| 5 | `MCP_BIND_HOST=127.0.0.1` | `grep 'MCP_BIND_HOST' ruflo/docker-compose.yml` | ☐ |
| 6 | `MCP_ENABLE_TERMINAL=false` | `grep 'MCP_ENABLE_TERMINAL' ruflo/docker-compose.yml` | ☐ |
| 7 | `MONGO_INITDB_ROOT_PASSWORD` set | `cat ruflo/.env` | ☐ |
| 8 | `MCP_AUTH_TOKEN` set nếu public | `cat ruflo/.env` | ☐ |
| 9 | Ports không expose internet | `ss -ltn | grep -E '3001|27017'` | ☐ |
| 10 | Secrets trong `HLK/config/secrets.env` không commit | `git ls-files | grep secrets.env` | ☐ |
| 11 | Không có API keys trong log | `grep -R 'sk-' HLK/logs/ .claude-flow/logs/ 2>/dev/null` | ☐ |
| 12 | HLK sanitizer hoạt động | `node HLK/wrappers/hlk-hook-bridge.mjs < test-secret.json` | ☐ |

---

## 5. Checklist triển khai Docker

| # | Hạng mục | Lệnh / Kiểm tra | Đạt |
|---|----------|-----------------|-----|
| 1 | `.env` tồn tại trong `ruflo/` | `ls ruflo/.env` | ☐ |
| 2 | `MONGO_INITDB_ROOT_PASSWORD` ngẫu nhiên | `openssl rand -base64 32` | ☐ |
| 3 | `MCP_AUTH_TOKEN` ngẫu nhiên nếu public | `openssl rand -base64 32` | ☐ |
| 4 | Docker bind localhost | `grep '127.0.0.1' ruflo/docker-compose.yml` | ☐ |
| 5 | `read_only: true` cho bridge | `grep 'read_only' ruflo/docker-compose.yml` | ☐ |
| 6 | `tmpfs` cho bridge | `grep 'tmpfs' ruflo/docker-compose.yml` | ☐ |
| 7 | MongoDB auth | `grep '\-\-auth' ruflo/docker-compose.yml` | ☐ |
| 8 | Build thành công | `docker compose -f ruflo/docker-compose.yml build` | ☐ |
| 9 | Services healthy | `docker compose ps` | ☐ |
| 10 | Không expose port ra internet | Kiểm tra firewall/Security Group | ☐ |

---

## 6. Checklist trước khi production

| # | Hạng mục | Lệnh / Kiểm tra | Đạt |
|---|----------|-----------------|-----|
| 1 | Commit sạch trên main | `git status` | ☐ |
| 2 | Tất cả test pass | `npm test` | ☐ |
| 3 | Security audit clean | `npm audit --audit-level high` | ☐ |
| 4 | `hlk-verify-integrity` pass | `node HLK/wrappers/hlk-verify-integrity.js` | ☐ |
| 5 | `hlk-loop` complete | `node HLK/loop/hlk-loop.mjs --status` | ☐ |
| 6 | Docker compose tested | `docker compose -f ruflo/docker-compose.yml up -d` | ☐ |
| 7 | MCP server reachable | `npx ruflo status` | ☐ |
| 8 | Backup `.env` và `hlk.config.json` | `cp .env .env.backup` | ☐ |
| 9 | Pin version ruflo | `hlk.config.json → ruflo_version_tested` | ☐ |
| 10 | GitHub repo private + opt-out | Xem checklist bảo mật | ☐ |

---

## 7. Checkpoint trong quy trình làm việc

### 7.1 Checkpoint 1: trước khi bắt đầu task

1. Đã search memory chưa?
2. Đã xác định topology + maxAgents chưa?
3. Đã viết acceptance criteria chưa?

### 7.2 Checkpoint 2: sau khi design

1. Design đã được lưu vào memory chưa?
2. Có rủi ro bảo mật/performance cần đánh giá?
3. Các agent tiếp theo có đủ thông tin không?

### 7.3 Checkpoint 3: sau khi implement

1. Code đã được test chưa?
2. Có secret accidentally leak?
3. `hlk-hook-bridge` không chặn nhầm?

### 7.4 Checkpoint 4: trước khi commit

1. Checklist trước commit đã hoàn thành?
2. `git diff` đã review?
3. Commit message đúng format?

---

## 8. Khắc phục sự cố (Troubleshooting)

### 8.1 Lỗi 1: `hlk-hook-bridge.mjs` không chạy

**Dấu hiệu:**
- Tool vẫn thấy secret gốc.
- Không có log `[HLK Hook]` trong stderr.

**Nguyên nhân:**
- `PreToolUse` chưa cấu hình.
- Đường dẫn `HLK/wrappers/hlk-hook-bridge.mjs` sai.
- `hlk_enabled: false`.

**Khắc phục:**

```bash
# Kiểm tra .claude/settings.json
grep -A5 'PreToolUse' .claude/settings.json

# Kiểm tra hlk.config.json
jq '.hlk_enabled' HLK/config/hlk.config.json

# Test trực tiếp
echo '{"tool_name":"Write","tool_input":{"file_path":"x.txt","content":"sk-abc123"}}' | node HLK/wrappers/hlk-hook-bridge.mjs
```

---

### 8.2 Lỗi 2: MCP server không khởi động

**Dấu hiệu:**
- Claude Code báo MCP server not reachable.
- `npx ruflo@latest mcp start` treo.

**Nguyên nhân:**
- HLK loader lỗi.
- `npx` cache hỏng.
- Network cần download.

**Khắc phục:**

```bash
# Kiểm tra MCP wrapper
node HLK/wrappers/ruflo-hlk-mcp.mjs mcp start

# Kiểm tra với HLK tắt
cp HLK/config/hlk.config.json HLK/config/hlk.config.json.bak
jq '.hlk_enabled = false' HLK/config/hlk.config.json > HLK/config/hlk.config.json.tmp
mv HLK/config/hlk.config.json.tmp HLK/config/hlk.config.json

npx -y ruflo@latest mcp start

# Khôi phục HLK
mv HLK/config/hlk.config.json.bak HLK/config/hlk.config.json
```

---

### 8.3 Lỗi 3: `bin/cli.js` không tìm thấy module

**Dấu hiệu:**
- `ERR_MODULE_NOT_FOUND`.
- `Cannot find ../dist/src/index.js`.

**Nguyên nhân:**
- Local CLI chưa build (`dist/` chưa tồn tại).

**Khắc phục:**

```bash
# Build local (nếu cần dùng local)
cd v3/@claude-flow/cli
npm install
npm run build

# Hoặc dùng npx thay vì local
npx ruflo@latest <command>
```

> Local wrapper `ruflo-hlk.mjs` cần build. Wrapper `ruflo-hlk-mcp.mjs` dùng `npx`, không cần build.

---

### 8.4 Lỗi 4: Custom hook chặn tất cả tool

**Dấu hiệu:**
- Mọi tool đều bị block với reason từ custom hook.
- `process.exit(2)` liên tục.

**Khắc phục:**

```bash
# Tạm tắt custom hooks
jq '.features.custom_hooks_injection = false' HLK/config/hlk.config.json > HLK/config/hlk.config.json.tmp
mv HLK/config/hlk.config.json.tmp HLK/config/hlk.config.json

# Đổi tên file hook
cd HLK/custom-hooks
ls */*.hook.mjs
mv agent-tool/10-block-raw-secrets.hook.mjs agent-tool/10-block-raw-secrets.hook.mjs.disabled

# Bật lại
cp HLK/config/hlk.config.json.bak HLK/config/hlk.config.json 2>/dev/null || \
  jq '.features.custom_hooks_injection = true' HLK/config/hlk.config.json > HLK/config/hlk.config.json.tmp
mv HLK/config/hlk.config.json.tmp HLK/config/hlk.config.json
```

---

### 8.5 Lỗi 5: `sanitizer` không redact

**Dấu hiệu:**
- Secret vẫn hiện trong output.
- Không có log `[HLK Sanitizer]`.

**Nguyên nhân:**
- Pattern regex sai.
- `data_sanitization` tắt.

**Khắc phục:**

```bash
# Kiểm tra config
jq '.features.data_sanitization' HLK/config/hlk.config.json

# Test sanitizer trực tiếp
node -e "import('./HLK/security/sanitizer.js').then(m => console.log(m.sanitize('sk-abc123def456')));"

# Kiểm tra patterns
jq '.security_rules.redact_patterns' HLK/config/hlk.config.json
```

---

### 8.6 Lỗi 6: Merge xung đột nội bộ

**Dấu hiệu:**
- `git merge` báo conflict.
- `.claude/settings.json` hoặc `HLK/config/hlk.config.json` bị sửa.

**Khắc phục:**

```bash
# Giữ local cho HLK và .claude/settings.json
git checkout --ours HLK/config/hlk.config.json .claude/settings.json
git add HLK/config/hlk.config.json .claude/settings.json

# Với file khác, resolve bình thường
# ...

git commit -m "chore: resolve merge conflicts"

# Verify
node HLK/wrappers/hlk-verify-integrity.js
```

---

### 8.7 Lỗi 7: HLK loader gây `SyntaxError: Unexpected token 'export'`

**Dấu hiệu:**
- Node crash khi `--import` HLK loader.
- `SyntaxError: Unexpected token 'export'`.

**Nguyên nhân:**
- Node coi file `.js` là CommonJS.
- `package.json` không có `"type": "module"` hoặc file không phải `.mjs`.

**Khắc phục:**

```bash
# Kiểm tra package.json
cat package.json | grep '"type"'

# Nếu loader là .js, đảm bảo package type=module
# Hoặc đổi loader thành .mjs
```

Hiện tại `package.json` có `"type": "module"`, loader `.js` sẽ được xử lý như ESM.

---

### 8.8 Lỗi 8: `agentdb.rvf` bị track lại

**Dấu hiệu:**
- `git status` hiển thị `agentdb.rvf` là untracked/staged.
- `git add .` định commit file này.

**Khắc phục:**

```bash
# Xóa khỏi index nếu đã staged
git rm --cached agentdb.rvf agentdb.rvf.lock

# Đảm bảo .gitignore bao gồm
echo '*.rvf' >> .gitignore
echo '*.rvf.lock' >> .gitignore

# Verify
git status --short
git check-ignore agentdb.rvf
```

---

### 8.9 Lỗi 9: `.claude/settings.json` bị ruflo update ghi đè

**Dấu hiệu:**
- Sau `npx ruflo init upgrade`, mất HLK PreToolUse.

**Khắc phục:**

```bash
# Khôi phục từ HEAD (nếu đã commit)
git checkout HEAD -- .claude/settings.json

# Hoặc khôi phục thủ công
git diff .claude/settings.json

# Thêm lại HLK PreToolUse và MCP wrapper
# Xem 03-cau-hinh-best-practice.md
```

---

### 8.10 Lỗi 10: Version mismatch

**Dấu hiệu:**
- `.claude/settings.json` `claudeFlow.version` khác `package.json`.

**Khắc phục:**

```bash
# Đồng bộ version
VERSION=$(jq -r '.version' package.json)
jq ".claudeFlow.version = \"$VERSION\"" .claude/settings.json > .claude/settings.json.tmp
mv .claude/settings.json.tmp .claude/settings.json

# Verify
jq '.claudeFlow.version' .claude/settings.json
```

---

## 9. Mã lỗi và ý nghĩa

| Mã | Ý nghĩa | Giải pháp |
|----|---------|-----------|
| `0` | Thành công / cho phép | — |
| `1` | Lỗi kỹ thuật | Xem stderr |
| `2` | Bị chặn bởi HLK / custom hook | Kiểm tra reason trong log |
| `127` | Lệnh không tìm thấy | Kiểm tra `PATH`, cài đặt Node |
| `130` | Người dùng hủy (Ctrl+C) | Chạy lại |
| `137` | Bị kill (OOM / SIGKILL) | Tăng RAM, giảm maxAgents |
| `3221225786` / `0xC000013A` | Windows kill / Ctrl+C | Chạy lại |

---

## 10. Diagnostic commands

```bash
# Tổng quan hệ thống
npx ruflo status

# Kiểm tra MCP
npx ruflo mcp status

# Kiểm tra swarm
npx ruflo swarm status

# Kiểm tra memory
npx ruflo memory status

# Kiểm tra security
npx ruflo security scan --depth full

# Kiểm tra performance
npx ruflo performance benchmark --suite all

# Kiểm tra HLK
node HLK/wrappers/hlk-verify-integrity.js
node HLK/loop/hlk-loop.mjs --status

# Kiểm tra docker
docker compose -f ruflo/docker-compose.yml ps
docker compose -f ruflo/docker-compose.yml logs mcp-bridge

# Kiểm tra process
tasklist | findstr node  # Windows
ps aux | grep node       # Linux/macOS
```
