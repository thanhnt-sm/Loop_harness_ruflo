/**
 * HLK Data Sanitizer
 * Scrubs sensitive data (API keys, passwords, tokens, connection strings)
 * from text before it is sent to memory, logs, or external APIs.
 *
 * Usage:
 *   import { sanitize, createSanitizer } from './sanitizer.js';
 *   const clean = sanitize("my key is sk-abc123def456...");
 *   // → "my key is [REDACTED]"
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CONFIG_PATH = path.join(__dirname, '../config/hlk.config.json');

/**
 * Load redact patterns from HLK config.
 * Falls back to built-in defaults if config is unreadable.
 */
function loadPatterns() {
  const DEFAULTS = [
    'sk-[a-zA-Z0-9]{32,}',
    'ghp_[a-zA-Z0-9]{36}',
    '(?i)password\\s*=\\s*[\'"]?[^\'"\\s]+',
    '(?i)api[_-]?key\\s*=\\s*[\'"]?[^\'"\\s]+',
    '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
  ];

  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    const cfg = JSON.parse(raw);
    const patterns = cfg?.security_rules?.redact_patterns;
    const replacement = cfg?.security_rules?.redact_replacement || '[REDACTED]';
    if (Array.isArray(patterns) && patterns.length > 0) {
      return { patterns, replacement };
    }
  } catch {
    // Config unreadable — use defaults
  }
  return { patterns: DEFAULTS, replacement: '[REDACTED]' };
}

/**
 * Create a reusable sanitizer function with compiled regex patterns.
 * @returns {{ sanitize: (text: string) => string, patterns: RegExp[] }}
 */
export function createSanitizer() {
  const { patterns, replacement } = loadPatterns();
  const compiled = patterns.map((p) => {
    try {
      // Convert (?i) flag to RegExp 'gi' flags
      const cleaned = p.replace(/\(\?i\)/g, '');
      const flags = p.includes('(?i)') ? 'gi' : 'g';
      return new RegExp(cleaned, flags);
    } catch {
      console.warn(`[HLK Sanitizer] Invalid regex pattern skipped: ${p}`);
      return null;
    }
  }).filter(Boolean);

  function sanitize(text) {
    if (typeof text !== 'string') return text;
    let result = text;
    for (const re of compiled) {
      result = result.replace(re, replacement);
    }
    return result;
  }

  return { sanitize, patterns: compiled };
}

// Default singleton instance
const defaultSanitizer = createSanitizer();

/**
 * Sanitize a string using the default HLK patterns.
 * @param {string} text - The text to sanitize.
 * @returns {string} Sanitized text with sensitive data replaced.
 */
export function sanitize(text) {
  return defaultSanitizer.sanitize(text);
}

/**
 * Sanitize all string values in a plain object (shallow).
 * @param {Record<string, any>} obj
 * @returns {Record<string, any>}
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
