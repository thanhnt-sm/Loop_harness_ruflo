#!/usr/bin/env node
// ============================================================================
// HLK/wrappers/hlk-hook-launcher.mjs
// ----------------------------------------------------------------------------
// Hook launcher trung tính — KHÔNG phụ thuộc $CLAUDE_PROJECT_DIR.
//
// Vấn đề trước đây:
//   .claude/settings.json và .devin/hooks.v1.json đều dùng:
//     node "$CLAUDE_PROJECT_DIR/HLK/wrappers/hlk-hook-bridge.mjs"
//   Khi chạy từ Devin CLI hoặc Antigravity, $CLAUDE_PROJECT_DIR rỗng
//   → hook không bao giờ chạy → HLK không can thiệp được.
//
// Giải pháp:
//   Launcher này tự tìm HLK dir bằng 2 cách (theo thứ tự):
//     1. process.cwd()/HLK        — vì mọi CLI chạy hook với cwd = workspace root
//     2. __dirname                — vì launcher nằm trong HLK/wrappers/ (fallback)
//   Sau đó spawn hlk-hook-bridge.mjs, truyền stdin qua, trả exit code của bridge.
//
// Cách dùng (trong settings.json / hooks.v1.json của MỌI CLI):
//   "command": "node HLK/wrappers/hlk-hook-launcher.mjs"
//
// Lưu ý: dùng path tương đối "HLK/wrappers/hlk-hook-launcher.mjs" vì
//   cwd lúc chạy hook luôn là workspace root (đã kiểm chứng với 3 CLI).
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---------------------------------------------------------------------------
// Bước 1: Tìm HLK dir
// ---------------------------------------------------------------------------

/**
 * Trả về đường dẫn tuyệt đối tới thư mục HLK trong workspace.
 * Thử theo thứ tự:
 *   1. process.cwd()/HLK   — trường hợp chuẩn (cwd = workspace root)
 *   2. __dirname/..         — fallback (launcher nằm trong HLK/wrappers/)
 */
function resolveHlkDir() {
  const candidates = [
    path.join(process.cwd(), 'HLK'),
    path.resolve(__dirname, '..'),
  ];

  for (const dir of candidates) {
    const bridge = path.join(dir, 'wrappers', 'hlk-hook-bridge.mjs');
    if (fs.existsSync(bridge)) {
      return dir;
    }
  }

  // Không tìm thấy — trả candidate đầu tiên để log lỗi rõ
  return candidates[0];
}

const HLK_DIR = resolveHlkDir();
const BRIDGE_PATH = path.join(HLK_DIR, 'wrappers', 'hlk-hook-bridge.mjs');

if (!fs.existsSync(BRIDGE_PATH)) {
  process.stderr.write(`[HLK Launcher] ❌ Không tìm thấy hlk-hook-bridge.mjs tại ${BRIDGE_PATH}\n`);
  process.stderr.write(`[HLK Launcher]    cwd = ${process.cwd()}\n`);
  process.stderr.write(`[HLK Launcher]    __dirname = ${__dirname}\n`);
  // Fail-closed: nếu HLK bridge không tồn tại, chặn tool để tránh secret lọt qua
  process.exit(2);
} else {
  // ---------------------------------------------------------------------------
  // Bước 2: Spawn hlk-hook-bridge.mjs, pipe stdin/stdout/stderr qua
  // ---------------------------------------------------------------------------

  const child = spawn(process.execPath, [BRIDGE_PATH], {
    stdio: ['pipe', 'inherit', 'inherit'],
  });

  // Pipe stdin của launcher sang stdin của bridge
  process.stdin.pipe(child.stdin);

  child.on('exit', (code, signal) => {
    if (signal) process.exit(1);
    process.exit(code ?? 0);
  });

  child.on('error', (err) => {
    process.stderr.write(`[HLK Launcher] ❌ Lỗi spawn bridge: ${err.message}\n`);
    // Fail-closed: không thể spawn bridge → chặn tool
    process.exit(2);
  });
}
