#!/usr/bin/env node
// ============================================================================
// .devin/scripts/hlk_wrappers/verify-first-wrapper.mjs
// ----------------------------------------------------------------------------
// CLI wrapper cho verify-first chain (mirror của HLK/wrappers/).
// Vì HLK/ permissions không cho phép edit từ session này, wrapper được
// lưu ở .devin/scripts/hlk_wrappers/ để cross-platform safe.
// HLK loader tự tham chiếu path này.
//
// Cách dùng:
//   node .devin/scripts/hlk_wrappers/verify-first-wrapper.mjs <BRD.md> [options]
// ============================================================================

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, appendFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// === Detect platform ===
const isWindows = process.platform === 'win32';
const pythonCmd = isWindows ? 'py' : 'python3';

// === Audit log ===
const AUDIT_LOG = resolve(
  process.env.AHD_AUDIT_LOG || '.devin/state/verify_first_audit.jsonl'
);

function writeAudit(entry) {
  try {
    mkdirSync(dirname(AUDIT_LOG), { recursive: true });
    appendFileSync(AUDIT_LOG, JSON.stringify({
      ...entry,
      timestamp: new Date().toISOString(),
    }) + '\n', 'utf-8');
  } catch (e) {
    process.stderr.write(`[verify-first-wrapper] audit log failed: ${e.message}\n`);
  }
}

// === Resolve CLI path ===
const CLI_PATH = resolve(__dirname, '../../../scripts/verify_first_cli.py');

if (!existsSync(CLI_PATH)) {
  process.stderr.write(`[verify-first-wrapper] CLI not found: ${CLI_PATH}\n`);
  process.exit(2);
}

// === Parse args ===
const args = process.argv.slice(2);
if (args.length === 0) {
  process.stderr.write('Usage: node .devin/scripts/hlk_wrappers/verify-first-wrapper.mjs <BRD.md> [options]\n');
  process.exit(2);
}

// === Spawn CLI ===
writeAudit({ event: 'wrapper_start', args, python_cmd: pythonCmd });

const child = spawn(pythonCmd, [CLI_PATH, ...args], {
  stdio: 'inherit',
  env: process.env,
});

child.on('exit', (code) => {
  writeAudit({ event: 'wrapper_end', args, exit_code: code });
  process.exit(code ?? 1);
});

child.on('error', (err) => {
  process.stderr.write(`[verify-first-wrapper] spawn error: ${err.message}\n`);
  writeAudit({ event: 'wrapper_error', args, error: err.message });
  process.exit(1);
});
