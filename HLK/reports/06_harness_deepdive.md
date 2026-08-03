# Báo Cáo 06 — Deep-Dive Hardening: Telemetry/config.toml, Redact `ruflo-aidefence`, AgentDB Storage

> **Pipeline HLK — Prompt 06: Deep-Dive AI Coding Agent Harness Hardening & AgentDB Audit**
> Phạm vi: repo cục bộ `Loop_harness_ruflo` (package `claude-flow` v3.x, thương hiệu *Ruflo*).
> **Phương pháp**: Kế thừa Báo cáo 01/02/05, KHÔNG lặp lại — chỉ đào sâu đúng 3 mục prompt 06 yêu cầu. Mọi khẳng định đối chiếu trực tiếp `grep`/đọc file thật, dẫn `file:dòng`. Prompt gốc (06) giả định một số tính năng không có thật — xem mục 4 "Sai lệch so với giả định ban đầu".

---

## 1. Step 1 — Telemetry OTel & `config.toml` Hardening

### 1.1. OpenTelemetry gRPC/HTTP: xác nhận lại KHÔNG tồn tại (đã có ở BC05, đào sâu thêm 1 lớp)

Báo cáo 05 (dòng 42) đã kết luận không có exporter OTel thật trong `v3/@claude-flow/*/src/`. Đào sâu thêm bằng cách tìm nơi các biến `OTEL_*` **có tác dụng thật**: không tìm thấy — không có package `@opentelemetry/exporter-*` nào được `import` trong `v3/@claude-flow/*/src/`. Do đó **không có "cổng gRPC/HTTP Telemetry"** nào để tắt trong core ruflo như prompt gốc giả định.

### 1.2. `.agents/config.toml` — schema thật, đối chiếu generator + validator

File thật `.agents/config.toml` (298 dòng, gốc repo) sinh bởi `v3/@claude-flow/codex/src/generators/config-toml.ts`. Xác minh mới trong prompt này:

- **`.agents/config.toml` KHÔNG do ruflo runtime đọc để enforce sandbox/network** — nó là **file cấu hình cho OpenNAI Codex CLI** (công cụ ngoài, đóng gói riêng). Bằng chứng: `v3/@claude-flow/codex/README.md` dòng 4, 19: *"OpenAI Codex CLI Adapter for Claude Flow V3"*. `@claude-flow/codex` chỉ **generate + validate** file này (`generators/config-toml.ts`, `validators/index.ts`) — không có consumer nào trong `v3/@claude-flow/cli/src` đọc `sandbox_workspace_write.network_access` hay `security.blocked_patterns` để enforce runtime (grep 4 khoá này trong toàn `v3/` chỉ khớp `config-toml.ts` sinh chuỗi + test, **0 call site enforcement**). Ngoại lệ: `v3/@claude-flow/cli/src/services/policy-runtime.ts` dòng 155–159 CÓ đọc section `[policy]` của `.agents/config.toml`/`.codex/config.toml` bằng regex — đây là phần ruflo tự đọc (ADR-324 policy mode), phần còn lại (`sandbox_mode`, `network_access`...) do binary Codex CLI của OpenAI thực thi, ngoài tầm kiểm chứng white-box của repo này.
- Validator `v3/@claude-flow/codex/src/validators/index.ts` dòng 66–81: chỉ có 3 field **bắt buộc** (`model`, `approval_policy`, `sandbox_mode`) + enum hợp lệ (`VALID_APPROVAL_POLICIES`, `VALID_SANDBOX_MODES`, `VALID_WEB_SEARCH_MODES` — dòng 66–76). Validator **không** có danh sách section hợp lệ đóng (whitelist) — nghĩa là thêm `[observability]` sẽ **không bị lỗi** nhưng cũng **không có tác dụng gì** (không consumer nào đọc nó) → xác nhận lại kết luận BC05 dòng 43–44.

### 1.3. `strip_source_code = true` — KHÔNG tồn tại field này ở bất kỳ đâu

`grep "strip_source_code"` toàn repo (`v3/`, `plugins/`, `.agents/`) → **0 kết quả**. Đây là field prompt gốc bịa ra, không có trong generator/validator/schema.

### 1.4. File cấu hình THẬT có thể áp dụng ngay cho `.agents/config.toml`

Đối chiếu file gốc hiện tại (đã đọc trực tiếp `.agents/config.toml` dòng 1–298):

