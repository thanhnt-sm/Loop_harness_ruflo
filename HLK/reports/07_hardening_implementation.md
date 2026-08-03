# Báo Cáo 07 — Triển Khai Hardening Ruflo (Tắt Telemetry, Config AIDefence & Bảo Vệ AgentDB)

> **Pipeline HLK — Prompt 07: Ruflo Hardening Implementation**
> Phạm vi: repo cục bộ `Loop_harness_ruflo` (package `claude-flow` v3.34.0, thương hiệu *Ruflo*).
> Vai trò: Security Engineer / Implementer — thực thi các đề xuất từ Báo cáo 03 (kiến trúc 3 tầng), Báo cáo 05 (data leak hardening), Báo cáo 06 (telemetry/AgentDB audit).

---

## 1. Tóm Tắt Điều Hành

Đã triển khai HLK v3.0.0 với 3 tầng bảo vệ độc lập, bật/tắt được:

| Tầng | Cơ chế | File chính | Bù đắp lỗ hổng |
|---|---|---|---|
| **1. Process preload** | `NODE_OPTIONS="--import=.../hlk-loader.js"` trước `bin/cli.js` | `HLK/wrappers/hlk-loader.js` | V1/V9 — secret trong CLI argv bị redact trước khi vào Ruflo; telemetry bị chặn bằng env. |
| **2. Agent runtime hook** | PreToolUse/PostToolUse gọi `hlk-hook-bridge.mjs` | `HLK/wrappers/hlk-hook-bridge.mjs` | V4/V1 — redact tool input cho Write/Edit; chặn Bash/ApplyPatch nếu chứa secret. |
| **3. Custom business logic** | `HLK/custom-hooks/<phase>/*.hook.mjs` | `HLK/custom-hooks/` | Kênh mở rộng riêng, không đụng core. |

Ngoài ra đã:
- Xóa `agentdb.rvf`/`agentdb.rvf.lock` khỏi git tracking (`git rm --cached`).
- Bổ sung `.gitignore` ngăn mọi `*.rvf` bị commit.
- Cải tiến script upstream sync thêm backup + dry-run + log.
- Cập nhật `hlk-verify-integrity.js` kiểm tra toàn bộ file/thư mục mới.

---

## 2. Danh Sách Thay Đổi

### 2.1. File mới

| File | Mục đích |
|---|---|
| `HLK/wrappers/hlk-hook-bridge.mjs` | Agent runtime hook: redact/chặn tool input |
| `HLK/wrappers/ruflo-hlk.mjs` | Launcher Node để chạy Ruflo với HLK preload |
| `HLK/wrappers/ruflo-hlk.ps1` | Launcher PowerShell |
| `HLK/wrappers/ruflo-hlk.cmd` | Launcher Command Prompt |
| `HLK/custom-hooks/README.md` | Hợp đồng và quy ước custom hook |
| `HLK/custom-hooks/pre-argv/.gitkeep` | Giữ thư mục trong git |
| `HLK/custom-hooks/post-sanitize/.gitkeep` | Giữ thư mục trong git |
| `HLK/custom-hooks/agent-tool/.gitkeep` | Giữ thư mục trong git |
| `HLK/config/secrets.env.example` | Template cho file secrets local |
| `HLK/reports/07_hardening_implementation.md` | Báo cáo này |

### 2.2. File sửa đổi

| File | Thay đổi chính |
|---|---|
| `HLK/wrappers/hlk-loader.js` | Viết lại v3.0.0: no-op khi tắt, top-level await, sanitize `process.argv`, nạp custom hooks, log ra stderr |
| `HLK/wrappers/hlk-verify-integrity.js` | Thêm kiểm tra file mới, `.gitignore`, git tracking `*.rvf` |
| `HLK/security/sanitizer.js` | Comment tiếng Việt, hỗ trợ `(?i)`, pattern rõ ràng |
| `HLK/security/vault-bridge.js` | Comment tiếng Việt, cache, ưu tiên process.env |
| `HLK/config/hlk.config.json` | Version 3.0.0, thêm pattern API key/JWT/private key |
| `.gitignore` | Thêm rule `*.rvf`, `*.rvf.lock`, `agentdb.rvf` |
| `.gitattributes` | Thêm `HLK/loop/**` và `HLK/reports/**` merge=ours |

### 2.3. Hành động git

```bash
git rm --cached agentdb.rvf agentdb.rvf.lock
```

Hai file nhị phân này đã bị xóa khỏi index git, không còn tracking.

---

## 3. Chi Tiết Triển Khai

### 3.1. `hlk-loader.js` v3.0.0

#### Nguyên tắc thiết kế

