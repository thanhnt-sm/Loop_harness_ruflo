#!/usr/bin/env node
/**
 * HLK Hook Bridge — Agent Runtime Hook
 * ======================================
 * Mục đích tổng thể:
 *   Chạy như một external hook từ PreToolUse/PostToolUse trong
 *   `.claude/settings.json`. Nhận JSON từ stdin, kiểm tra/redact nội dung
 *   nhạy cảm trong tool_input, rồi trả lại JSON đã xử lý qua stdout.
 *
 * Cách dùng (trong .claude/settings.json):
 *   "PreToolUse": [
 *     "node HLK/wrappers/hlk-hook-bridge.mjs"
 *   ]
 *
 * Exit codes:
 *   0 = cho phép tool chạy (có thể đã redact)
 *   2 = chặn tool
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---------------------------------------------------------------------------
// Bước 1: Tiện ích cơ bản
// ---------------------------------------------------------------------------

/**
 * Ghi log ra stderr. Không bao giờ ra stdout vì stdout là output JSON.
 */
function log(msg) {
  process.stderr.write(`[HLK Hook] ${msg}\n`);
}

/**
 * Đệ quy tìm mọi chuỗi string bên trong một object/array.
 * Dùng để kiểm tra toàn bộ tool_input có chứa secret không.
 */
function findAllStrings(obj, out = []) {
  if (typeof obj === 'string') {
    out.push(obj);
  } else if (Array.isArray(obj)) {
    for (const item of obj) findAllStrings(item, out);
  } else if (obj && typeof obj === 'object') {
    for (const value of Object.values(obj)) findAllStrings(value, out);
  }
  return out;
}

/**
 * Đệ quy thay thế mọi chuỗi string bên trong object/array
 * bằng hàm sanitizer.
 */
function replaceAllStrings(obj, sanitizer) {
  if (typeof obj === 'string') return sanitizer(obj);
  if (Array.isArray(obj)) return obj.map((v) => replaceAllStrings(v, sanitizer));
  if (obj && typeof obj === 'object') {
    const result = {};
    for (const [k, v] of Object.entries(obj)) {
      result[k] = replaceAllStrings(v, sanitizer);
    }
    return result;
  }
  return obj;
}

// ---------------------------------------------------------------------------
// Bước 2: Đọc toàn bộ stdin
// ---------------------------------------------------------------------------

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf8').trim();
}

// ---------------------------------------------------------------------------
// Bước 3: Load HLK config
// ---------------------------------------------------------------------------

const CONFIG_PATH = path.resolve(__dirname, '../config/hlk.config.json');

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
      return JSON.parse(raw);
    }
  } catch (err) {
    log(`Không đọc được config: ${err.message}`);
  }
  return { hlk_enabled: false };
}

const config = loadConfig();