```toml
# Dòng 36 — hiện = "cached", nên siết về "disabled" nếu không cần agent tự tra cứu web
web_search = "disabled"

# Dòng 144–152 — hiện network_access = true (rủi ro: agent có thể gọi ra ngoài
# trong sandbox writable); đổi false nếu workflow không cần agent tự fetch mạng
[sandbox_workspace_write]
writable_roots = []
network_access = false
exclude_slash_tmp = false

# Dòng 158–178 — ĐÃ ĐÚNG, giữ nguyên (input_validation/secret_scanning/cve_scanning bật sẵn)
[security]
input_validation = true
path_traversal_prevention = true
secret_scanning = true
cve_scanning = true
max_file_size = 10485760
allowed_extensions = []
blocked_patterns = ["\\.env$", "credentials\\.json$", "\\.pem$", "\\.key$"]

# Dòng 207–215 — hiện destination = "stdout": đổi "file" để log KHÔNG in ra
# terminal/host log tổng hợp, giữ tại đĩa cục bộ (không phải cơ chế "OTel File
# Exporter" của prompt gốc — đây là logger nội bộ CLI, field thật duy nhất gần
# nghĩa "xuất log ra file cục bộ")
[logging]
level = "info"
format = "json"
destination = "file"
```

**Lưu ý bắt buộc**: các key trong `[sandbox_workspace_write]`/`[security]`/`web_search` chỉ có tác dụng nếu host thực thi là **OpenAI Codex CLI thật** đọc đúng `.agents/config.toml`/`.codex/config.toml` theo schema của chính nó — repo này chỉ kiểm chứng được rằng ruflo **sinh** và **validate cú pháp** file, không kiểm chứng được hành vi enforcement runtime bên trong Codex CLI (nằm ngoài mã nguồn `v3/`).

### 1.5. Kênh telemetry sản phẩm thật (funnel) — không lặp lại BC05, chỉ tóm tắt hành động

Toàn bộ chi tiết funnel (`RUFLO_FUNNEL=0`, precedence chain, endpoint) đã có đầy đủ ở BC05 mục 1–2 — áp dụng y nguyên, không có phát hiện mới trong prompt này ngoài việc xác nhận lại: `grep "https://" v3/@claude-flow/cli/src/funnel/` vẫn chỉ ra đúng 3 endpoint đã biết.

---

## 2. Step 2 — Redact Config Cho `ruflo-aidefence`

### 2.1. Xác nhận lại: không có JSON config `pii_scanner` (đã có ở BC05) — đào sâu cơ chế redact THẬT

Không lặp mô hình 3-gate (đã mô tả kỹ ở BC05 mục 4, BC02 mục 3.3). Điều tra mới trong prompt này: **`ruflo-aidefence` (6 MCP tool) chỉ PHÁT HIỆN (detect/scan/is_safe/has_pii), KHÔNG tự động REDACT nội dung** — xác nhận bằng đọc trực tiếp `v3/@claude-flow/cli/src/mcp-tools/security-tools.ts`:
- `aidefenceScanTool` (dòng 134–136), `aidefenceIsSafeTool` (dòng 450–500), `aidefenceHasPIITool` (dòng 505+) đều trả về JSON `{safe, promptSafe, piiPresent, threats...}` — **không có tham số/field nào trả về chuỗi đã redact**. Agent phải **tự quyết định** làm gì với kết quả (advisory, đúng như BC02 mục 3.3 đã chỉ ra).

### 2.2. Phát hiện MỚI: hàm `redactPII()` THẬT, có sẵn, làm đúng việc "xóa bỏ/thay thế API key, connection string" — nhưng chỉ chạy trong luồng `transfer export`, KHÔNG chạy trong luồng `memory store`