1. **No-op tuyệt đối khi tắt**: khi `hlk_enabled=false`, không in log, không set env, không import, không sửa `process.argv`.
2. **Top-level await**: đảm bảo mọi bước preload hoàn tất trước khi Ruflo chạy.
3. **Log ra stderr**: tránh phá khung JSON-RPC khi Ruflo chạy ở chế độ MCP server.
4. **Static export ở cuối file**: ESM không cho phép `export` trong block `if/else`.

#### Cấu trúc code

```
Bước 1: loadConfig()
Bước 2: Khai báo public API mặc định (no-op)
Bước 3: Nếu hlk_enabled === true:
  3.1 log() ra stderr
  3.2 set telemetry env (chỉ nếu chưa set)
  3.3 load sanitizer, vault
  3.4 load custom hooks theo phase
  3.5 chạy pre-argv hooks
  3.6 sanitize process.argv (-v, --value, --data, --content)
  3.7 chạy post-sanitize hooks
  3.8 log hoàn tất
  3.9 gán lại public API
Bước 4: export public API
```

#### Xử lý `process.argv`

Ví dụ kết quả thực tế (đã test):

```
IN  argv:  [..., "--value", "sk-abc123def456ghijk789lmno01234567"]
OUT argv:  [..., "--value", "[REDACTED]"]
```

**Giới hạn quan trọng**: chỉ phủ đường CLI trực tiếp. Đường MCP stdio (JSON-RPC qua stdin) **không** đi qua `process.argv`, nên tầng 2 (`hlk-hook-bridge.mjs`) bắt buộc phải tồn tại song song.

### 3.2. `hlk-hook-bridge.mjs`

#### Cơ chế

- Nhận JSON từ stdin.
- Trích `tool_name` và `tool_input`.
- Với `Bash`/`ApplyPatch`: nếu chứa secret → `exit 2` (chặn).
- Với `Write`/`Edit`/`tool` khác: redact nội dung rồi trả JSON qua stdout.
- Hỗ trợ `HLK/custom-hooks/agent-tool/*.hook.mjs`.

#### Ví dụ kết quả thực tế

```bash
# Bash chứa secret → bị chặn
echo '{"tool_name":"Bash","tool_input":{"command":"curl -H \"Authorization: Bearer sk-abc...\""}}' | node HLK/wrappers/hlk-hook-bridge.mjs
# exit: 2
# stderr: [HLK Hook] 🚫 Tool Bash chứa dữ liệu nhạy cảm — bị chặn để tránh rò rỉ

# Write chứa secret → bị redact
echo '{"tool_name":"Write","tool_input":{"content":"my api_key=sk-abc..."}}' | node HLK/wrappers/hlk-hook-bridge.mjs
# stdout: {"tool_name":"Write","tool_input":{"content":"my [REDACTED]"}}
```

### 3.3. `ruflo-hlk` launcher

Tự động set `NODE_OPTIONS` trỏ đến `hlk-loader.js` rồi spawn `node bin/cli.js <args>`.

```bash
# Linux/Mac/Windows với Node
node HLK/wrappers/ruflo-hlk.mjs memory store -k demo -v "sk-..."

# Windows PowerShell
.\HLK\wrappers\ruflo-hlk.ps1 memory store -k demo -v "sk-..."

# Windows Command Prompt
.\HLK\wrappers\ruflo-hlk.cmd memory store -k demo -v "sk-..."
```

### 3.4. Custom hooks

Quy ước tên: `HLK/custom-hooks/<phase>/<order>-<mo-ta>.hook.mjs`

| phase | Thứ tự chạy | Context |
|---|---|---|
| `pre-argv` | Sau telemetry, trước sanitize argv | `{ argv }` |
| `post-sanitize` | Sau sanitize argv | `{ argv }` |
| `agent-tool` | Trong `hlk-hook-bridge.mjs` | `{ toolName, toolInput, input }` |

Hợp đồng trả về:

```js
{ value?: any, block?: boolean, reason?: string }
```

- `block: true` → dừng với exit code 2.
- Lỗi kỹ thuật → bỏ qua hook.

### 3.5. Cập nhật `sanitizer.js` và `vault-bridge.js`

- `sanitizer.js`: thêm pattern JWT, API key dạng `sk-|pk-|api_key_`, private key multiline.
- `vault-bridge.js`: ưu tiên `process.env` > `HLK/config/secrets.env` > `defaultValue`.

### 3.6. Xử lý `agentdb.rvf` tracking

```bash
$ git ls-files -- agentdb.rvf agentdb.rvf.lock
# (rỗng)
```

`.gitignore` đã bổ sung:

```gitignore
agentdb.rvf
agentdb.rvf.lock
*.rvf
*.rvf.lock
```

### 3.7. Telemetry overrides

`hlk.config.json`:

