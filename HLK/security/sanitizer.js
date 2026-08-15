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
// U29: Expanded with AWS, JWT, OAuth, DB connection patterns
const DEFAULT_PATTERNS = [
  // Existing patterns
  'sk-[a-zA-Z0-9]{32,}',
  'ghp_[a-zA-Z0-9]{36}',
  '(?i)password\\s*=\\s*[\'"]?[^\'"\\s]+',
  '(?i)api[_-]?key\\s*=\\s*[\'"]?[^\'"\\s]+',
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
  // U29: AWS access key ID (starts with AKIA, 20 chars total)
  'AKIA[0-9A-Z]{16}',
  // U29: AWS secret access key (40 chars, base64-ish after key ID)
  '(?i)aws[_-]?secret[_-]?access[_-]?key\\s*=\\s*[\'"]?[A-Za-z0-9/+=]{40}',
  // U29: JWT (3 base64 segments separated by dots, excluding eyJ prefix to avoid false positives)
  '[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]{20,}',
  // U29: OAuth Bearer token
  '(?i)Bearer\\s+[A-Za-z0-9._-]+',
  // U29: Database connection string with credentials
  '[a-z]+://[^:\\s]+:[^@\\s]+@[^/\\s]+',
  // U29: Google API key
  'AIza[0-9A-Za-z_-]{35}',
  // U29: Slack token
  'xox[baprs]-[0-9A-Za-z-]+',
  // U29: Stripe key
  '(sk|pk|rk)_(live|test)_[0-9a-zA-Z]{24,}',
  // U54: Twilio API credentials (Account SID + Auth Token)
  'AC[a-z0-9]{32}',
  'SK[a-z0-9]{32}',
  // U54: SendGrid API key
  'SG\\.[a-zA-Z0-9_-]{22}\\.[a-zA-Z0-9_-]{43}',
  // U54: Datadog API key + App key
  'pub[a-f0-9]{32}',
  '(?i)datadog[_-]?(api|app)[_-]?key\\s*=\\s*[\'"]?[a-f0-9]{32}',
  // U54: Firebase web API config (longer variant)
  'AIzaSy[A-Za-z0-9_-]{33,}',
  // U54: AWS session token (long base64-ish after token=)
  '(?i)aws[_-]?session[_-]?token\\s*=\\s*[\'"]?[A-Za-z0-9/+=]{40,}',
  // U54: GitHub fine-grained PAT (github_pat_...)
  'github_pat_[A-Za-z0-9_]{22,}',
  // U54: GitLab PAT
  'glpat-[A-Za-z0-9_-]{20}',
  // U54: npm publish token
  'npm_[A-Za-z0-9]{36}',
];

// ---------------------------------------------------------------------------
// Bước 1: Đọc pattern từ config
// ---------------------------------------------------------------------------

// CVE-2026-AHD-011: patterns "critical" — nếu thiếu và failClosedOnConfigError
// bật, sanitizer từ chối hoạt động (fail CLOSED) thay vì chạy với bộ thiếu.
const CRITICAL_SUBSTRINGS = [
  'AKIA',           // AWS access key
  'PRIVATE KEY',    // private key blocks
  'ghp_',           // GitHub PAT
  'glpat-',         // GitLab PAT
  'sk-',            // OpenAI-style keys
  '://',            // DB/URL connection string (creds)
  'Bearer',         // OAuth bearer tokens
  'eyJ',            // JWT
  'github_pat_',    // GitHub fine-grained PAT
  'npm_',           // npm publish token
  'SG.',            // SendGrid API key
  'AIzaSy',         // Google/Firebase long API key
  'xox',            // Slack token
  '(sk|pk|rk)_',    // Stripe live/test keys
];

function isCriticalPattern(pattern) {
  const cleaned = pattern.startsWith('(?i)') ? pattern.slice(4) : pattern;
  return CRITICAL_SUBSTRINGS.some((sub) => cleaned.includes(sub));
}

/**
 * Đọc các regex pattern redact từ `hlk.config.json`.
 *
 * Cú pháp hỗ trợ trong JSON:
 *   "(?i)api_key\\s*=\\s*[^\\s]+"  → flag case-insensitive
 *
 * Chuỗi `(?i)` trong regex JavaScript không hỗ trợ trực tiếp,
 * nên hàm `compilePattern` sẽ chuyển thành flag `gi`.
 *
 * CVE-2026-AHD-011: trả thêm { configValid, errors, warn } — lỗi config
 * không còn silent; `failClosedOnConfigError` đọc từ security_rules.
 */