File `v3/@claude-flow/cli/src/transfer/anonymization/index.ts`:
- Dòng 17–26: `PII_PATTERNS` — regex thật cho `email`, `phone`, `ipv4`, `ipv6`, `apiKey` (`/\b(sk-|pk-|api[_-]?key[_-]?)[a-zA-Z0-9]{20,}\b/gi`), `jwt`, `homePath`, `windowsPath`.
- Dòng 31–40: `REDACTIONS` — bảng thay thế (`apiKey → '[REDACTED_API_KEY]'`, `jwt → '[REDACTED_JWT]'`, `email → user_<hash8>@example.com`...).
- Dòng 103–116: `export function redactPII(content: string): string` — áp từng pattern + thay thế, trả về chuỗi đã redact **thật sự** (không chỉ gắn cờ).
- Nơi gọi: `v3/@claude-flow/cli/src/transfer/export.ts` dòng 29, 38–39 (`redactPii = true` mặc định khi export pattern ra IPFS/CFP format) và `transfer/deploy-seraphine.ts` dòng 172, 188.
- **Không có** connection-string pattern (`mongodb://`, `postgresql://`...) trong `PII_PATTERNS` này — khác với HLK `hlk.config.json` dòng 33 (`(mongodb\+srv|postgresql|mysql)://...`) vốn đã có sẵn pattern này.
- **Không có nơi nào gọi `redactPII()` trước khi ghi AgentDB** (`bridgeStoreEntry()` — đã xác nhận lại bằng grep `redactPII|redact` trong `memory-bridge.ts` → 0 kết quả) — khớp với lỗ hổng V1 của BC02.

### 2.3. Đề xuất áp dụng ngay: dùng lại `redactPII()` làm lớp redact trước khi lưu (không sửa core)

Vì `memory-bridge.ts` không có middleware chính thức (BC01 dòng 100, BC02 V1), và `redactPII()` đã có sẵn logic đúng — cách áp dụng KHÔNG sửa core: viết một CLI wrapper mới trong `HLK/` gọi `@claude-flow/cli`'s `transfer` module làm sanitizer trước khi gọi `memory store`, hoặc (khuyến nghị mạnh hơn) mở rộng `HLK/security/sanitizer.js` hiện có để **thêm đúng bộ pattern PII_PATTERNS này** (email/phone/ip/apiKey/jwt/path) cộng với các pattern hiện có (connection string, private key), rồi nối dây qua hook `PreToolUse`/`post-edit` (đã xác định ở BC01 mục 4, hàng #3) — vì `HLK/security/sanitizer.js` hiện có **0 call site** vào `v3/` (BC02 V9), đây chính là chỗ cần vá trong prompt 07.

```json
// Bổ sung vào HLK/config/hlk.config.json -> security_rules.redact_patterns
// (đối chiếu 1:1 với PII_PATTERNS thật trong transfer/anonymization/index.ts:17-26)
{
  "security_rules": {
    "redact_patterns": [
      "sk-[a-zA-Z0-9]{32,}",
      "ghp_[a-zA-Z0-9]{36}",
      "\\b(sk-|pk-|api[_-]?key[_-]?)[a-zA-Z0-9]{20,}\\b",
      "\\beyJ[a-zA-Z0-9_-]*\\.eyJ[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*\\b",
      "(?i)password\\s*=\\s*['\"]?[^'\"\\s]+",
      "(?i)(mongodb\\+srv|postgresql|mysql)://[^\\s]+",
      "-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ],
    "redact_replacement": "[REDACTED]"
  }
}
```

### 2.4. Kênh phòng thủ nâng cao đã có, chỉ cần BẬT: `CLAUDE_FLOW_STRICT_GUARDRAIL`

Không lặp chi tiết (đã có đủ ở BC02 mục 3.1) — hành động cụ thể: đặt `CLAUDE_FLOW_STRICT_GUARDRAIL=true` để bật `applyContentBoundaryGuardrail()` (`v3/@claude-flow/cli/src/mcp-client.ts` dòng 295) — mặc định tắt. Đây là công tắc **có thật, một dòng env**, khác hẳn `pii_scanner.policy=REDACT` (không tồn tại) mà prompt gốc đề xuất.

---

## 3. Step 3 — Cấu Trúc Lưu Trữ AgentDB & Chống Đồng Bộ Ngầm

### 3.1. Có **HAI file/định dạng khác nhau**, cả hai đều tồn tại thật trên đĩa — prompt gốc gộp chung thành một `agentdb.rvf` là sai

