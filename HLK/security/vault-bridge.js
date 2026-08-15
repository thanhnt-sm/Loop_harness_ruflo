/**
 * HLK Vault Bridge
 * =================
 * Mục đích tổng thể:
 *   Quản lý secrets/API keys một cách độc lập với ruflo core.
 *
 * Thứ tự ưu tiên khi tìm một secret (CVE-2026-AHD-012):
 *   Mặc định "file>env" (an toàn hơn — file local không bị lộ qua
 *   environment của process cha/CI):
 *     1. HLK/config/secrets.env — file local (đã được .gitignore)
 *     2. process.env — biến môi trường hệ điều hành
 *     3. defaultValue (nếu truyền vào) hoặc undefined
 *
 *   Có thể cấu hình lại qua `security_rules.secretPrecedence` trong
 *   hlk.config.json: "file>env" (default) | "env>file" (legacy).
 *
 * Tuyệt đối không lưu secrets vào bất kỳ file tracked nào.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// File secrets local, được .gitignore bảo vệ
const SECRETS_PATH = path.resolve(__dirname, '../config/secrets.env');
const CONFIG_PATH = path.resolve(__dirname, '../config/hlk.config.json');

// Cache để tránh đọc file nhiều lần
/** @type {Map<string, string>} */
const secretsCache = new Map();
let loaded = false;
let precedence = 'file>env';

/**
 * CVE-2026-AHD-012: đọc secretPrecedence từ hlk.config.json.
 * Default "file>env" (an toàn hơn). Lỗi config -> giữ default + warning.
 */
function loadPrecedence() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
      const value = cfg?.security_rules?.secretPrecedence;
      if (value === 'env>file' || value === 'file>env') {
        precedence = value;
      } else if (value !== undefined) {
        process.stderr.write(`[HLK Vault] WARNING: secretPrecedence không hợp lệ: ${value} — dùng default 'file>env'\n`);
      }
    }
  } catch (err) {
    process.stderr.write(`[HLK Vault] WARNING: không đọc được config precedence: ${err.message} — dùng default 'file>env'\n`);
  }
}

// ---------------------------------------------------------------------------
// Bước 1: Parse file .env đơn giản
// ---------------------------------------------------------------------------

/**
 * Parse file .env:
 *   KEY=VALUE
 *   export KEY=VALUE     (hỗ trợ export prefix — dotenv convention)
 *   KEY=VALUE # comment  (bỏ inline comment khi value không quote)
 *   KEY="VALUE" / KEY='VALUE'
 *
 * Không hỗ trợ interpolation hay multi-line.
 *
 * @param {string} filePath
 * @returns {Map<string, string>}
 */
