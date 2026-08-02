/**
 * HLK Data Sanitizer
 * ==================
 * Mục đích tổng thể:
 *   Thay thế (redact) các chuỗi nhạy cảm (API keys, tokens, passwords,
 *   connection strings, private keys) bằng chuỗi `[REDACTED]` hoặc giá trị
 *   cấu hình khác trước khi dữ liệu được ghi vào memory, log, hoặc gửi đi.
 *
 * Nguồn pattern:
 *   1. HLK/config/hlk.config.json → security_rules.redact_patterns
 *   2. Nếu config lỗi → fallback về danh sách mặc định
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Đường dẫn đến file cấu hình HLK
const CONFIG_PATH = path.resolve(__dirname, '../config/hlk.config.json');

// Danh sách pattern mặc định nếu không đọc được config
const DEFAULT_PATTERNS = [
  'sk-[a-zA-Z0-9]{32,}',
  'ghp_[a-zA-Z0-9]{36}',
  '(?i)password\\s*=\\s*[\'"]?[^\'"\\s]+',
  '(?i)api[_-]?key\\s*=\\s*[\'"]?[^\'"\\s]+',
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
];

// ---------------------------------------------------------------------------
// Bước 1: Đọc pattern từ config
// ---------------------------------------------------------------------------

/**
 * Đọc các regex pattern redact từ `hlk.config.json`.
 *
 * Cú pháp hỗ trợ trong JSON:
 *   "(?i)api_key\\s*=\\s*[^\\s]+"  → flag case-insensitive
 *
 * Chuỗi `(?i)` trong regex JavaScript không hỗ trợ trực tiếp,
 * nên hàm `compilePattern` sẽ chuyển thành flag `gi`.
 */
function loadConfigRules() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
      const cfg = JSON.parse(raw);
      const patterns = cfg?.security_rules?.redact_patterns;
      const replacement = cfg?.security_rules?.redact_replacement || '[REDACTED]';

      if (Array.isArray(patterns) && patterns.length > 0) {
        return { patterns, replacement };
      }
    }
  } catch (err) {
    // Config lỗi → dùng mặc định, không throw
  }

  return { patterns: DEFAULT_PATTERNS, replacement: '[REDACTED]' };
}

// ---------------------------------------------------------------------------
// Bước 2: Biên dịch pattern thành RegExp
// ---------------------------------------------------------------------------

/**
 * Biên dịch một chuỗi pattern thành RegExp.
 *
 * Quy tắc:
 *   - Nếu pattern chứa `(?i)` ở đầu → loại bỏ `(?i)` và thêm flag `i`.
 *   - Nếu không có `(?i)` → flag `g` để thay thế tất cả lần xuất hiện.
 *
 * Nếu pattern sai cú pháp → bỏ qua pattern đó.
 */
function compilePattern(pattern) {
  const hasCaseInsensitive = pattern.startsWith('(?i)');
  const cleaned = hasCaseInsensitive ? pattern.replace(/^\(\?i\)/, '') : pattern;
  const flags = hasCaseInsensitive ? 'gi' : 'g';

  try {
    return new RegExp(cleaned, flags);
  } catch (err) {
    process.stderr.write(`[HLK Sanitizer] Bỏ qua pattern lỗi: ${pattern} — ${err.message}\n`);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Bước 3: Tạo sanitizer
// ---------------------------------------------------------------------------

/**
 * Tạo một sanitizer với pattern đã biên dịch.
 *
 * @returns {{ sanitize: Function, patterns: RegExp[], replacement: string }}
 */
export function createSanitizer() {
  const { patterns, replacement } = loadConfigRules();

  const compiledPatterns = patterns
    .map(compilePattern)
    .filter(Boolean);

  /**
   * Thay thế các chuỗi khớp pattern bằng `replacement`.
   *
   * @param {string} text - chuỗi cần redact
   * @returns {string} - chuỗi đã redact
   */
  function sanitize(text) {
    if (typeof text !== 'string') return text;

    let result = text;
    for (const re of compiledPatterns) {
      result = result.replace(re, replacement);
    }
    return result;
  }

  return { sanitize, patterns: compiledPatterns, replacement };
}

// ---------------------------------------------------------------------------
// Bước 4: Singleton mặc định
// ---------------------------------------------------------------------------

const defaultSanitizer = createSanitizer();

/**
 * Sanitize một chuỗi dùng sanitizer mặc định.
 */
export function sanitize(text) {
  return defaultSanitizer.sanitize(text);
}

/**
 * Sanitize tất cả các giá trị string trong một object (shallow).
 */
export function sanitizeObject(obj) {
  if (!obj || typeof obj !== 'object') return obj;

  const result = {};
  for (const [key, value] of Object.entries(obj)) {
    result[key] = typeof value === 'string' ? sanitize(value) : value;
  }
  return result;
}

export default { sanitize, sanitizeObject, createSanitizer };