| File | Vị trí | Định dạng | Ai ghi | Vai trò thật |
|---|---|---|---|---|
| `agentdb.rvf` (+ `.lock`) | **Gốc repo** (đã xác nhận tồn tại: 162 bytes + magic bytes `RVF\0`) | Binary nhị phân riêng (RVF = "RuVector Format", ADR-057) | Module native `ruvector` (Rust/NAPI) qua `v3/@claude-flow/cli/src/ruvector/vector-db.ts` | **Default storage path khi KHÔNG truyền `storagePath` tường minh** cho `VectorDBClass` — dòng 190–197 (comment): *"the native ruvector DB takes an exclusive file lock... Without an explicit path it defaults to a shared file in the CWD (e.g. agentdb.rvf)"* |
| `agentdb-memory.db` | `.swarm/` (cạnh `memory.db`) | **SQLite plaintext chuẩn** (không phải RVF) | `@claude-flow/memory`'s `ControllerRegistry` qua `better-sqlite3`, gọi từ `memory-bridge.ts` dòng 117–121 | File **thật sự** được `memory store`/`memory search`/hooks `post-edit` dùng hằng ngày — đã mô tả ở BC02 mục 2.2 (KHÔNG bao giờ mã hóa dù bật `CLAUDE_FLOW_ENCRYPT_AT_REST=1`) |

→ **Kết luận quan trọng**: lệnh `ruflo memory store/search` (đường dẫn CLI/MCP thực tế mà agent dùng) đi qua `agentdb-memory.db` (SQLite), KHÔNG phải `agentdb.rvf`. File `agentdb.rvf` chỉ được native `ruvector` module tạo ra khi có code gọi `createVectorDB()` **mà không set `storagePath`** — bằng chứng khác: `v3/@claude-flow/cli/src/services/policy-runtime.ts` dòng 137–144 liệt kê cả 2 file này trong `detectLegacyCapabilities()` như 2 "candidate" độc lập, và `mcp-tools/system-tools.ts` dòng 324–332 cũng liệt kê chúng riêng biệt trong health-check.

### 3.2. Có phải HNSW thật không? — Câu trả lời chia 2 phần, khác giả định của prompt gốc

- **Thiết kế/tài liệu**: `ADR-057-rvf-native-storage-backend.md` (status **"Proposed"**, dòng 5) mô tả kiến trúc segment thật: `VEC_SEG` (vector, hỗ trợ lượng tử hoá fp32/fp16/int8), `INDEX_SEG` (3-layer HNSW), `KV_SEG`, `LOG_SEG` (dòng 113–123) — đây là **thiết kế cho tương lai** của backend `.rvf` dùng chung cho `shared`/`memory`/`embeddings`, KHÔNG phải mô tả về đúng file `agentdb.rvf` gốc repo (file đó chỉ là do `ruvector` NAPI tự sinh, dùng schema riêng của thư viện `ruvector`, không phải schema ADR-057).
- **Đường dẫn thực thi thật** (`bridgeSearchEntries()`, dòng 1022–1194 và `bridgeSearchHNSW()`, dòng 1704–1772 trong `memory-bridge.ts`): **KHÔNG dùng HNSW library nào cả** — cả hai hàm này chạy `SELECT ... FROM memory_entries LIMIT 1000` (hoặc `LIMIT 10000` với `bridgeSearchHNSW`) rồi tính **cosine similarity brute-force bằng JavaScript thuần** (`cosineSim()`, dòng 1750–1751) + BM25 thủ công (dòng 1103–1108). Tên hàm `bridgeSearchHNSW` là **misnomer** — comment dòng 1701 tự gọi nó là *"HNSW-equivalent search"*, tức mô phỏng chức năng chứ không phải chỉ mục HNSW thật.
- **HNSW thật có tồn tại** ở lớp khác: `v3/@claude-flow/memory/src/agentdb-backend.ts` dòng 1–8, 42–61, 79–139 — class `AgentDBBackend` có `vectorBackend: 'auto' | 'ruvector' | 'hnswlib'`, dynamic-import package `agentdb` (dòng 52–55, optional dependency) và cấu hình `hnswM/hnswEfConstruction/hnswEfSearch`. Đây là backend độc lập, **không phải** con đường mà `memory-bridge.ts` (bridge dùng cho CLI `memory store/search`) đi qua — `memory-bridge.ts` khởi tạo `ControllerRegistry` với `vectorBackend: 'auto'` (dòng 186) nhưng cách đọc dữ liệu thực tế (`bridgeSearchEntries`) vẫn là truy vấn SQL + JS brute-force như trên, không gọi các API HNSW của `agentdb-backend.ts`.

