/**
 * HLK Vault Bridge
 * =================
 * Mục đích tổng thể:
 *   Quản lý secrets/API keys một cách độc lập với ruflo core.
 *
 * Thứ tự ưu tiên khi tìm một secret:
 *   1. process.env — biến môi trường hệ điều hành
 *   2. HLK/config/secrets.env — file local (đã được .gitignore)
 *   3. defaultValue (nếu truyền vào) hoặc undefined
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

// Cache để tránh đọc file nhiều lần
/** @type {Map<string, string>} */
const secretsCache = new Map();
let loaded = false;

// ---------------------------------------------------------------------------
// Bước 1: Parse file .env đơn giản
// ---------------------------------------------------------------------------

/**
 * Parse file .env theo định dạng đơn giản:
 *   KEY=VALUE
 *   # comment
 *
 * Hỗ trợ value có dấu ngoặc đơn/kép.
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
      const line = raw.trim();
      if (!line || line.startsWith('#')) continue;

      const eqIdx = line.indexOf('=');
      if (eqIdx < 1) continue;

      const key = line.slice(0, eqIdx).trim();
      let value = line.slice(eqIdx + 1).trim();

      // Bỏ dấu ngoặc bao quanh value
      if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1);
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
  if (loaded) return;

  const fileSecrets = parseDotEnv(SECRETS_PATH);
  for (const [k, v] of fileSecrets) {
    secretsCache.set(k, v);
  }

  loaded = true;
}

// ---------------------------------------------------------------------------
// Bước 3: Public API
// ---------------------------------------------------------------------------

/**
 * Lấy giá trị secret.
 *
 * Thứ tự ưu tiên:
 *   1. process.env
 *   2. HLK/config/secrets.env
 *   3. defaultValue
 */
export function getSecret(key, defaultValue) {
  if (process.env[key] !== undefined) {
    return process.env[key];
  }
  ensureLoaded();
  return secretsCache.get(key) ?? defaultValue;
}

/**
 * Kiểm tra secret có tồn tại không.
 */
export function hasSecret(key) {
  if (process.env[key] !== undefined) return true;
  ensureLoaded();
  return secretsCache.has(key);
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

export default { getSecret, hasSecret, listSecretKeys, reload, getSecretsPath };
