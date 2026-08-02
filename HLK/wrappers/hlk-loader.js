/**
 * HLK Interceptor Loader Module (ESM compatible)
 * Quản lý cơ chế Bật/Tắt (Toggleable) của HLK Layer mà không sửa đổi trực tiếp core ruflo.
 *
 * v2.0.0 — Now binds actual middleware:
 *   - Data sanitizer (redacts secrets from memory/logs)
 *   - Telemetry blocker (sets env vars to disable external telemetry)
 *   - Vault bridge integration
 *
 * Usage:
 *   import hlk from './hlk-loader.js';
 *   if (hlk.isEnabled()) { ... }
 *   const clean = hlk.sanitize("text with sk-abc123...");
 *   const key = hlk.getSecret("OPENAI_API_KEY");
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CONFIG_PATH = path.join(__dirname, '../config/hlk.config.json');

// ─── Config Loading ──────────────────────────────────────────────────────────

export function getHlkConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
      return JSON.parse(raw);
    }
  } catch (err) {
    console.warn('[HLK WARNING] Không thể đọc hlk.config.json, mặc định disable HLK.');
  }
  return { hlk_enabled: false };
}

const config = getHlkConfig();

// ─── Middleware Binding ──────────────────────────────────────────────────────

let sanitizerModule = null;
let vaultModule = null;

async function bindMiddleware() {
  if (!config.hlk_enabled) return;

  // 1. Telemetry blocker — inject env vars to kill external telemetry
  if (config.features?.telemetry_blocker && config.telemetry_overrides) {
    for (const [key, value] of Object.entries(config.telemetry_overrides)) {
      if (process.env[key] === undefined) {
        process.env[key] = String(value);
      }
    }
    console.log('[HLK] 🚫 Telemetry blocker active — external exporters disabled');
  }

  // 2. Data sanitizer
  if (config.features?.data_sanitization) {
    try {
      sanitizerModule = await import('../security/sanitizer.js');
      console.log('[HLK] 🧹 Data sanitizer loaded — sensitive patterns will be redacted');
    } catch (err) {
      console.warn('[HLK WARNING] Failed to load sanitizer:', err.message);
    }
  }

  // 3. Vault bridge
  if (config.features?.secret_vault_override) {
    try {
      vaultModule = await import('../security/vault-bridge.js');
      console.log('[HLK] 🔐 Vault bridge loaded — secrets managed independently');
    } catch (err) {
      console.warn('[HLK WARNING] Failed to load vault bridge:', err.message);
    }
  }

  // 4. Knowledge protection notice
  if (config.features?.knowledge_protection) {
    console.log('[HLK] 📚 Knowledge protection active');
  }
}

// ─── Initialization ──────────────────────────────────────────────────────────

if (config.hlk_enabled) {
  console.log('[HLK] 🛡️ HLK Layer ENABLED (v' + (config.version || '?') + ') — binding middleware...');
  // Bind middleware async but don't block module loading
  bindMiddleware().catch((err) => {
    console.error('[HLK ERROR] Middleware binding failed:', err.message);
  });
} else {
  console.log('[HLK] ⚡ HLK Layer DISABLED — running vanilla Ruflo');
}

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Check if HLK layer is enabled.
 * @returns {boolean}
 */
function isEnabled() {
  return config.hlk_enabled === true;
}

/**
 * Sanitize text using HLK redaction patterns.
 * Returns text unchanged if HLK is disabled or sanitizer not loaded.
 * @param {string} text
 * @returns {string}
 */
function sanitize(text) {
  if (!config.hlk_enabled || !sanitizerModule) return text;
  return sanitizerModule.sanitize(text);
}

/**
 * Get a secret from vault bridge.
 * Falls through to process.env if vault not loaded.
 * @param {string} key
 * @param {string} [defaultValue]
 * @returns {string | undefined}
 */
function getSecret(key, defaultValue) {
  if (vaultModule) {
    return vaultModule.getSecret(key, defaultValue);
  }
  return process.env[key] ?? defaultValue;
}

/**
 * Get the current HLK version string.
 * @returns {string}
 */
function getVersion() {
  return config.version || 'unknown';
}

/**
 * Get the ruflo version that this HLK config was tested against.
 * @returns {string}
 */
function getTestedRufloVersion() {
  return config.ruflo_version_tested || 'unknown';
}

export default {
  isEnabled,
  sanitize,
  getSecret,
  getVersion,
  getTestedRufloVersion,
  config,
};