→ **Sai lệch với prompt gốc**: HNSW/vector-index THẬT tồn tại trong codebase (`agentdb-backend.ts`, ADR-057, native `ruvector`), nhưng **con đường CLI/MCP `memory search` mà agent dùng hằng ngày lại KHÔNG dùng chỉ mục HNSW** — nó brute-force trên chính bảng SQLite plaintext `agentdb-memory.db`. Rủi ro rò rỉ vì vậy nằm ở SQL/JS thô, không phải ở cấu trúc chỉ mục vector.

### 3.3. Phát hiện MỚI, nghiêm trọng: `agentdb.rvf` + `agentdb.rvf.lock` **ĐÃ ĐƯỢC COMMIT VÀO GIT**, không nằm trong `.gitignore`

Đây là bằng chứng runtime, không phải suy luận:

```
$ git ls-files -- agentdb.rvf agentdb.rvf.lock
agentdb.rvf
agentdb.rvf.lock

$ git log -1 --format="%H %ai %s" -- agentdb.rvf
c29eab8 2026-08-03 chore: initial commit with HLK v2.0.0 layer ...

$ grep -c "rvf\|agentdb" .gitignore
0
```

- Root `.gitignore` **có** exclude `.swarm/` (dòng 79–81, 136) — tức `agentdb-memory.db`/`memory.db` (bảng dữ liệu chính, chứa `content` thô — BC02 V1/V2) **được** loại khỏi git.
- Nhưng root `.gitignore` **KHÔNG có bất kỳ pattern nào** cho `agentdb.rvf`/`agentdb.rvf.lock` — và 2 file này **đã bị commit thật** vào lần commit khởi tạo repo HLK (`c29eab8`).
- **Đây chính là "đồng bộ ngầm ra ngoài" cụ thể và có thật nhất tìm được trong toàn bộ audit**: nếu file `agentdb.rvf` từng có dữ liệu thật tại thời điểm `git add`/`git commit`, nó đã đi thẳng vào lịch sử git — và sẽ **push đi cùng mọi lần `git push`** tới bất kỳ remote. Đây là kênh rò rỉ **git-based**, khác hẳn "federation plugin" mà prompt gốc ngờ vực.

### 3.4. "Federation" — plugin CÓ THẬT, nhưng KHÔNG cài mặc định trong repo này; không phải cơ chế đồng bộ AgentDB tự động

`grep -ri federation plugins/` cho ra **2 plugin thật**: `plugins/ruflo-federation/` và `plugins/ruflo-bbs-federation/`. Đọc `plugins/ruflo-federation/README.md`:
- Dòng 1–3, 90–94: đây là lớp **truyền tin (messaging) giữa các cài đặt ruflo khác nhau** (cross-installation), có namespace AgentDB riêng tên `federation` (dùng cho peer registry, trust score, audit log, message receipt — KHÔNG đồng bộ toàn bộ `memory_entries`).
- Dòng 14, 65–69: yêu cầu **mTLS + ed25519 handshake** trước khi trao đổi bất kỳ dữ liệu nào; runtime thật nằm ở package ngoài `@claude-flow/plugin-agent-federation` (`npx -y -p ...`), **không phải plugin tự chạy nền**.
- Dòng 15, 76–88: có PII pipeline riêng (14 loại, chính sách BLOCK/REDACT/HASH/PASS theo trust-level) — nhưng BC02 mục 3.4 đã chỉ ra `ADR165-OPEN-01` (`v3/@claude-flow/security/src/CVE-REMEDIATION.ts` dòng 420–440): chính Ruflo tự khai là PII scan **chưa được wire** vào `plugin-agent-federation` thật (`remediationStatus: 'pending'`).
- **Xác nhận trong prompt này**: `.claude-flow/plugins/installed.json` **không tồn tại** trong repo hiện tại → federation KHÔNG được cài/kích hoạt mặc định; phải chạy tường minh `/plugin install ruflo-federation@ruflo` rồi `/federation init`/`join` mới có nguy cơ. Đây là điểm prompt gốc nêu đúng hướng nghi vấn ("plugin federation") nhưng đánh giá sai mức độ rủi ro mặc định (KHÔNG bật sẵn, không tự động sync file DB).

### 3.5. Cách chặn "đồng bộ ngầm" — checklist áp dụng ngay (thứ tự ưu tiên theo bằng chứng thật)

