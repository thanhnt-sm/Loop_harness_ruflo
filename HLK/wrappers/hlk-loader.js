/**
 * HLK Interceptor Loader Module (ESM compatible)
 * =================================================
 * Mục đích tổng thể:
 *   - Can thiệp tiến trình Node.js TRƯỚC khi CLI chạy.
 *   - Bật/tắt hoàn toàn bằng `hlk_enabled` trong `HLK/config/hlk.config.json`.
 *   - Khi bật: redact secret trong `process.argv`, block telemetry, nạp vault,
 *     nạp custom hooks.
 *   - Khi tắt: no-op tuyệt đối — không in log, không set env, không đụng argv.
 *
 * Cách dùng:
 *   NODE_OPTIONS="--import=file://<repo>/HLK/wrappers/hlk-loader.js" node <cli> ...
 *
 * Phiên bản: 3.0.0
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Đường dẫn tuyệt đối đến file cấu hình HLK
const CONFIG_PATH = path.resolve(__dirname, '../config/hlk.config.json');

// ---------------------------------------------------------------------------
// Bước 1: Đọc cấu hình HLK
// ---------------------------------------------------------------------------

/**
 * Đọc file cấu hình `hlk.config.json`.
 * Nếu file không tồn tại hoặc lỗi parse → trả về `{ hlk_enabled: false }`
 * để đảm bảo an toàn mặc định.
 *
 * Quan trọng: Hàm này KHÔNG được in log ra stdout/stderr vì lúc này
 * chưa biết `hlk_enabled` là true hay false.
 */
function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
      return JSON.parse(raw);
    }
  } catch {
    // Không đọc được config → disable. Không in log tại đây.
  }
  return { hlk_enabled: false };
}

const config = loadConfig();

// ---------------------------------------------------------------------------
// Bước 2: Khai báo public API mặc định (no-op)
// ---------------------------------------------------------------------------

// Các biến này sẽ được gán lại nếu HLK bật
let sanitizerModule = null;
let vaultModule = null;
let customHooks = { 'pre-argv': [], 'post-sanitize': [] };

function isEnabledFn() { return false; }
function sanitizeFn(text) { return text; }
function sanitizeObjectFn(obj) { return obj; }
function getSecretFn(key, defaultValue) { return process.env[key] ?? defaultValue; }
function hasSecretFn() { return false; }
function getCustomHooksFn() { return customHooks; }

// Gán reference
let isEnabled = isEnabledFn;
let sanitize = sanitizeFn;
let sanitizeObject = sanitizeObjectFn;
let getSecret = getSecretFn;
let hasSecret = hasSecretFn;
let getCustomHooks = getCustomHooksFn;

function getHlkConfig() { return config; }
function getVersion() { return config.version || 'unknown'; }

// ---------------------------------------------------------------------------
// Bước 3: Nếu HLK bật, thực thi initialization
// ---------------------------------------------------------------------------

