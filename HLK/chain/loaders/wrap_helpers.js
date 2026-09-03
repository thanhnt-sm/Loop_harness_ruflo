// ============================================================================
// HLK/chain/loaders/wrap_helpers.js
// ----------------------------------------------------------------------------
// Standalone wrap helpers cho child_process.spawn + execFile.
// Tách ra để tránh patch global (Plan 8 phase 2).
//
// Cách dùng:
//   import { wrapSpawn, wrapExecFile, enablePatching, disablePatching } from './wrap_helpers.js';
//
//   // Opt-in patch (default: NO side effects on import)
//   enablePatching();
//   // ... code ...
//   disablePatching();  // restore original
// ============================================================================

import { spawn as _origSpawn, execFile as _origExecFile } from 'node:child_process';

const _SHELL_METACHARS = /[|&;()<>$`\\\"'*?{}\n\r\t]/;

let _patched = false;
let _origSpawnRef = _origSpawn;
let _origExecFileRef = _origExecFile;

/**
 * Sanitize argv (chống injection).
 */
function sanitizeArgv(argv) {
  const sanitized = [];
  const warnings = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (typeof arg !== 'string') {
      sanitized.push(String(arg));
      continue;
    }
    if (_SHELL_METACHARS.test(arg)) {
      warnings.push(`argv[${i}] contains shell metachar: ${arg.substring(0, 50)}`);
      sanitized.push(arg.replace(_SHELL_METACHARS, '_'));
    } else {
      sanitized.push(arg);
    }
  }
  return { sanitized, warnings };
}

/**
 * Wrap một spawn function với argv sanitization.
 */
function wrapSpawn(originalSpawn, options = {}) {
  return function wrappedSpawn(cmd, args, spawnOptions) {
    if (!options.enabled) {
      return originalSpawn(cmd, args, spawnOptions);
    }
    const { sanitized, warnings } = sanitizeArgv([cmd, ...(args || [])]);
    if (warnings.length > 0 && options.onWarning) {
      for (const w of warnings) options.onWarning(w);
    }
    const [cleanCmd, ...cleanArgs] = sanitized;
    return originalSpawn(cleanCmd, cleanArgs, spawnOptions);
  };
}

/**
 * Wrap một execFile function.
 */
function wrapExecFile(originalExecFile, options = {}) {
  return function wrappedExecFile(cmd, args, execOptions, callback) {
    if (!options.enabled) {
      return originalExecFile(cmd, args, execOptions, callback);
    }
    const { sanitized, warnings } = sanitizeArgv([cmd, ...(args || [])]);
    if (warnings.length > 0 && options.onWarning) {
      for (const w of warnings) options.onWarning(w);
    }
    const [cleanCmd, ...cleanArgs] = sanitized;
    return originalExecFile(cleanCmd, cleanArgs, execOptions, callback);
  };
}

/**
 * Enable global patching. Idempotent.
 */
function enablePatching(childProcessModule, options = {}) {
  if (_patched) return false;
  _origSpawnRef = childProcessModule.spawn;
  _origExecFileRef = childProcessModule.execFile;
  childProcessModule.spawn = wrapSpawn(_origSpawnRef, { enabled: true, ...options });
  childProcessModule.execFile = wrapExecFile(_origExecFileRef, { enabled: true, ...options });
  _patched = true;
  return true;
}

/**
 * Disable global patching. Restore original.
 */
function disablePatching(childProcessModule) {
  if (!_patched) return false;
  if (childProcessModule) {
    childProcessModule.spawn = _origSpawnRef;
    childProcessModule.execFile = _origExecFileRef;
  }
  _patched = false;
  return true;
}

/**
 * Check if currently patched.
 */
function isPatched() {
  return _patched;
}

export {
  wrapSpawn,
  wrapExecFile,
  enablePatching,
  disablePatching,
  isPatched,
  sanitizeArgv,
};