```bash
# 1) VÁ NGAY — gỡ agentdb.rvf/.lock khỏi git history tracking hiện tại
#    (file đã bị track — thêm gitignore KHÔNG đủ, phải rm --cached)
git rm --cached agentdb.rvf agentdb.rvf.lock

# 2) Thêm vào .gitignore gốc (hiện có .swarm/ ở dòng 79-81,136 nhưng thiếu 2 dòng này)
echo "agentdb.rvf" >> .gitignore
echo "agentdb.rvf.lock" >> .gitignore
echo "*.rvf" >> .gitignore
echo "*.rvf.lock" >> .gitignore

# 3) Không cài plugin federation nếu không có nhu cầu multi-instance thật
#    (mặc định đã KHÔNG cài — chỉ cần KHÔNG chạy các lệnh sau nếu không cần)
#    /plugin install ruflo-federation@ruflo   <-- KHÔNG chạy nếu không cần

# 4) Di chuyển .swarm/ ra khỏi mọi thư mục có OS-level cloud sync
#    (OneDrive/Dropbox/Google Drive) — ruflo tôn trọng biến này (memory-initializer.ts:109)
CLAUDE_FLOW_MEMORY_PATH="D:\ruflo-local-only\.swarm"

# 5) Bật mã hóa at-rest cho phần CÓ hỗ trợ (sessions/terminals — theo BC02 V2,
#    KHÔNG che được agentdb-memory.db, nhưng vẫn nên bật cho phần còn lại)
CLAUDE_FLOW_ENCRYPT_AT_REST=1

# 6) Kiểm chứng không còn gì "rò" qua git trước mỗi lần push
git status --porcelain | Select-String "\.rvf|\.db$|agentdb"
git log --all --oneline -- "*.rvf" "*.db"   # xác nhận không còn commit nào chứa DB
```

**Giới hạn cần nêu rõ**: bước 4 (`CLAUDE_FLOW_MEMORY_PATH`) chỉ dời được `agentdb-memory.db`/`memory.db` (đi qua `getMemoryRoot()`), **KHÔNG dời được** `agentdb.rvf` ở gốc repo vì file đó do native `ruvector` module tự quyết định `storagePath` mặc định theo `process.cwd()` (`vector-db.ts` dòng 190–201) chỉ khi code gọi không truyền `storagePath` tường minh — cách chặn chắc chắn nhất vẫn là bước 1+2 (gitignore + rm --cached), không phụ thuộc việc file được ghi ở đâu.

---

## 4. Sai Lệch So Với Giả Định Ban Đầu (Prompt 06 Gốc)

| Giả định trong prompt gốc | Thực tế trong code | Bằng chứng |
|---|---|---|
| "Cổng gRPC/HTTP Telemetry của OpenTelemetry" cần tắt trong `config.toml`/`.env` | Không có exporter OTel nào trong core ruflo để tắt (đã xác nhận lại BC05) | Không tìm thấy `@opentelemetry/exporter-*` import trong `v3/@claude-flow/*/src/` |
| Flag `strip_source_code = true` trong `config.toml` | Field này **không tồn tại** ở bất kỳ đâu trong schema | `grep "strip_source_code"` toàn repo → 0 kết quả |
| `.agents/config.toml` là file ruflo tự enforce sandbox/network | Đây là file cấu hình cho **OpenAI Codex CLI** (bên ngoài); ruflo chỉ generate + validate cú pháp, chỉ tự đọc mỗi section `[policy]` | `v3/@claude-flow/codex/README.md:4,19`; `policy-runtime.ts:155-159`; 0 call site enforcement cho `sandbox_workspace_write`/`security` trong `cli/src` |
| Plugin `ruflo-aidefence` có "file JSON" để cấu hình redact | Không có JSON config; 6 MCP tool chỉ **phát hiện**, không tự redact; hàm redact thật (`redactPII()`) nằm ở module `transfer` (export), không liên quan `ruflo-aidefence` | `security-tools.ts` (không field redact trong output); `transfer/anonymization/index.ts:103-116` |
| `agentdb.rvf` là MỘT file, lưu code dạng vector dựa trên HNSW, cần chặn "đồng bộ ngầm" qua mạng/plugin | Có **HAI** file khác nhau (`agentdb.rvf` từ native `ruvector`, `agentdb-memory.db` từ SQLite/`better-sqlite3`); đường dẫn `memory search` thật dùng brute-force JS, không phải HNSW; rủi ro "đồng bộ ngầm" thật nằm ở **git tracking** (đã bị commit), không phải ở "federation plugin" tự động | `memory-bridge.ts:117-121,1704-1772`; `git ls-files -- agentdb.rvf` → tracked; `.gitignore` không có pattern `*.rvf` |
| Plugin "federation" đồng bộ AgentDB tự động, cần chặn | Plugin `ruflo-federation` có thật nhưng KHÔNG cài mặc định, cần cài + init/join tường minh, có PII gate riêng (dù có lỗ theo ADR165-OPEN-01) | `plugins/ruflo-federation/README.md`; `.claude-flow/plugins/installed.json` không tồn tại trong repo |

