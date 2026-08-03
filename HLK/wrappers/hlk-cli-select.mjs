// ============================================================================
// HLK/wrappers/hlk-cli-select.mjs
// ----------------------------------------------------------------------------
// Module dùng chung cho các installer HLK: hỏi human đang dùng CLI nào,
// trả về đúng đường dẫn cấu hình / file MCP / thư mục skills cho CLI đó.
//
// Mục đích:
//   Trước đây các installer hard-code cho Claude Code (.claude/settings.json),
//   nên Devin CLI và Antigravity CLI không thấy MCP server của ruflo, dẫn tới
//   ruflo không nhận diện được CLI đang chạy và chỉ theo rule của Claude.
//
//   Giờ đây, installer hỏi thẳng human: "Bạn đang dùng CLI nào?"
//   Rồi chỉ cấu hình cho CLI đó (hoặc cả 3 nếu chọn "all").
//
// Cách dùng (từ installer .mjs):
//   import { promptCli, cliTargets, CLI_INFO, hookCommand } from '../wrappers/hlk-cli-select.mjs';
//   const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
//   const choice = await promptCli(rl);        // 'claude' | 'devin' | 'agy' | 'all'
//   rl.close();
//   const targets = cliTargets(choice);       // ['claude'] hoặc ['claude','devin','agy']
//   for (const cli of targets) {
//     const dir   = cliConfigDir(ws, cli);     // .claude | .devin | .agents
//     const mcp   = cliMcpConfigPath(ws, cli); // .../settings.json hoặc mcp_config.json
//     const skills= cliSkillsDir(ws, cli);     // .../skills
//     // ... ghi file cấu hình cho CLI này
//   }
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';

// ---------------------------------------------------------------------------
// Danh sách CLI được hỗ trợ + thông tin đường dẫn riêng của từng CLI
// ---------------------------------------------------------------------------

/**
 * Thông tin cấu hình cho từng CLI.
 * - claude: Claude Code  → .claude/settings.json  (mcpServers + hooks cùng file)
 * - devin: Devin CLI     → .devin/mcp_config.json  (MCP) + .devin/hooks.v1.json (hooks)
 * - agy:   Antigravity   → .agents/mcp_config.json (MCP) + .agents/config.toml (settings)
 *
 * Lưu ý: mỗi CLI đọc MCP từ file khác nhau, nên phải ghi đúng file của CLI đó.
 */
export const CLI_INFO = {
  claude: {
    displayName: 'Claude Code',
    configDir: '.claude',
    // Claude Code giữ cả hooks và mcpServers trong cùng settings.json
    settingsFile: 'settings.json',
    mcpFile: 'settings.json',     // MCP nằm trong settings.json (khóa mcpServers)
    hooksFile: 'settings.json',   // hooks cũng trong settings.json (khóa hooks)
    skillsSubdir: 'skills',
    // Claude Code có $CLAUDE_PROJECT_DIR, nhưng launcher trung tính không cần
    projectDirEnv: 'CLAUDE_PROJECT_DIR',
  },
  devin: {
    displayName: 'Devin CLI',
    configDir: '.devin',
    settingsFile: 'config.json',
    mcpFile: 'mcp_config.json',
    hooksFile: 'hooks.v1.json',
    skillsSubdir: 'skills',
    // Devin CLI không định nghĩa biến project dir chuẩn → dùng launcher trung tính
    projectDirEnv: null,
  },
  agy: {
    displayName: 'Antigravity CLI (agy)',
    configDir: '.agents',
    settingsFile: 'config.toml',
    mcpFile: 'mcp_config.json',
    hooksFile: null,               // agy không có file hooks riêng (chỉ MCP)
    skillsSubdir: 'skills',
    projectDirEnv: null,
  },
};

/**
 * Hook command trung tính — KHÔNG dùng $CLAUDE_PROJECT_DIR.
 * Dùng path tương đối 'HLK/wrappers/hlk-hook-launcher.mjs' từ workspace root.
 * Cả 3 CLI đều chạy hook với cwd = workspace root, nên path tương đối work.
 *
 * Launcher sẽ tự tìm HLK dir (qua process.cwd() hoặc __dirname) rồi gọi
 * hlk-hook-bridge.mjs — không phụ thuộc biến môi trường của CLI nào.
 */