if (config.hlk_enabled) {
  // -------------------------------------------------------------------
  // 3.1. Tiện ích log — LUÔN ghi ra stderr
  // -------------------------------------------------------------------

  /**
   * Ghi log ra `stderr` thay vì `console.log`.
   * Lý do: khi CLI chạy ở chế độ MCP server, stdout chứa khung JSON-RPC.
   * Nếu log ra stdout sẽ làm hỏng giao thức stdio.
   */
  function log(msg) {
    process.stderr.write(`[HLK] ${msg}\n`);
  }

  // -------------------------------------------------------------------
  // 3.2. Chặn telemetry bằng biến môi trường
  // -------------------------------------------------------------------

  /**
   * Bước này chỉ chạy khi `features.telemetry_blocker === true`.
   * Nguyên tắc: chỉ set env nếu env đó CHƯA tồn tại, tôn trọng giá trị
   * mà người dùng đã cấu hình thủ công.
   */
  if (config.features?.telemetry_blocker && config.telemetry_overrides) {
    for (const [key, value] of Object.entries(config.telemetry_overrides)) {
      if (process.env[key] === undefined) {
        process.env[key] = String(value);
      }
    }
    log('🚫 Telemetry blocker active — external exporters disabled');
  }

  // -------------------------------------------------------------------
  // 3.3. Nạp các module phụ trợ theo feature flag
  // -------------------------------------------------------------------

  if (config.features?.data_sanitization) {
    try {
      sanitizerModule = await import('../security/sanitizer.js');
      log('🧹 Data sanitizer loaded');
    } catch (err) {
      log(`⚠ Failed to load sanitizer: ${err.message}`);
    }
  }

  if (config.features?.secret_vault_override) {
    try {
      vaultModule = await import('../security/vault-bridge.js');
      log('🔐 Vault bridge loaded');
    } catch (err) {
      log(`⚠ Failed to load vault bridge: ${err.message}`);
    }
  }

  // -------------------------------------------------------------------
  // 3.4. Nạp custom hooks theo phase
  // -------------------------------------------------------------------

  /**
   * Cấu trúc custom hooks:
   *   HLK/custom-hooks/<phase>/*.hook.mjs
   *
   * phase hỗ trợ:
   *   - pre-argv: chạy trước khi sanitize process.argv
   *   - post-sanitize: chạy sau khi sanitize process.argv
   *   - agent-tool: dùng trong `hlk-hook-bridge.mjs` (không load ở đây)
   *
   * Tên file: `<order>-<mo-ta>.hook.mjs`, ví dụ `10-block-internal-codename.hook.mjs`.
   * Số `order` quyết định thứ tự chạy.
   *
   * Hợp đồng export default:
   *   async function run(context) {
   *     return { value?: any, block?: boolean, reason?: string };
   *   }
   *
   * Lỗi kỹ thuật trong một hook → bỏ qua hook đó, không sập tiến trình.
   * `block: true` → dừng tiến trình với exit code 2.
   */
  const CUSTOM_HOOKS_DIR = path.resolve(__dirname, '../custom-hooks');

  customHooks = {
    'pre-argv': [],
    'post-sanitize': [],
  };

  async function loadCustomHooksForPhase(phase) {
    const phaseDir = path.join(CUSTOM_HOOKS_DIR, phase);
    if (!fs.existsSync(phaseDir)) return;

    const files = fs.readdirSync(phaseDir)
      .filter((f) => f.endsWith('.hook.mjs'))
      .sort();

    for (const file of files) {
      const filePath = path.join(phaseDir, file);
      try {
        const mod = await import(pathToFileURL(filePath).href);
        if (typeof mod.default === 'function') {
          customHooks[phase].push({ file, run: mod.default });
        }
      } catch (err) {
        log(`⚠ custom-hook lỗi nạp, bỏ qua: ${file} — ${err.message}`);
      }
    }
  }

  async function runCustomHooks(phase, context) {
    let ctx = context;
    for (const { file, run } of customHooks[phase] || []) {
      try {
        const result = await run(ctx);
        if (result?.block) {
          log(`🚫 Bị chặn bởi custom-hook ${file}: ${result.reason || ''}`);
          process.exit(2);
        }
        if (result && 'value' in result) {
          ctx = { ...ctx, value: result.value };
        }
      } catch (err) {
        log(`⚠ custom-hook lỗi khi chạy, bỏ qua: ${file} — ${err.message}`);
      }
    }
    return ctx;
  }

  if (config.features?.custom_hooks_injection) {
    await loadCustomHooksForPhase('pre-argv');
    await loadCustomHooksForPhase('post-sanitize');

    if (customHooks['pre-argv'].length > 0 || customHooks['post-sanitize'].length > 0) {
      log('🔌 Custom hooks loaded');
    }
  }

  // -------------------------------------------------------------------
  // 3.5. Chạy pre-argv custom hooks
  // -------------------------------------------------------------------

  if (config.features?.custom_hooks_injection && customHooks['pre-argv'].length > 0) {
    const preResult = await runCustomHooks('pre-argv', { argv: process.argv });
    if (preResult.argv && Array.isArray(preResult.argv)) {
      process.argv.splice(0, process.argv.length, ...preResult.argv);
    }
  }

  // -------------------------------------------------------------------
  // 3.6. Sanitize process.argv trước khi CLI parse
  // -------------------------------------------------------------------

  /**
   * Các flag chứa giá trị nhạy cảm mà CLI sử dụng:
   *   -v, --value (memory store value)
   *   --data      (dữ liệu thô)
   *   --content   (nội dung ghi vào memory hoặc tool input)
   *
   * Hàm này quét từng cặp (flag, value) và thay thế giá trị bằng
   * `sanitizer.sanitize()` trước khi commander parse.
   */
  const SENSITIVE_FLAG_PATTERN = /^(-v|--value|--data|--content)$/i;

  function sanitizeSensitiveArgv(argv) {
    if (!sanitizerModule) return argv;

    const out = [];
    for (let i = 0; i < argv.length; i++) {
      const arg = argv[i];
      out.push(arg);

      if (SENSITIVE_FLAG_PATTERN.test(arg) && i + 1 < argv.length) {
        const rawValue = argv[i + 1];
        const cleanValue = sanitizerModule.sanitize(rawValue);

        if (cleanValue !== rawValue) {
          out.push(cleanValue);
          i += 1; // bỏ qua giá trị gốc
          log(`🧹 Sanitized CLI value for flag ${arg}`);
        }
      }
    }

    return out;
  }

  if (config.features?.data_sanitization && sanitizerModule) {
    process.argv.splice(0, process.argv.length, ...sanitizeSensitiveArgv(process.argv));
  }

  // -------------------------------------------------------------------
  // 3.7. Chạy post-sanitize custom hooks
  // -------------------------------------------------------------------

  if (config.features?.custom_hooks_injection && customHooks['post-sanitize'].length > 0) {
    await runCustomHooks('post-sanitize', { argv: process.argv });
  }

  // -------------------------------------------------------------------
  // 3.8. Thông báo hoàn tất preload
  // -------------------------------------------------------------------

  log(`🛡️ HLK Layer ENABLED (v${config.version || '?'})`);

  // -------------------------------------------------------------------
  // 3.9. Cập nhật public API cho nhánh bật
  // -------------------------------------------------------------------

  isEnabled = () => true;
  sanitize = (text) => (sanitizerModule ? sanitizerModule.sanitize(text) : text);
  sanitizeObject = (obj) => (sanitizerModule ? sanitizerModule.sanitizeObject(obj) : obj);
  getSecret = (key, defaultValue) => {
    if (vaultModule) return vaultModule.getSecret(key, defaultValue);
    return process.env[key] ?? defaultValue;
  };
  hasSecret = (key) => {
    if (vaultModule) return vaultModule.hasSecret(key);
    return process.env[key] !== undefined;
  };
  getCustomHooks = () => customHooks;
}

// ---------------------------------------------------------------------------
// Bước 4: Export public API
// ---------------------------------------------------------------------------

export {
  getHlkConfig,
  isEnabled,
  sanitize,
  sanitizeObject,
  getSecret,
  hasSecret,
  getVersion,
  getCustomHooks,
};

export default {
  getHlkConfig,
  isEnabled,
  sanitize,
  sanitizeObject,
  getSecret,
  hasSecret,
  getVersion,
  getCustomHooks,
};