---

## Learnings

- **File nhị phân "trông vô hại" (162 byte) vẫn phải audit bằng git, không chỉ bằng nội dung**: `agentdb.rvf` chỉ nặng 162 byte lúc kiểm tra nhưng việc nó đã bị `git add`/commit là rủi ro kiến trúc — dữ liệu tương lai ghi vào cùng path sẽ tự động "kế thừa" trạng thái tracked đó cho tới khi ai đó chủ động `git rm --cached`. Luôn kiểm `git ls-files` cho mọi file trạng thái/cache trước khi kết luận "đã được gitignore".
- **Hai file trùng tên miền (`agentdb.rvf` vs `agentdb-memory.db`) dễ gây audit nhầm mục tiêu**: nếu chỉ đọc theo tên biến trong 1 file code sẽ lầm tưởng chỉ có một kho lưu trữ; phải trace theo *đường gọi thực thi* (`bridgeSearchEntries`/`bridgeStoreEntry` — hàm nào thực sự chạy khi gõ `memory store`) chứ không phải theo tên gợi nhớ ("HNSW", "AgentDB") trong comment/docstring.
- **Tên hàm không phải bằng chứng hành vi**: `bridgeSearchHNSW()` không dùng HNSW — đọc docstring/comment ("HNSW-equivalent") và đối chiếu với thân hàm (SQL LIMIT + cosine JS thuần) là bước bắt buộc, không được suy diễn từ tên hàm hay tên ADR liên quan.
- **Một file cấu hình (`.agents/config.toml`) có thể phục vụ HAI hệ thống khác nhau**: ruflo generate/validate cú pháp, nhưng phần lớn key enforcement runtime (`sandbox_mode`, `network_access`) thuộc về binary Codex CLI bên ngoài — trước khi viết hướng dẫn "sửa key X để chặn Y", phải xác định ai là consumer thật của key đó, nếu không sẽ đưa ra "cấu hình ma" giống các field mà prompt gốc từng giả định sai (đã bị BC05 chỉ ra 1 lần, prompt 06 lặp lại kiểu sai này ở field khác).
- **Mức độ rủi ro thật của một plugin phải kiểm bằng trạng thái cài đặt, không chỉ bằng tài liệu tính năng**: `ruflo-federation` đọc README có vẻ đáng ngại (mTLS, Byzantine consensus, PII pipeline) nhưng vì `.claude-flow/plugins/installed.json` không tồn tại, nó chưa hề được kích hoạt trong repo — luôn kiểm trạng thái cài đặt thật trước khi xếp hạng severity.
- **Chức năng redact "làm đúng việc" có thể nằm ở một module không liên quan tên gọi**: `redactPII()` (dùng đúng regex API-key/JWT/email cần cho prompt gốc) nằm trong `transfer/anonymization/`, không nằm trong `ruflo-aidefence` hay `security/` — khi tìm "cơ chế redact có sẵn để tái sử dụng", nên grep theo hành vi (`function redact`, bảng thay thế) thay vì theo tên plugin/thư mục có vẻ liên quan nhất.
- **Bằng chứng runtime (`git log`, `git ls-files`) mạnh hơn bằng chứng tĩnh (đọc `.gitignore`)**: chỉ đọc `.gitignore` sẽ bỏ sót trường hợp file đã bị track TRƯỚC khi có rule ignore — luôn chạy `git ls-files <path>` để xác nhận trạng thái tracked thật sự, đặc biệt với các file trạng thái/cache dễ bị coi là "chắc đã ignore rồi".
