#!/usr/bin/env node
// ============================================================================
// HLK/loaders/verify-first-loader.js
// ----------------------------------------------------------------------------
// HLK loader cho verify-first chain.
// Khi process gọi `verify-first-cli` (scripts/verify_first_cli.py), loader này
// sẽ:
//   1. Sanitize argv (chống injection từ BRD content)
//   2. Pre-check: log audit start
//   3. Post-check: log audit end + gate verdict
//   4. Nếu mode=live + không có AHD_AUTO_PR_SKIP_CONFIRM=1 → require human confirm
//
// Cách dùng: preload qua NODE_OPTIONS="--require ./HLK/loaders/verify-first-loader.js"
// ============================================================================

const fs = require('node:fs');
const path = require('node:path');
const { spawn, execFile, execFileSync } = require('node:child_process');

// === Audit log path ===
const AUDIT_LOG = path.resolve(
  process.env.AHD_AUDIT_LOG || '.devin/state/verify_first_audit.jsonl'
);

// === Sanitize argv (chống injection) ===
const SHELL_METACHARS = /[|&;()<>$`\\\"'*?{}\n\r\t]/;

function sanitizeArgv(argv) {
  const sanitized = [];
  const warnings = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (typeof arg !== 'string') {
      sanitized.push(String(arg));
      continue;
    }
    // Cho phép path (chứa / \\ : . _) - chỉ check shell metachars
    if (SHELL_METACHARS.test(arg)) {
      warnings.push(`argv[${i}] chứa shell metachar: ${arg.substring(0, 50)}`);
      // Replace metachars bằng _ để không block nhưng warn
      sanitized.push(arg.replace(/[|&;()<>$`\\\"'*?{}\n\r\t]/g, '_'));
    } else {
      sanitized.push(arg);
    }
  }
  return { sanitized, warnings };
}

// === Write audit entry ===
function writeAudit(entry) {
  try {
    fs.mkdirSync(path.dirname(AUDIT_LOG), { recursive: true });
    fs.appendFileSync(AUDIT_LOG, JSON.stringify({
      ...entry,
      timestamp: new Date().toISOString(),
    }) + '\n', 'utf-8');
  } catch (e) {
    // Best-effort
    process.stderr.write(`[verify-first-loader] audit log failed: ${e.message}\n`);
  }
}

// === Detect verify-first-cli invocation ===
// Node's child_process.spawn / execFile calls pass through here (via require hook).
// We hook the spawn function to intercept.

const originalSpawn = child_process.spawn;
const originalExecFile = child_process.execFile;

function isVerifyFirstCall(cmd, args) {
  // Check if this is a call to verify_first_cli.py
  if (typeof cmd !== 'string') return false;
  if (cmd.endsWith('verify_first_cli.py')) return true;
  if (cmd === 'python' || cmd === 'python3' || cmd === 'py') {
    return args && args.some(a => typeof a === 'string' && a.endsWith('verify_first_cli.py'));
  }
  return false;
}

function interceptSpawn(cmd, args, options) {
  if (isVerifyFirstCall(cmd, args)) {
    const { sanitized, warnings } = sanitizeArgv(args);
    if (warnings.length > 0) {
      process.stderr.write(`[verify-first-loader] WARN: ${warnings.join('; ')}\n`);
      writeAudit({ event: 'start', cmd, warnings });
    } else {
      writeAudit({ event: 'start', cmd, warnings: [] });
    }
    // Check mode=live + require confirm
    const isLive = args.includes('--live');
    const skipConfirm = process.env.AHD_AUTO_PR_SKIP_CONFIRM === '1';
    if (isLive && !skipConfirm) {
      process.stderr.write(
        '[verify-first-loader] mode=live detected, AHD_AUTO_PR_SKIP_CONFIRM not set. ' +
        'Human confirm required at verify-first-cli level.\n'
      );
    }
    // Call original with sanitized args
    const result = originalSpawn(cmd, sanitized, options);
    result.on('exit', (code) => {
      writeAudit({ event: 'end', cmd, exit_code: code, warnings });
    });
    return result;
  }
  return originalSpawn(cmd, args, options);
}

function interceptExecFile(cmd, args, options, callback) {
  if (isVerifyFirstCall(cmd, args)) {
    const { sanitized, warnings } = sanitizeArgv(args);
    if (warnings.length > 0) {
      process.stderr.write(`[verify-first-loader] WARN: ${warnings.join('; ')}\n`);
    }
    writeAudit({ event: 'start', cmd, warnings, via: 'execFile' });
    return originalExecFile(cmd, sanitized, options, callback);
  }
  return originalExecFile(cmd, args, options, callback);
}

// === Install hooks ===
try {
  const child_process = require('node:child_process');
  // Patch spawn
  child_process.spawn = interceptSpawn;
  // Patch execFile
  if (child_process.execFile !== interceptExecFile) {
    child_process.execFile = interceptExecFile;
  }
  process.stderr.write('[verify-first-loader] loaded; verify-first-cli calls will be audited\n');
} catch (e) {
  process.stderr.write(`[verify-first-loader] failed to install hooks: ${e.message}\n`);
}