function loadConfigRules() {
  const errors = [];
  const warnings = [];
  let configValid = false;
  let failClosedOnConfigError = false;
  let patterns = null;
  let replacement = '[REDACTED]';

  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
      const cfg = JSON.parse(raw);
      patterns = cfg?.security_rules?.redact_patterns;
      replacement = cfg?.security_rules?.redact_replacement || '[REDACTED]';
      failClosedOnConfigError = Boolean(cfg?.security_rules?.failClosedOnConfigError);

      if (Array.isArray(patterns) && patterns.length > 0) {
        configValid = true;
      } else {
        errors.push('security_rules.redact_patterns missing or empty in hlk.config.json');
      }
    } else {
      errors.push(`config not found: ${CONFIG_PATH}`);
    }
  } catch (err) {
    errors.push(`config parse error: ${err.message}`);
  }

  if (!configValid) {
    // CVE-2026-AHD-011: warning rõ ràng, KHÔNG silent nữa
    warnings.push(
      `config invalid (${errors.join('; ')}) — falling back to ${DEFAULT_PATTERNS.length} default patterns`,
    );
    for (const w of warnings) {
      process.stderr.write(`[HLK Sanitizer] WARNING: ${w}\n`);
    }
    return { patterns: DEFAULT_PATTERNS, replacement: '[REDACTED]', configValid: false, errors, warnings, failClosedOnConfigError };
  }
  return { patterns, replacement, configValid: true, errors, warnings, failClosedOnConfigError };
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
  const { patterns, replacement, configValid, errors, warnings, failClosedOnConfigError } = loadConfigRules();

  const compiledPatterns = patterns
    .map(compilePattern)
    .filter(Boolean);

  // CVE-2026-AHD-011: fail CLOSED nếu cấu hình lỗi/thiếu critical patterns
  // và security_rules.failClosedOnConfigError = true.
  // Critical baseline = DEFAULT_PATTERNS (bộ chuẩn); config chỉ được phép
  // THÊM pattern, không được BỚT pattern critical.
  if (failClosedOnConfigError) {
    const compiledSources = new Set(compiledPatterns.map((re) => re.source));
    const requiredCritical = DEFAULT_PATTERNS.filter(isCriticalPattern);
    const missingCritical = requiredCritical.filter((p) => !compiledSources.has(compileSource(p)));
    const problems = [];
    if (!configValid) problems.push('config invalid');
    if (missingCritical.length > 0) problems.push(`critical patterns missing: ${missingCritical.join(', ')}`);
    if (problems.length > 0) {
      const msg = `[HLK Sanitizer] FAIL-CLOSED: ${problems.join('; ')} — refusing to sanitize with incomplete rules (CVE-2026-AHD-011)`;
      process.stderr.write(`${msg}\n`);
      throw new Error(msg);
    }
  }

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

  /**
   * CVE-2026-AHD-011: health check — trạng thái cấu hình + pattern đã load.
   */
  function healthCheck() {
    const compiledSources = new Set(compiledPatterns.map((re) => re.source));
    const requiredCritical = DEFAULT_PATTERNS.filter(isCriticalPattern);
    const missingCritical = requiredCritical.filter((p) => !compiledSources.has(compileSource(p)));
    return {
      patternsLoaded: compiledPatterns.length,
      patternsConfigured: patterns.length,
      configValid,
      failClosedOnConfigError,
      criticalMissing: missingCritical,
      errors,
      warnings,
      ok: configValid && missingCritical.length === 0,
    };
  }

  return { sanitize, patterns: compiledPatterns, replacement, healthCheck };
}

function compileSource(pattern) {
  const hasCaseInsensitive = pattern.startsWith('(?i)');
  const cleaned = hasCaseInsensitive ? pattern.replace(/^\(\?i\)/, '') : pattern;
  const flags = hasCaseInsensitive ? 'gi' : 'g';
  try {
    return new RegExp(cleaned, flags).source;
  } catch (err) {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Bước 4: Singleton mặc định
// ---------------------------------------------------------------------------

const defaultSanitizer = (() => {
  try {
    return createSanitizer();
  } catch (err) {
    // CVE-2026-AHD-011: fail-closed — sanitize() sẽ throw, không pass-through
    return null;
  }
})();

/**
 * Sanitize một chuỗi dùng sanitizer mặc định.
 */
export function sanitize(text) {
  if (!defaultSanitizer) {
    throw new Error('[HLK Sanitizer] FAIL-CLOSED: sanitizer unavailable (CVE-2026-AHD-011)');
  }
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