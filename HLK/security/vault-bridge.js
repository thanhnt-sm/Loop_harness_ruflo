/**
 * HLK Vault Bridge
 * Manages secrets/API keys independently from ruflo core.
 *
 * Strategy:
 *   1. Reads from process.env first (OS-level secrets)
 *   2. Falls back to HLK/config/secrets.env (gitignored local file)
 *   3. Never stores secrets in hlk.config.json or any tracked file
 *
 * Usage:
 *   import { getSecret, hasSecret, listSecretKeys } from './vault-bridge.js';
 *   const apiKey = getSecret('OPENAI_API_KEY');
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SECRETS_PATH = path.join(__dirname, '../config/secrets.env');

/** @type {Map<string, string>} */
const secretsCache = new Map();
let loaded = false;

/**
 * Parse a simple .env file (KEY=VALUE per line, # comments, no interpolation).
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
      // Strip surrounding quotes
      if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1);
      }
      map.set(key, value);
    }
  } catch (err) {
    console.warn('[HLK Vault] Could not read secrets.env:', err.message);
  }
  return map;
}

/**
 * Load secrets from the local secrets.env file into cache.
 * Only loads once; call reload() to force refresh.
 */
function ensureLoaded() {
  if (loaded) return;
  const fileSecrets = parseDotEnv(SECRETS_PATH);
  for (const [k, v] of fileSecrets) {
    secretsCache.set(k, v);
  }
  loaded = true;
}

/**
 * Get a secret value. Checks process.env first, then local secrets file.
 * @param {string} key - The secret key name.
 * @param {string} [defaultValue] - Fallback if not found.
 * @returns {string | undefined}
 */
export function getSecret(key, defaultValue) {
  // Process env always takes precedence
  if (process.env[key] !== undefined) {
    return process.env[key];
  }
  ensureLoaded();
  return secretsCache.get(key) ?? defaultValue;
}

/**
 * Check if a secret exists (in env or local file).
 * @param {string} key
 * @returns {boolean}
 */
export function hasSecret(key) {
  if (process.env[key] !== undefined) return true;
  ensureLoaded();
  return secretsCache.has(key);
}

/**
 * List all known secret key names (from local file only — env vars are not enumerable safely).
 * @returns {string[]}
 */
export function listSecretKeys() {
  ensureLoaded();
  return [...secretsCache.keys()];
}

/**
 * Force reload secrets from disk.
 */
export function reload() {
  secretsCache.clear();
  loaded = false;
  ensureLoaded();
}

/**
 * Get the path to the secrets file (for diagnostics).
 * @returns {string}
 */
export function getSecretsPath() {
  return SECRETS_PATH;
}

export default { getSecret, hasSecret, listSecretKeys, reload, getSecretsPath };