// Nếu HLK tắt, thoát ngay — không can thiệp agent runtime
if (!config.hlk_enabled) {
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Bước 4: Load sanitizer
// ---------------------------------------------------------------------------

let sanitizer = null;

if (config.features?.data_sanitization) {
  try {
    const sanitizerModule = await import('../security/sanitizer.js');
    sanitizer = sanitizerModule.sanitize || ((text) => text);
  } catch (err) {
    log(`Không nạp được sanitizer: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Bước 5: Nạp agent-tool custom hooks
// ---------------------------------------------------------------------------

const AGENT_TOOL_HOOKS_DIR = path.resolve(__dirname, '../custom-hooks/agent-tool');
const agentToolHooks = [];

async function loadAgentToolHooks() {
  if (!config.features?.custom_hooks_injection) return;
  if (!fs.existsSync(AGENT_TOOL_HOOKS_DIR)) return;

  const files = fs.readdirSync(AGENT_TOOL_HOOKS_DIR)
    .filter((f) => f.endsWith('.hook.mjs'))
    .sort();

  for (const file of files) {
    const filePath = path.join(AGENT_TOOL_HOOKS_DIR, file);
    try {
      const mod = await import(pathToFileURL(filePath).href);
      if (typeof mod.default === 'function') {
        agentToolHooks.push({ file, run: mod.default });
      }
    } catch (err) {
      log(`⚠ agent-tool hook lỗi nạp, bỏ qua: ${file} — ${err.message}`);
    }
  }
}

async function runAgentToolHooks(context) {
  let ctx = context;
  for (const { file, run } of agentToolHooks) {
    try {
      const result = await run(ctx);
      if (result?.block) {
        log(`🚫 Bị chặn bởi agent-tool hook ${file}: ${result.reason || ''}`);
        process.exit(2);
      }
      if (result && 'value' in result) {
        ctx = { ...ctx, value: result.value };
      }
    } catch (err) {
      log(`⚠ agent-tool hook lỗi khi chạy, bỏ qua: ${file} — ${err.message}`);
    }
  }
  return ctx;
}

await loadAgentToolHooks();

// ---------------------------------------------------------------------------
// Bước 6: Đọc và parse input JSON
// ---------------------------------------------------------------------------

const rawInput = await readStdin();
let input;

try {
  input = rawInput ? JSON.parse(rawInput) : {};
} catch (err) {
  log(`Input không phải JSON hợp lệ: ${err.message}`);
  // Fail-open: nếu input lạ, không chặn, chỉ trả input gốc
  console.log(rawInput || '{}');
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Bước 7: Trích xuất tool_input
// ---------------------------------------------------------------------------

const toolName = input?.tool_name || 'unknown';
let toolInput = input?.tool_input || input;

if (!toolInput || typeof toolInput !== 'object') {
  console.log(JSON.stringify(input));
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Bước 8: Chạy agent-tool hooks trước khi sanitize
// ---------------------------------------------------------------------------

if (agentToolHooks.length > 0) {
  await runAgentToolHooks({ toolName, toolInput, input });
}

// ---------------------------------------------------------------------------
// Bước 9: Chặn hoặc redact tùy theo loại tool
// ---------------------------------------------------------------------------

/**
 * Các tool chạy command hoặc patch lên hệ thống (Bash, ApplyPatch)
 * KHÔNG được phép chứa secret — vì redact một câu lệnh rồi chạy
 * có thể tạo ra hành vi không mong muốn.
 */
const BLOCK_TOOLS = ['Bash', 'ApplyPatch'];

if (sanitizer && BLOCK_TOOLS.includes(toolName)) {
  const allStrings = findAllStrings(toolInput);
  const rawJoined = allStrings.join(' ');

  if (rawJoined !== sanitizer(rawJoined)) {
    log(`🚫 Tool ${toolName} chứa dữ liệu nhạy cảm — bị chặn để tránh rò rỉ`);
    process.exit(2);
  }
}

/**
 * Các tool ghi file (Write, Edit) cho phép redact nội dung
 * rồi tiếp tục. Nội dung file sẽ chứa [REDACTED] thay vì secret.
 */
if (sanitizer) {
  const allStrings = findAllStrings(toolInput);

  for (const s of allStrings) {
    const clean = sanitizer(s);
    if (clean !== s) {
      log(`🧹 Phát hiện dữ liệu nhạy cảm trong tool input của ${toolName}`);
    }
  }

  if (config.features?.data_sanitization) {
    const sanitizedToolInput = replaceAllStrings(toolInput, sanitizer);
    if (input.tool_input) {
      input.tool_input = sanitizedToolInput;
      // Cập nhật toolInput để các bước sau dùng dữ liệu đã redact
      toolInput = sanitizedToolInput;
    } else {
      input = sanitizedToolInput;
      toolInput = sanitizedToolInput;
    }
  }
}

// ---------------------------------------------------------------------------
// Bước 11: Trả output JSON
// ---------------------------------------------------------------------------

console.log(JSON.stringify(input));
process.exit(0);