export function hookCommand(timeout = 5000) {
  return {
    type: 'command',
    command: 'node HLK/wrappers/hlk-hook-launcher.mjs',
    timeout,
  };
}

// ---------------------------------------------------------------------------
// Hỏi human đang dùng CLI nào
// ---------------------------------------------------------------------------

/**
 * Hỏi human chọn CLI đang dùng. Trả về:
 *   'claude' | 'devin' | 'agy' | 'all'
 *
 * @param {readline.Interface} rl  - interface đã tạo từ installer
 * @param {string} defaultChoice   - mặc định nếu user Enter (default: 'all')
 */
export function promptCli(rl, defaultChoice = 'all') {
  return new Promise((resolve) => {
    process.stderr.write('\n');
    process.stderr.write('═══ Bạn đang dùng CLI nào? ═══\n');
    process.stderr.write('  1. Claude Code        (.claude/)\n');
    process.stderr.write('  2. Devin CLI          (.devin/)\n');
    process.stderr.write('  3. Antigravity CLI    (.agents/)\n');
    process.stderr.write('  4. Tất cả (cả 3 CLI)  ← khuyến nghị nếu dùng nhiều CLI\n');
    process.stderr.write(`Nhập số (1-4) [mặc định: ${defaultChoice === 'all' ? '4' : defaultChoice}]: `);

    rl.question('', (answer) => {
      const trimmed = (answer || '').trim().toLowerCase();
      const map = {
        '1': 'claude', 'claude': 'claude', 'c': 'claude',
        '2': 'devin', 'devin': 'devin', 'd': 'devin',
        '3': 'agy', 'agy': 'agy', 'antigravity': 'agy', 'a': 'agy',
        '4': 'all', 'all': 'all',
      };
      resolve(map[trimmed] || defaultChoice);
    });
  });
}

/**
 * Chuyển lựa chọn ('claude' | 'devin' | 'agy' | 'all') thành mảng CLI cần cấu hình.
 */
export function cliTargets(choice) {
  if (choice === 'all') return ['claude', 'devin', 'agy'];
  if (CLI_INFO[choice]) return [choice];
  // Fallback an toàn: cấu hình cả 3
  return ['claude', 'devin', 'agy'];
}

// ---------------------------------------------------------------------------
// Trả về đường dẫn cấu hình cho từng CLI
// ---------------------------------------------------------------------------

/** Thư mục config của CLI trong workspace (ví dụ .claude, .devin, .agents). */
export function cliConfigDir(ws, cli) {
  return path.join(ws, CLI_INFO[cli].configDir);
}

/** File settings chính của CLI (có thể chứa cả hooks + MCP tùy CLI). */
export function cliSettingsPath(ws, cli) {
  return path.join(cliConfigDir(ws, cli), CLI_INFO[cli].settingsFile);
}

/** File MCP config của CLI (nơi khai báo mcpServers). */
export function cliMcpConfigPath(ws, cli) {
  return path.join(cliConfigDir(ws, cli), CLI_INFO[cli].mcpFile);
}

/** File hooks của CLI (nếu CLI có file hooks riêng; null nếu gộp trong settings). */
export function cliHooksPath(ws, cli) {
  if (!CLI_INFO[cli].hooksFile) return null;
  return path.join(cliConfigDir(ws, cli), CLI_INFO[cli].hooksFile);
}

/** Thư mục skills của CLI trong workspace. */
export function cliSkillsDir(ws, cli) {
  return path.join(cliConfigDir(ws, cli), CLI_INFO[cli].skillsSubdir);
}

/** Tên hiển thị của CLI (cho log). */
export function cliDisplayName(cli) {
  return CLI_INFO[cli]?.displayName || cli;
}

// ---------------------------------------------------------------------------
// Đảm bảo thư mục config + skills của CLI tồn tại
// ---------------------------------------------------------------------------

export function ensureCliDirs(ws, cli) {
  const configDir = cliConfigDir(ws, cli);
  fs.mkdirSync(configDir, { recursive: true });
  const skillsDir = cliSkillsDir(ws, cli);
  fs.mkdirSync(skillsDir, { recursive: true });
  return { configDir, skillsDir };
}