function parseDotEnv(filePath) {
  const map = new Map();

  try {
    if (!fs.existsSync(filePath)) return map;

    const lines = fs.readFileSync(filePath, 'utf8').split('\n');
    for (const raw of lines) {
      let line = raw.trim();
      if (!line || line.startsWith('#')) continue;

      // Bỏ export prefix (dotenv convention)
      if (line.startsWith('export ')) {
        line = line.slice('export '.length).trim();
      }

      const eqIdx = line.indexOf('=');
      if (eqIdx < 1) continue;

      const key = line.slice(0, eqIdx).trim();
      let value = line.slice(eqIdx + 1).trim();

      const isQuoted = (value.startsWith('"') && value.endsWith('"')) ||
                       (value.startsWith("'") && value.endsWith("'"));

      // Bỏ dấu ngoặc bao quanh value
      if (isQuoted) {
        value = value.slice(1, -1);
        // Giải escape dấu ngoặc bên trong (\" → ", \' → ')
        value = value.replace(/\\(["'])/g, '$1');
      } else {
        // Không quote → cắt inline comment (sau '#' không trong quote)
        const hashIdx = value.indexOf(' #');
        if (hashIdx >= 0) {
          value = value.slice(0, hashIdx).trim();
        }
      }

      map.set(key, value);
    }
  } catch (err) {
    process.stderr.write(`[HLK Vault] Không đọc được secrets.env: ${err.message}\n`);
  }

  return map;
}

// ---------------------------------------------------------------------------
// Bước 2: Đảm bảo secrets đã load vào cache
// ---------------------------------------------------------------------------

function ensureLoaded() {
  if (loaded) return true;

  const fileSecrets = parseDotEnv(SECRETS_PATH);
  for (const [k, v] of fileSecrets) {
    secretsCache.set(k, v);
  }

  loaded = true;
  return true;
}

// ---------------------------------------------------------------------------
// Bước 2b: Audit log (CVE-2026-AHD-012)
// ---------------------------------------------------------------------------

/**
 * Ghi nguồn secret vào telemetry/vault_audit.jsonl (append-only, không ghi
 * giá trị secret — chỉ key + nguồn).
 */
function auditSecretAccess(key, source) {
  try {
    const auditDir = path.resolve(__dirname, '../../.devin/telemetry');
    fs.mkdirSync(auditDir, { recursive: true });
    const entry = {
      ts: new Date().toISOString(),
      event: 'vault.getSecret',
      key,
      source,
    };
    fs.appendFileSync(path.join(auditDir, 'vault_audit.jsonl'), JSON.stringify(entry) + '\n');
  } catch (err) {
    // Best-effort: audit lỗi không chặn getSecret
    process.stderr.write(`[HLK Vault] WARNING: audit log lỗi: ${err.message}\n`);
  }
}

/**
 * CVE-2026-AHD-012: trả về precedence đang dùng (cho diagnostics/tests).
 */
export function getSecretPrecedence() {
  loadPrecedence();
  return precedence;
}

// ---------------------------------------------------------------------------
// Bước 3: Public API
// ---------------------------------------------------------------------------

/**
 * Lấy giá trị secret.
 *
 * Thứ tự ưu tiên (CVE-2026-AHD-012):
 *   file>env (default, an toàn): 1. secrets.env  2. process.env  3. defaultValue
 *   env>file (legacy):            1. process.env  2. secrets.env  3. defaultValue
 *
 * Ghi audit log nguồn secret (file|env|default) vào telemetry/vault_audit.jsonl.
 */
export function getSecret(key, defaultValue) {
  loadPrecedence();
  const fileValue = ensureLoaded() ? secretsCache.get(key) : undefined;
  const envValue = process.env[key];

  let value;
  let source;
  if (precedence === 'file>env') {
    if (fileValue !== undefined) { value = fileValue; source = 'file'; }
    else if (envValue !== undefined) { value = envValue; source = 'env'; }
    else { value = defaultValue; source = 'default'; }
  } else {
    if (envValue !== undefined) { value = envValue; source = 'env'; }
    else if (fileValue !== undefined) { value = fileValue; source = 'file'; }
    else { value = defaultValue; source = 'default'; }
  }

  // CVE-2026-AHD-016: tránh log-spam audit file cho source='default' (key không
  // tồn tại), NHƯNG vẫn cảnh báo stderr — fallback về default không an toàn cần
  // được phát hiện (miss-config / credential yếu), chỉ khác là không ghi jsonl.
  if (source === 'file' || source === 'env') {
    auditSecretAccess(key, source);
  } else if (source === 'default') {
    process.stderr.write(`[HLK Vault] WARNING: getSecret('${key}') không tìm thấy file/env — đang dùng defaultValue (fallback).\n`);
  }
  return value;
}

/**
 * Kiểm tra secret có tồn tại không (theo thứ tự ưu tiên hiện hành).
 */
export function hasSecret(key) {
  loadPrecedence();
  const fileValue = ensureLoaded() ? secretsCache.has(key) : false;
  if (precedence === 'file>env') {
    return fileValue || process.env[key] !== undefined;
  }
  return process.env[key] !== undefined || fileValue;
}

/**
 * Liệt kê tất cả key trong file secrets.env (KHÔNG liệt kê process.env).
 */
export function listSecretKeys() {
  ensureLoaded();
  return [...secretsCache.keys()];
}

/**
 * Force reload secrets từ disk.
 */
export function reload() {
  secretsCache.clear();
  loaded = false;
  ensureLoaded();
}

/**
 * Trả về đường dẫn đến file secrets.env (dùng cho diagnostics).
 */
export function getSecretsPath() {
  return SECRETS_PATH;
}

export default { getSecret, hasSecret, listSecretKeys, reload, getSecretsPath, getSecretPrecedence };
