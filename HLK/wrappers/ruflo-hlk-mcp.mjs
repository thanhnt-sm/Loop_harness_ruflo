#!/usr/bin/env node
/**
 * Ruflo HLK MCP Launcher
 * =======================
 * Mục đích tổng thể:
 *   Khởi động Ruflo MCP server qua `npx ruflo@latest mcp start`
 *   với HLK loader được preload, để HLK can thiệp ngay cả tiến trình
 *   MCP server (telemetry, custom hooks, argv sanitize).
 *
 * Đây là wrapper dành riêng cho `.claude/settings.json` → `mcpServers`.
 * Không cần build local; luôn dùng bản publish mới nhất.
 *
 * Cách dùng trong .claude/settings.json:
 *   "mcpServers": {
 *     "claude-flow": {
 *       "command": "node",
 *       "args": [
 *         "HLK/wrappers/ruflo-hlk-mcp.mjs",
 *         "mcp",
 *         "start"
 *       ]
 *     }
 *   }
 */

import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// Bước 1: Xác định đường dẫn gốc repo và loader
// ---------------------------------------------------------------------------

const REPO_ROOT = resolve(__dirname, '..', '..');
const LOADER_URL = pathToFileURL(resolve(REPO_ROOT, 'HLK/wrappers/hlk-loader.js')).href;

// ---------------------------------------------------------------------------
// Bước 2: Chuẩn bị môi trường
// ---------------------------------------------------------------------------

const env = { ...process.env };

if (!env.NODE_OPTIONS) {
  env.NODE_OPTIONS = `--import=${LOADER_URL}`;
} else if (!env.NODE_OPTIONS.includes('--import=')) {
  env.NODE_OPTIONS += ` --import=${LOADER_URL}`;
}

// ---------------------------------------------------------------------------
// Bước 3: Spawn npx ruflo@latest với args
// ---------------------------------------------------------------------------

const cliArgs = process.argv.slice(2);

const child = spawn(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['-y', 'ruflo@latest', ...cliArgs], {
  cwd: REPO_ROOT,
  env,
  stdio: 'inherit',
  shell: false,
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});

child.on('error', (err) => {
  process.stderr.write(`[ruflo-hlk-mcp] Lỗi spawn: ${err.message}\n`);
  process.exit(1);
});