```json
{
  "telemetry_overrides": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "0",
    "DISABLE_TELEMETRY": "1",
    "OTEL_TRACES_EXPORTER": "none",
    "OTEL_METRICS_EXPORTER": "file",
    "OTEL_LOGS_EXPORTER": "file",
    "LANGSMITH_TRACING": "false",
    "LANGFUSE_TRACING": "false"
  }
}
```

Nguyên tắc: chỉ set env nếu chưa tồn tại.

---

## 4. Kiểm Thử

### 4.1. HLK integrity

```bash
node HLK/wrappers/hlk-verify-integrity.js
```

**Kết quả**: `🎉 All HLK integrity checks PASSED!`

### 4.2. Loader bật

```bash
$env:NODE_OPTIONS="--import=file://D:/.../HLK/wrappers/hlk-loader.js"
node -e "console.log(process.argv)" --value "sk-abc123..."
```

**Kết quả**: `process.argv` chứa `[REDACTED]`; log `[HLK]` xuất hiện trên `stderr`.

### 4.3. Loader tắt

Sửa `hlk_enabled` thành `false` trong `hlk.config.json`, chạy lại.

**Kết quả**: `stderr` rỗng; `process.argv` giữ nguyên secret.

### 4.4. Hook bridge

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"curl -H \"Authorization: Bearer sk-abc...\""}}' | node HLK/wrappers/hlk-hook-bridge.mjs
# exit 2

echo '{"tool_name":"Write","tool_input":{"content":"my api_key=sk-abc..."}}' | node HLK/wrappers/hlk-hook-bridge.mjs
# stdout: {"tool_name":"Write","tool_input":{"content":"my [REDACTED]"}}
```

---

## 5. Giới Hạn Đã Biết

1. **Tầng 1 (argv) không phủ MCP stdio**: payload JSON-RPC không nằm trong `process.argv`. Tầng 2 (`hlk-hook-bridge.mjs`) bắt buộc phải được cấu hình trong `.claude/settings.json`.
2. **Bash/ApplyPatch bị chặn nếu chứa secret**: thiết kế an toàn, nhưng có thể gây false positive nếu command chứa string trông giống secret (ví dụ ví dụ học tập). Người dùng có thể điều chỉnh pattern hoặc thêm custom hook whitelist.
3. **Ruflo CLI `bin/cli.js` hiện chưa build**: `npx claude-flow swarm run` lỗi vì thiếu `dist/src/index.js`. HLK loader vẫn hoạt động khi `bin/cli.js` được build lại.
4. **Write/Edit redact nội dung file**: file đích sẽ chứa `[REDACTED]` thay vì secret. Đây là hành vi mong muốn, nhưng người dùng phải kiểm tra kết quả.
5. **Custom hook lỗi kỹ thuật bị bỏ qua**: fail-open, không làm sập CLI.

---

## 6. Hướng Dẫn Kích Hoạt

### Bước 1: Cấu hình `.claude/settings.json` (tùy chọn, cho tầng 2)

```json
{
  "PreToolUse": [
    "node HLK/wrappers/hlk-hook-bridge.mjs"
  ],
  "PostToolUse": [
    "node HLK/wrappers/hlk-hook-bridge.mjs"
  ]
}
```

### Bước 2: Chạy Ruflo qua launcher

```bash
# PowerShell
.\HLK\wrappers\ruflo-hlk.ps1 memory store -k demo -v "sk-..."
```

Hoặc set `NODE_OPTIONS` thủ công.

---

## Learnings

- **ESM `export` không thể nằm trong block `if/else`**: lỗi `SyntaxError: Unexpected token 'export'` khi lần đầu viết `if (disabled) { export ... }` buộc phải tái cấu trúc thành: khai báo `let` cho API, gán lại trong `if`, rồi `export` ở top-level cuối file.
- **Top-level await trong `--import` module là cơ chế đồng bộ hợp lệ**: Node.js đảm bảo module preload evaluate xong mọi `await` trước khi entry module chạy — dùng để nạp sanitizer/vault/hooks đồng bộ trước khi Ruflo parse argv.
- **Redact Bash command và chạy nó có thể nguy hiểm hơn chặn**: quyết định chặn `Bash`/`ApplyPatch` nếu chứa secret (thay vì redact rồi chạy) là lựa chọn an toàn; chỉ redact `Write`/`Edit` vì nội dung file được kiểm soát.
- **Git tracking của file `.rvf` phải kiểm bằng `git ls-files`**: `.gitignore` chỉ ngăn file *mới* được track; file đã track trước đó cần `git rm --cached`.
- **Log preload phải ra `stderr`**: nếu ra `stdout` sẽ làm lẫn khung JSON-RPC khi Ruflo chạy MCP server.
- **Pattern `(?i)` trong regex JavaScript không hỗ trợ trực tiếp**: cần xử lý trong `sanitizer.js` bằng cách loại bỏ `(?i)` và thêm flag `i`.
