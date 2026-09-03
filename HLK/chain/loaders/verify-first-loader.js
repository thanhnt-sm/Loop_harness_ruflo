#!/usr/bin/env node
// ============================================================================
// HLK/chain/loaders/verify-first-loader.js
// ----------------------------------------------------------------------------
// HLK loader cho verify-first chain (scoped version, Plan 8 phase 2).
// Không patch global child_process.spawn mặc định. Phải gọi
// enablePatching() explicitly để activate.
//
// Cách dùng:
//   // 1. Standalone: tự wrap khi gọi
//   import { wrapSpawn } from 'HLK/chain/loaders/wrap_helpers.js';
//   const child = wrapSpawn(originalSpawn)(cmd, args);
//
//   // 2. Opt-in global patch (khi load qua require với env flag)
//   if (process.env.HLK_VERIFY_FIRST_ACTIVE === '1') {
//     const cp = await import('node:child_process');
//     const { enablePatching } = await import('./wrap_helpers.js');
//     enablePatching(cp);
//   }
// ============================================================================

import {
  enablePatching,
  disablePatching,
  isPatched,
  wrapSpawn,
  wrapExecFile,
  sanitizeArgv,
} from './wrap_helpers.js';

const SHELL_METACHARS_RE = /[|&;()<>$`\\\"'*?{}\n\r\t]/;

// === Audit log ===
const AUDIT_LOG = process.env.AHD_AUDIT_LOG || '.devin/state/verify_first_audit.jsonl';

/**
 * Detect if a subprocess call is for verify-first CLI.
 */
function isVerifyFirstCall(cmd, args) {
  if (typeof cmd !== 'string') return false;
  if (cmd.endsWith('verify_first_cli.py')) return true;
  if (['python', 'python3', 'py'].includes(cmd)) {
    return Array.isArray(args) && args.some((a) => typeof a === 'string' && a.endsWith('verify_first_cli.py'));
  }
  return false;
}

/**
 * Intercept spawn calls (only when enabled).
 */
function interceptSpawn(cmd, args, options) {
  if (!isVerifyFirstCall(cmd, args)) {
    return _origSpawnRef(cmd, args, options);
  }
  const { sanitized, warnings } = sanitizeArgv([cmd, ...(args || [])]);
  if (warnings.length > 0) {
    process.stderr.write(`[verify-first-loader] WARN: ${warnings.join('; ')}\n`);
  }
  const [cleanCmd, ...cleanArgs] = sanitized;
  if (process.env.AHD_AUDIT_LOG) {
    try {
      require('node:fs').appendFileSync(AUDIT_LOG, JSON.stringify({
        event: 'spawn', cmd: cleanCmd, args: cleanArgs, timestamp: new Date().toISOString(),
      }) + '\n');
    } catch (e) { /* best-effort */ }
  }
  return _origSpawnRef(cleanCmd, cleanArgs, options);
}

/**
 * Intercept execFile calls.
 */
function interceptExecFile(cmd, args, options, callback) {
  if (!isVerifyFirstCall(cmd, args)) {
    return _origExecFileRef(cmd, args, options, callback);
  }
  const { sanitized, warnings } = sanitizeArgv([cmd, ...(args || [])]);
  if (warnings.length > 0) {
    process.stderr.write(`[verify-first-loader] WARN: ${warnings.join('; ')}\n`);
  }
  const [cleanCmd, ...cleanArgs] = sanitized;
  return _origExecFileRef(cleanCmd, cleanArgs, options, callback);
}

// === Public API: scoped patching (Plan 8 phase 2) ===
let _origSpawnRef = null;
let _origExecFileRef = null;

async function enableScopedPatching() {
  if (isPatched()) return false;
  const cp = await import('node:child_process');
  _origSpawnRef = cp.spawn;
  _origExecFileRef = cp.execFile;
  cp.spawn = function (cmd, args, opts) {
    return interceptSpawn.call(this, cmd, args, opts);
  };
  cp.execFile = function (cmd, args, opts, cb) {
    return interceptExecFile.call(this, cmd, args, opts, cb);
  };
  // Use the enablePatching from wrap_helpers for proper state tracking
  enablePatching(cp);
  process.stderr.write('[verify-first-loader] scoped patching ENABLED\n');
  return true;
}

async function disableScopedPatching() {
  if (!isPatched()) return false;
  const cp = await import('node:child_process');
  disablePatching(cp);
  // Restore the original references
  cp.spawn = _origSpawnRef;
  cp.execFile = _origExecFileRef;
  process.stderr.write('[verify-first-loader] scoped patching DISABLED\n');
  return true;
}

// === Auto-enable if env var set ===
if (process.env.HLK_VERIFY_FIRST_ACTIVE === '1') {
  // Async fire-and-forget; won't block import
  enableScopedPatching().catch((e) => {
    process.stderr.write(`[verify-first-loader] auto-enable failed: ${e.message}\n`);
  });
}
