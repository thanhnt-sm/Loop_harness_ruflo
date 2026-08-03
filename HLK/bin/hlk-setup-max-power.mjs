#!/usr/bin/env node
// ============================================================================
// HLK/bin/hlk-setup-max-power.mjs
// ----------------------------------------------------------------------------
// Script thiết lập Ruflo ở mức "MAX POWER" cho một workspace bất kỳ.
//
// VAI TRÒ: Orchestrator chính — cài đặt đầy đủ Ruflo + HLK + 3 CLI + provider.
//           Đây là script KHUYẾN NGHỊ cho người mới.
//
// KHI NÀO DÙNG SCRIPT NÀO TRONG HLK/bin/:
//   - Cài MAX POWER đầy đủ (Ruflo + HLK + 3 CLI + provider tuning):
//       → hlk-setup-max-power.mjs (script này)
//   - Update/re-patch/upgrade workspace đã có MAX POWER:
//       → hlk-update-max-power.mjs
//   - Lifecycle đơn giản (init + install HLK, không MAX POWER):
//       → hlk-lifecycle.mjs
//   - Chỉ cài HLK vào workspace đã có ruflo:
//       → hlk-install.mjs
//   - Chỉ update HLK trong workspace:
//       → hlk-update.mjs
//   - Kiểm tra trạng thái HLK:
//       → hlk-status.mjs
//   - Đóng gói HLK thành .tgz (chỉ trong repo HLK):
//       → hlk-pack.mjs / hlk-repack.mjs
//
// Mục tiêu:
//   - Hỗ trợ cài Ruflo CỤC BỘ trong workspace (--local) hoặc dùng global.
//   - Hỏi đường dẫn workspace cần thiết lập.
//   - Tự động thiết lập tối đa: ruflo chạy full chain / full flow,
//     mọi thông số đẩy lên mức cao nhất, mọi tính năng bật mạnh nhất.
//   - Thiết lập đồng bộ cho 3 CLI: Claude Code, Devin CLI, Antigravity CLI (agy).
//   - Tinh chỉnh cấu hình cho từng AI provider (Claude, Codex, Gemini, OpenAI).
//
// Cách dùng:
//   node HLK/bin/hlk-setup-max-power.mjs                          # hỏi path + global
//   node HLK/bin/hlk-setup-max-power.mjs --local                  # cài ruflo cục bộ workspace
//   node HLK/bin/hlk-setup-max-power.mjs --path D:/projects/my-ws --yes --local
//
// Options:
//   --path <dir>   Đường dẫn workspace (bỏ qua bước hỏi).
//   --yes          Không hỏi xác nhận (chạy headless).
//   --local        Cài ruflo CỤC BỘ trong workspace (npm install, không global).
//   --skip-ruflo   Bỏ qua bước cài Ruflo (giả sử đã cài).
//   --skip-hlk     Bỏ qua bước cài HLK layer.
//   --skip-devin   Bỏ qua cấu hình Devin CLI (.devin/).
//   --skip-agy     Bỏ qua cấu hình Antigravity CLI (agy).
//   --skip-providers  Bỏ qua tinh chỉnh provider.
//   --provider <name>  Provider mặc định: claude | codex | gemini | openai (mặc định: claude).
//   --ruflo-version <ver>  Phiên bản ruflo (mặc định: latest).
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Parse tham số dòng lệnh (mọi flag đều có mặc định, --yes bỏ qua hỏi) ---
// Mặc định: LOCAL=true (cài cục bộ), mọi tính năng bật, provider=claude.
let USER_PATH = null;
let YES = false;
let LOCAL = true;          // Mặc định: cài CỤC BỘ
let SKIP_RUFLO = false;
let SKIP_HLK = false;
let SKIP_DEVIN = false;
let SKIP_AGY = false;
let SKIP_PROVIDERS = false;
let PROVIDER = 'claude';
let RUFLO_VERSION = 'latest';

// Các flag đã được set qua CLI args (để biết cái nào cần hỏi, cái nào đã có)
const CLI_SET = new Set();

const rawArgs = process.argv.slice(2);
for (let i = 0; i < rawArgs.length; i++) {
  const a = rawArgs[i];
  if (a === '--path' && rawArgs[i + 1]) { USER_PATH = rawArgs[i + 1]; CLI_SET.add('path'); i++; }
  else if (a === '--yes' || a === '-y') { YES = true; CLI_SET.add('yes'); }
  else if (a === '--local') { LOCAL = true; CLI_SET.add('local'); }
  else if (a === '--global') { LOCAL = false; CLI_SET.add('local'); }
  else if (a === '--skip-ruflo') { SKIP_RUFLO = true; CLI_SET.add('skip-ruflo'); }
  else if (a === '--skip-hlk') { SKIP_HLK = true; CLI_SET.add('skip-hlk'); }
  else if (a === '--skip-devin') { SKIP_DEVIN = true; CLI_SET.add('skip-devin'); }
  else if (a === '--skip-agy') { SKIP_AGY = true; CLI_SET.add('skip-agy'); }
  else if (a === '--skip-providers') { SKIP_PROVIDERS = true; CLI_SET.add('skip-providers'); }
  else if (a === '--provider' && rawArgs[i + 1]) { PROVIDER = rawArgs[i + 1]; CLI_SET.add('provider'); i++; }
  else if (a === '--ruflo-version' && rawArgs[i + 1]) { RUFLO_VERSION = rawArgs[i + 1]; CLI_SET.add('ruflo-version'); i++; }
  else if (a === '--help' || a === '-h') {
    process.stderr.write([
      'hlk-setup-max-power.mjs — Thiết lập Ruflo MAX POWER cho workspace',
      '',
      'Mặc định: cài CỤC BỘ (--local), hỏi tất cả tham số có đề xuất mặc định.',
      'Dùng --yes để chạy headless (không hỏi, dùng mặc định).',
      '',
      'Cách dùng:',
      '  node HLK/bin/hlk-setup-max-power.mjs                    # hỏi tương tác đầy đủ',
      '  node HLK/bin/hlk-setup-max-power.mjs --yes              # headless, dùng mặc định',
      '  node HLK/bin/hlk-setup-max-power.mjs --path D:/ws --provider codex --yes',
      '',
      'Options (ghi đè mặc định, bỏ qua câu hỏi tương ứng):',
      '  --path <dir>           Đường dẫn workspace',
      '  --yes                  Không hỏi, dùng mặc định',
      '  --local                Cài ruflo CỤC BỘ (MẶC ĐỊNH)',
      '  --global               Dùng ruflo global/npx (bật tắt --local)',
      '  --skip-ruflo           Bỏ qua cài Ruflo',
      '  --skip-hlk             Bỏ qua cài HLK layer',
      '  --skip-devin           Bỏ qua cấu hình Devin CLI',
      '  --skip-agy             Bỏ qua cấu hình Antigravity CLI (agy)',
      '  --skip-providers       Bỏ qua tinh chỉnh provider',
      '  --provider <name>      Provider: claude|codex|gemini|openai (mặc định: claude)',
      '  --ruflo-version <ver>  Version ruflo (mặc định: latest)',
    ].join('\n') + '\n');
    process.exit(0);
  }
}

// --- Tiện ích log có màu (an toàn trên Windows) ---
const USE_COLOR = process.stderr.isTTY && process.platform !== 'win32';
const c = (code, s) => USE_COLOR ? `\x1b[${code}m${s}\x1b[0m` : s;
const log = {
  info: (m) => process.stderr.write(`${c('36', 'ℹ')} ${m}\n`),
  step: (m) => process.stderr.write(`${c('32', '▸')} ${m}\n`),
  ok:   (m) => process.stderr.write(`${c('32', '✓')} ${m}\n`),
  warn: (m) => process.stderr.write(`${c('33', '⚠')} ${m}\n`),
  err:  (m) => process.stderr.write(`${c('31', '✗')} ${m}\n`),
  head: (m) => process.stderr.write(`\n${c('1;36', '═══ ' + m + ' ═══')}\n`),
};

// ============================================================================
// HỆ THỐNG HỎI TƯƠNG TÁC — hỗ trợ 3 loại prompt, đều có đề xuất mặc định
// ============================================================================

// Hỏi text input với giá trị mặc định (Enter để chấp nhận mặc định)
function askText(question, defaultVal) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(`${question} [mặc định: ${c('33', defaultVal)}]: `, (ans) => {
      rl.close();
      const t = (ans || '').trim().replace(/^["']|["']$/g, '');
      resolve(t || defaultVal);
    });
  });
}

// Hỏi yes/no với mặc định (Enter để chấp nhận mặc định)
function askBool(question, defaultVal) {
  const hint = defaultVal ? 'Y/n' : 'y/N';
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(`${question} [${hint}]: `, (ans) => {
      rl.close();
      const t = (ans || '').trim().toLowerCase();
      if (t === '') return resolve(defaultVal);
      resolve(/^y(es)?$/i.test(t));
    });
  });
}

// Hỏi chọn từ danh sách với mặc định (nhập số hoặc Enter để mặc định)
function askChoice(question, choices, defaultIdx) {
  const lines = choices.map((ch, i) => {
    const marker = i === defaultIdx ? c('33', ` → ${i + 1}. ${ch}`) : `    ${i + 1}. ${ch}`;
    return marker;
  });
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(`${question}\n${lines.join('\n')}\nChọn [mặc định: ${defaultIdx + 1}]: `, (ans) => {
      rl.close();
      const t = (ans || '').trim();
      if (t === '') return resolve(defaultIdx);
      const n = parseInt(t, 10);
      if (n >= 1 && n <= choices.length) return resolve(n - 1);
      // Cho phép nhập tên luôn
      const lower = t.toLowerCase();
      const idx = choices.findIndex((ch) => ch.toLowerCase().includes(lower));
      if (idx >= 0) return resolve(idx);
      log.warn(`Giá trị không hợp lệ, dùng mặc định: ${choices[defaultIdx]}`);
      resolve(defaultIdx);
    });
  });
}

// ============================================================================
// HỎI TẤT CẢ THAM SỐ — chỉ hỏi cái nào chưa được set qua CLI args
// ============================================================================

async function askAllParams() {
  log.head('Cấu hình thiết lập MAX POWER');

  // Nếu --yes: bỏ qua tất cả câu hỏi, dùng mặc định (hoặc flag đã truyền)
  if (YES) {
    log.info('--yes: dùng mặc định (local + claude + mọi tính năng bật).');
    return;
  }

  // 1. Workspace path
  if (!CLI_SET.has('path')) {
    USER_PATH = await askText('1. Đường dẫn workspace cần thiết lập?', process.cwd());
  }

  // 2. Local vs Global
  if (!CLI_SET.has('local')) {
    const idx = await askChoice(
      '2. Chế độ cài Ruflo?',
      ['Local (cài cục bộ trong workspace — khuyến nghị cho test)', 'Global (dùng ruflo global hoặc npx)'],
      0,  // mặc định: Local
    );
    LOCAL = idx === 0;
  }

  // 3. Provider
  if (!CLI_SET.has('provider')) {
    const idx = await askChoice(
      '3. AI Provider mặc định?',
      [
        'claude — Anthropic (reasoning, architecture, security) [khuyến nghị]',
        'codex — OpenAI Codex (implementation, optimization)',
        'gemini — Google (multimodal, research, long-context)',
        'openai — OpenAI GPT-4.1 (reasoning, general)',
      ],
      0,  // mặc định: claude
    );
    PROVIDER = ['claude', 'codex', 'gemini', 'openai'][idx];
  }

  // 4. Ruflo version
  if (!CLI_SET.has('ruflo-version')) {
    RUFLO_VERSION = await askText('4. Version Ruflo?', 'latest');
  }

  // 5. Các tính năng bật/tắt
  log.info('5. Các tính năng (bật/tắt):');

  if (!CLI_SET.has('skip-ruflo')) {
    SKIP_RUFLO = !(await askBool('   Cài/init Ruflo?', true));
  }
  if (!CLI_SET.has('skip-hlk')) {
    SKIP_HLK = !(await askBool('   Cài HLK layer (security + hooks)?', true));
  }
  if (!CLI_SET.has('skip-devin')) {
    SKIP_DEVIN = !(await askBool('   Cấu hình Devin CLI (.devin/)?', true));
  }
  if (!CLI_SET.has('skip-agy')) {
    SKIP_AGY = !(await askBool('   Cấu hình Antigravity CLI (agy)?', true));
  }
  if (!CLI_SET.has('skip-providers')) {
    SKIP_PROVIDERS = !(await askBool('   Tinh chỉnh Provider (claude/codex/gemini/openai)?', true));
  }

  // 6. Xác nhận
  if (!CLI_SET.has('yes')) {
    log.info('');
    log.info('Tóm tắt cấu hình sẽ áp dụng:');
    log.info(`  Workspace:     ${USER_PATH}`);
    log.info(`  Chế độ:        ${LOCAL ? 'LOCAL (cục bộ)' : 'GLOBAL/npx'}`);
    log.info(`  Provider:      ${PROVIDER}`);
    log.info(`  Ruflo version: ${RUFLO_VERSION}`);
    log.info(`  Cài Ruflo:     ${SKIP_RUFLO ? 'KHÔNG' : 'CÓ'}`);
    log.info(`  HLK layer:     ${SKIP_HLK ? 'KHÔNG' : 'CÓ'}`);
    log.info(`  Devin CLI:     ${SKIP_DEVIN ? 'KHÔNG' : 'CÓ'}`);
    log.info(`  Antigravity:   ${SKIP_AGY ? 'KHÔNG' : 'CÓ'}`);
    log.info(`  Providers:     ${SKIP_PROVIDERS ? 'KHÔNG' : 'CÓ'}`);
    log.info('');
    const ok = await askBool('Xác nhận bắt đầu thiết lập?', true);
    if (!ok) { log.info('Đã hủy.'); process.exit(0); }
  }
}

// --- Hỏi yes/no (legacy, giữ cho các hàm khác dùng) ---
function askConfirm(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(`${question} [y/N]: `, (ans) => {
      rl.close();
      resolve(/^y(es)?$/i.test((ans || '').trim()));
    });
  });
}

// --- Kiểm tra một lệnh có sẵn trong PATH ---
function hasCmd(cmd) {
  const r = spawnSync(cmd, ['--version'], { stdio: 'pipe', shell: process.platform === 'win32' });
  return r.status === 0;
}

// --- Chạy lệnh, kế thừa stdio ---
function run(cmd, args, opts = {}) {
  return spawnSync(cmd, args, {
    cwd: opts.cwd,
    stdio: opts.stdio ?? 'inherit',
    shell: process.platform === 'win32',
    env: { ...process.env, ...(opts.env || {}) },
  });
}

// --- Kiểm tra ruflo đã được cài (global hoặc npx cache) ---
function rufloInstalled() {
  if (hasCmd('ruflo')) return true;
  // Thử npx --no-install ruflo --version (nếu đã cache)
  const r = spawnSync('npx', ['--no-install', 'ruflo', '--version'], {
    stdio: 'pipe', shell: process.platform === 'win32',
  });
  return r.status === 0;
}

// --- Sao chép đệ quy (tương thích Node cũ) ---
function copyRecursive(src, dst) {
  if (typeof fs.cpSync === 'function') {
    fs.cpSync(src, dst, { recursive: true, force: true });
    return;
  }
  if (!fs.existsSync(dst)) fs.mkdirSync(dst, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, e.name), d = path.join(dst, e.name);
    if (e.isDirectory()) copyRecursive(s, d); else fs.copyFileSync(s, d);
  }
}

// ============================================================================
// CẤU HÌNH "MAX POWER" cho .claude/settings.json
// ----------------------------------------------------------------------------
// Đây là phần cốt lõi: mọi thông số đẩy lên mức cao nhất, mọi tính năng bật.
// Dựa trên FULL_INIT_OPTIONS của v3 + AGENTS.md + CLAUDE.md best practices.
// ============================================================================

function buildMaxPowerSettings(pkgVersion) {
  return {
    // --- Model & routing ---
    model: 'claude-sonnet-5',
    skillListingBudgetFraction: 0.08,
    customInstructions: [
      'Follow the project CLAUDE.md and AGENTS.md guidelines.',
      'Use concurrent execution for all operations.',
      'Prioritize v3 implementation with security-first development,',
      '15-agent swarm coordination, phased performance optimization,',
      'and cross-platform helper automation.',
      'MAX POWER: all features enabled, hierarchical-mesh topology,',
      'hybrid memory + HNSW, neural learning, daemon 10 workers,',
      'agent teams, full hooks, statusline, security auto-scan.',
    ].join(' '),

    // --- Biến môi trường bật tối đa ---
    env: {
      CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: '1',
      CLAUDE_FLOW_V3_ENABLED: 'true',
      CLAUDE_FLOW_HOOKS_ENABLED: 'true',
      CLAUDE_FLOW_MODE: 'v3',
      CLAUDE_FLOW_TOPOLOGY: 'hierarchical-mesh',
      CLAUDE_FLOW_MAX_AGENTS: '15',
      CLAUDE_FLOW_MEMORY_BACKEND: 'hybrid',
      CLAUDE_FLOW_HNSW_ENABLED: 'true',
      CLAUDE_FLOW_NEURAL_ENABLED: 'true',
      CLAUDE_FLOW_DAEMON_AUTOSTART: 'true',
      CLAUDE_FLOW_AGENT_TEAMS: 'true',
      CLAUDE_FLOW_LEARNING_ENABLED: 'true',
      CLAUDE_FLOW_SECURITY_AUTOSCAN: 'true',
    },

    // --- Permissions: cho phép ruflo/claude-flow full ---
    permissions: {
      allow: [
        'Bash(npx ruflo:*)',
        'Bash(npx claude-flow:*)',
        'Bash(npx @claude-flow/*:*)',
        'Bash(ruflo:*)',
        'Bash(claude-flow:*)',
        'Bash(node:*)',
        'Bash(npm run:*)',
        'Bash(npm test:*)',
        'Bash(npm install:*)',
        'Bash(git status)',
        'Bash(git diff:*)',
        'Bash(git log:*)',
        'Bash(git add:*)',
        'Bash(git commit:*)',
        'Bash(git push)',
        'Bash(git config:*)',
        'Bash(git branch:*)',
        'Bash(git checkout:*)',
        'Bash(git stash:*)',
        'Bash(git tag:*)',
        'Bash(jq:*)',
        'Bash(which:*)',
        'Bash(pwd)',
        'Bash(ls:*)',
        'Bash(npx:*)',
        'mcp__claude-flow__*',
        'mcp__ruv-swarm__*',
        'mcp__flow-nexus__*',
        'mcp__ruflo__*',
      ],
      deny: [
        'Read(./.env)',
        'Read(./.env.*)',
        'Bash(rm -rf /)',
      ],
    },

    // --- Hooks đầy đủ: PreToolUse, PostToolUse, UserPromptSubmit, ---
    // --- SessionStart, SessionEnd, Stop, PreCompact, SubagentStop ---
    hooks: {
      PreToolUse: [
        {
          hooks: [{
            type: 'command',
            command: 'node "$CLAUDE_PROJECT_DIR/HLK/wrappers/hlk-hook-bridge.mjs"',
            timeout: 5000,
          }],
        },
        {
          matcher: 'Bash',
          hooks: [{
            type: 'command',
            command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" pre-bash',
            timeout: 5000,
          }],
        },
      ],
      PostToolUse: [
        {
          matcher: 'Write|Edit|MultiEdit',
          hooks: [{
            type: 'command',
            command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" post-edit',
            timeout: 10000,
          }],
        },
      ],
      UserPromptSubmit: [
        {
          hooks: [{
            type: 'command',
            command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" route',
            timeout: 10000,
          }],
        },
      ],
      SessionStart: [
        {
          hooks: [
            {
              type: 'command',
              command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" session-restore',
              timeout: 15000,
            },
            {
              type: 'command',
              command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/auto-memory-hook.mjs" import',
              timeout: 8000,
            },
          ],
        },
      ],
      SessionEnd: [
        {
          hooks: [{
            type: 'command',
            command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" session-end',
            timeout: 10000,
          }],
        },
      ],
      Stop: [
        {
          hooks: [{
            type: 'command',
            command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/auto-memory-hook.mjs" sync',
            timeout: 10000,
          }],
        },
      ],
      PreCompact: [
        {
          matcher: 'manual',
          hooks: [
            { type: 'command', command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" compact-manual' },
            { type: 'command', command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" session-end', timeout: 5000 },
          ],
        },
        {
          matcher: 'auto',
          hooks: [
            { type: 'command', command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" compact-auto' },
            { type: 'command', command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" session-end', timeout: 6000 },
          ],
        },
      ],
      SubagentStop: [
        {
          hooks: [{
            type: 'command',
            command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" post-task',
            timeout: 5000,
          }],
        },
      ],
    },

    // --- Attribution ---
    attribution: {
      commit: 'Co-Authored-By: RuFlo <ruv@ruv.net>',
      pr: 'Generated with [RuFlo](https://github.com/ruvnet/ruflo)',
    },

    // --- claudeFlow block: MAX POWER ---
    claudeFlow: {
      version: pkgVersion || '3.34.0',
      enabled: true,
      modelPreferences: {
        default: 'claude-sonnet-5',
        routing: 'claude-haiku-4-5-20251001',
      },

      // Agent Teams: bật đầy đủ
      agentTeams: {
        enabled: true,
        teammateMode: 'auto',
        taskListEnabled: true,
        mailboxEnabled: true,
        coordination: {
          autoAssignOnIdle: true,
          trainPatternsOnComplete: true,
          notifyLeadOnComplete: true,
          sharedMemoryNamespace: 'agent-teams',
        },
        hooks: {
          teammateIdle: { enabled: true, autoAssign: true, checkTaskList: true },
          taskCompleted: { enabled: true, trainPatterns: true, notifyLead: true },
        },
      },

      // Swarm: topology mạnh nhất, 15 agents
      swarm: {
        topology: 'hierarchical-mesh',
        maxAgents: 15,
        strategy: 'specialized',
        consensus: 'raft',
        loadBalancingStrategy: 'capability-match',
        messageTimeout: 30000,
        retryAttempts: 3,
        healthCheckInterval: 5000,
      },

      // Memory: hybrid + HNSW + learning bridge + memory graph + agent scopes
      memory: {
        backend: 'hybrid',
        enableHNSW: true,
        learningBridge: { enabled: true },
        memoryGraph: { enabled: true },
        agentScopes: { enabled: true },
      },

      // Neural: bật
      neural: { enabled: true },

      // Daemon: autoStart + đầy đủ 10 workers + schedules
      daemon: {
        autoStart: true,
        workers: [
          'map', 'audit', 'optimize', 'consolidate', 'testgaps',
          'ultralearn', 'deepdive', 'document', 'refactor', 'benchmark',
        ],
        schedules: {
          audit:       { interval: '1h', priority: 'critical' },
          optimize:    { interval: '30m', priority: 'high' },
          consolidate: { interval: '2h', priority: 'low' },
          document:    { interval: '1h', priority: 'normal' },
          deepdive:    { interval: '4h', priority: 'normal' },
          ultralearn:  { interval: '1h', priority: 'normal' },
          testgaps:    { interval: '2h', priority: 'high' },
          refactor:    { interval: '6h', priority: 'normal' },
          benchmark:   { interval: '12h', priority: 'normal' },
          map:         { interval: '4h', priority: 'low' },
        },
      },

      // Learning: bật + autoTrain + 3 patterns + retention
      learning: {
        enabled: true,
        autoTrain: true,
        patterns: ['coordination', 'optimization', 'prediction'],
        retention: { shortTerm: '24h', longTerm: '30d' },
      },

      // ADR auto-generate
      adr: { autoGenerate: true, directory: '/docs/adr', template: 'madr' },

      // DDD tracking
      ddd: { trackDomains: true, validateBoundedContexts: true, directory: '/docs/ddd' },

      // Security: auto-scan + scan on edit + cve + threat model
      security: {
        autoScan: true,
        scanOnEdit: true,
        cveCheck: true,
        threatModel: true,
      },

      // Hooks config đầy đủ (tất cả true)
      hooksConfig: {
        preToolUse: true,
        postToolUse: true,
        userPromptSubmit: true,
        sessionStart: true,
        stop: true,
        notification: true,
        permissionRequest: true,
        timeout: 5000,
        continueOnError: true,
      },

      // Skills: tất cả
      skills: {
        core: true, agentdb: true, github: true, flowNexus: true, v3: true, all: true,
      },

      // Commands: tất cả
      commands: {
        core: true, analysis: true, automation: true, github: true,
        hooks: true, monitoring: true, optimization: true, sparc: true,
      },

      // Agents: tất cả gồm consensus + hiveMind
      agents: {
        core: true, github: true, sparc: true, swarm: true,
        consensus: true, hiveMind: true,
      },

      // MCP: tất cả server
      mcp: {
        claudeFlow: true, agenticFlow: true, memory: true,
        neural: true, github: true,
      },

      // Runtime
      runtime: {
        topology: 'hierarchical-mesh',
        maxAgents: 15,
        memoryBackend: 'hybrid',
        enableHNSW: true,
        enableNeural: true,
      },

      // Statusline bật
      statusline: {
        enabled: true,
        style: 'detailed',
        position: 'right',
        refreshInterval: 2000,
      },
    },

    // --- Agents & Skills source ---
    agents: { source: '.claude/agents', customAgents: [] },
    skills: { source: '.claude/commands', enabled: true },

    // --- Statusline command ---
    statusLine: {
      type: 'command',
      command: 'sh -c \'exec node "${CLAUDE_PROJECT_DIR:-.}/.claude/helpers/statusline.cjs"\'',
    },

    // --- MCP servers: claude-flow qua HLK wrapper nếu có, fallback npx ---
    mcpServers: {
      'claude-flow': {
        command: 'node',
        args: ['HLK/wrappers/ruflo-hlk-mcp.mjs', 'mcp', 'start'],
      },
    },
    enabledMcpjsonServers: ['claude-flow'],
  };
}

// ============================================================================
// CÁC BƯỚC THIẾT LẬP
// ============================================================================

// Cài Node 22 portable vào .tools/node/ (Windows only)
// Tự động tải + giải nén + tạo activate scripts
function installNodePortable(ws) {
  const toolsDir = path.join(ws, '.tools');
  const nodeDir = path.join(toolsDir, 'node');
  const nodeVer = '22.22.3';
  const zipName = `node-v${nodeVer}-win-x64.zip`;
  const zipPath = path.join(toolsDir, zipName);
  const url = `https://nodejs.org/dist/v${nodeVer}/${zipName}`;

  if (!fs.existsSync(toolsDir)) fs.mkdirSync(toolsDir, { recursive: true });
  if (fs.existsSync(nodeDir)) fs.rmSync(nodeDir, { recursive: true, force: true });
  fs.mkdirSync(nodeDir, { recursive: true });

  // Tải zip bằng curl (có sẵn Windows 10+)
  log.info(`  Tải ${url}...`);
  const dl = spawnSync('curl', ['-L', '-o', zipPath, url], { stdio: 'pipe' });
  if (dl.status !== 0) throw new Error(`curl thất bại: ${dl.stderr?.toString() || ''}`);
  if (!fs.existsSync(zipPath)) throw new Error('Tải zip thất bại');

  // Giải nén bằng PowerShell
  const ex = spawnSync('powershell', ['-NoProfile', '-Command',
    `Expand-Archive -Path '${zipPath}' -DestinationPath '${toolsDir}' -Force`], { stdio: 'pipe' });
  if (ex.status !== 0) throw new Error(`Expand-Archive thất bại: ${ex.stderr?.toString() || ''}`);
  const extracted = path.join(toolsDir, `node-v${nodeVer}-win-x64`);
  if (!fs.existsSync(extracted)) throw new Error('Giải nén thất bại');

  // Di chuyển nội dung vào .tools/node/
  for (const item of fs.readdirSync(extracted)) {
    fs.renameSync(path.join(extracted, item), path.join(nodeDir, item));
  }
  fs.rmSync(extracted, { recursive: true, force: true });
  fs.unlinkSync(zipPath);

  // Tạo activate.ps1
  const activatePs1 = path.join(ws, 'activate.ps1');
  fs.writeFileSync(activatePs1, [
    '# activate.ps1 - Kich hoat Node portable cho workspace nay',
    '$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path',
    '$nodeDir = Join-Path $wsRoot ".tools\\node"',
    'if (-not (Test-Path (Join-Path $nodeDir "node.exe"))) { Write-Host "LOI: Khong tim thay Node portable" -ForegroundColor Red; return }',
    '$global:_OldPath = $env:PATH',
    '$env:PATH = "$nodeDir;$env:PATH"',
    '$env:NODE_PATH = Join-Path $wsRoot "node_modules"',
    'function global:deactivate { if ($global:_OldPath) { $env:PATH = $global:_OldPath; Remove-Variable -Name _OldPath -Scope Global -EA SilentlyContinue } }',
    '$v = & (Join-Path $nodeDir "node.exe") --version',
    'Write-Host "Node portable: $v" -ForegroundColor Green',
  ].join('\n') + '\n');

  // Tạo activate.cmd
  const activateCmd = path.join(ws, 'activate.cmd');
  fs.writeFileSync(activateCmd, [
    '@echo off',
    'set "WS_ROOT=%~dp0"',
    'if "%WS_ROOT:~-1%"=="\\" set "WS_ROOT=%WS_ROOT:~0,-1%"',
    'set "NODE_DIR=%WS_ROOT%\\.tools\\node"',
    'if not exist "%NODE_DIR%\\node.exe" (echo LOI: Khong tim thay Node portable & exit /b 1)',
    'set "PATH=%NODE_DIR%;%PATH%"',
    'set "NODE_PATH=%WS_ROOT%\\node_modules"',
    'echo Node portable da kich hoat',
    'endlocal & set "PATH=%NODE_DIR%;%PATH%" & set "NODE_PATH=%WS_ROOT%\\node_modules"',
  ].join('\r\n') + '\r\n');

  // Thêm .tools/node/ vào .gitignore
  const giPath = path.join(ws, '.gitignore');
  if (fs.existsSync(giPath)) {
    const gi = fs.readFileSync(giPath, 'utf8');
    if (!gi.includes('.tools/node/')) {
      fs.appendFileSync(giPath, '\n# Node portable\n.tools/node/\n.tools/*.zip\n');
    }
  }

  log.ok(`  Node v${nodeVer} portable cài tại .tools/node/`);
  log.ok('  Đã tạo activate.ps1 + activate.cmd');
}

// Bước 0: Kiểm tra prerequisites
function checkPrerequisites(ws) {
  log.head('Bước 0: Kiểm tra prerequisites');

  // Node >= 20 — nếu thiếu, thử cài Node portable vào .tools/node/
  const nodeMajor = parseInt(process.versions.node.split('.')[0], 10);
  if (nodeMajor < 20) {
    log.warn(`Node >= 20 yêu cầu. Hiện tại: ${process.version}`);
    const portableNode = path.join(ws, '.tools', 'node', 'node.exe');
    if (fs.existsSync(portableNode)) {
      log.ok(`Đã có Node portable tại .tools/node/ — chạy: . .\\activate.ps1 (PS) hoặc activate (CMD)`);
      log.info('  Sau khi activate, chạy lại script này bằng Node 22.');
    } else {
      log.info('Thử cài Node 22 portable vào .tools/node/...');
      try {
        installNodePortable(ws);
        log.ok('Đã cài Node 22 portable. Bật activate rồi chạy lại script.');
        log.info('  PowerShell: . .\\activate.ps1');
        log.info('  CMD:        activate');
        process.exit(0);
      } catch (e) {
        log.err(`Không cài được Node portable: ${e.message}`);
        log.info('Cài thủ công: tải node-v22-win-x64.zip từ https://nodejs.org/dist/v22.22.3/');
        process.exit(1);
      }
    }
    process.exit(1);
  }
  log.ok(`Node ${process.version}`);

  // npm
  if (!hasCmd('npm')) { log.err('Không tìm thấy npm.'); process.exit(1); }
  log.ok('npm sẵn sàng');

  // git (tùy chọn nhưng khuyến nghị)
  if (hasCmd('git')) log.ok('git sẵn sàng');
  else log.warn('git không tìm thấy — một số tính năng (hooks, upstream pull) sẽ bị hạn chế.');

  // --- Kiểm tra ruflo ---
  if (SKIP_RUFLO) {
    log.warn('--skip-ruflo: bỏ qua kiểm tra cài đặt Ruflo');
    return;
  }

  if (LOCAL) {
    // --local: sẽ cài ruflo cục bộ trong workspace, không cần global
    log.ok('--local: sẽ cài ruflo CỤC BỘ trong workspace (không cần global)');
    log.info('  Ruflo sẽ được thêm vào devDependencies của workspace.');
  } else {
    // Global mode: yêu cầu ruflo đã cài global hoặc npx cache
    if (!rufloInstalled()) {
      log.warn('Ruflo chưa cài global. Hai lựa chọn:');
      log.info('  1. Cài global: npm install -g ruflo@latest');
      log.info('  2. Dùng --local: node HLK/bin/hlk-setup-max-power.mjs --local --path <ws>');
      log.info('     (script sẽ cài ruflo cục bộ trong workspace để test)');
      // Không exit — cho phép tiếp tục nếu user muốn (sẽ fallback npx -y)
      log.warn('Tiếp tục với npx -y (chậm hơn nhưng vẫn hoạt động).');
    } else {
      log.ok('Ruflo đã cài (global hoặc npx cache)');
    }
  }
}

// Bước 1: Xác định workspace
async function resolveWorkspace() {
  log.head('Bước 1: Xác định workspace');
  let ws;
  if (USER_PATH) {
    ws = path.resolve(USER_PATH);
    log.info(`Path (từ --path): ${ws}`);
  } else {
    ws = path.resolve(await askWorkspacePath());
    log.info(`Path (nhập): ${ws}`);
  }

  // Tạo thư mục nếu chưa có
  if (!fs.existsSync(ws)) {
    fs.mkdirSync(ws, { recursive: true });
    log.ok(`Đã tạo thư mục: ${ws}`);
  }
  return ws;
}

// Bước 2: Cài / init Ruflo trong workspace
function installRuflo(ws) {
  log.head('Bước 2: Cài / init Ruflo trong workspace');
  if (SKIP_RUFLO) { log.warn('--skip-ruflo: bỏ qua.'); return; }

  const pkg = RUFLO_VERSION === 'latest' ? 'ruflo@latest' : `ruflo@${RUFLO_VERSION}`;

  // --- --local mode: cài ruflo cục bộ vào workspace ---
  if (LOCAL) {
    log.info(`--local: cài ${pkg} cục bộ vào workspace (npm install --save-dev)`);
    // Đảm bảo workspace có package.json
    const pkgPath = path.join(ws, 'package.json');
    if (!fs.existsSync(pkgPath)) {
      fs.writeFileSync(pkgPath, JSON.stringify({
        name: path.basename(ws).toLowerCase().replace(/[^a-z0-9-]/g, '-'),
        version: '0.0.1',
        private: true,
        type: 'module',
      }, null, 2) + '\n', 'utf8');
      log.ok('Đã tạo package.json tối thiểu cho workspace');
    }

    // Cài ruflo cục bộ
    const inst = run('npm', ['install', '--save-dev', pkg], { cwd: ws });
    if (inst.status !== 0) {
      log.warn('npm install ruflo cục bộ gặp lỗi — fallback npx -y.');
    } else {
      log.ok(`Đã cài ${pkg} cục bộ vào workspace.`);
      log.info('  Dùng: npx ruflo <command>  hoặc  node node_modules/ruflo/bin/ruflo.js <command>');
    }

    // Init ruflo trong workspace
    const hasInit = fs.existsSync(path.join(ws, '.claude', 'settings.json'));
    if (!hasInit) {
      log.info('Chạy ruflo init --yes (cục bộ)...');
      const r = run('npx', ['ruflo', 'init', '--yes'], { cwd: ws });
      if (r.status !== 0) log.warn('ruflo init thất bại — sẽ tạo settings thủ công.');
      else log.ok('ruflo init xong.');
    } else {
      log.info('Workspace đã có .claude/settings.json — chạy upgrade --add-missing.');
      const r = run('npx', ['ruflo', 'init', 'upgrade', '--add-missing'], { cwd: ws });
      if (r.status !== 0) log.warn('ruflo upgrade gặp lỗi — tiếp tục patch thủ công.');
      else log.ok('ruflo upgrade xong.');
    }
    return;
  }

  // --- Global/npx mode ---
  const hasInit = fs.existsSync(path.join(ws, '.claude', 'settings.json')) ||
                  fs.existsSync(path.join(ws, 'package.json'));

  if (hasInit) {
    log.info('Workspace đã có cấu hình Ruflo — chạy upgrade --add-missing.');
    const r = run('npx', ['-y', pkg, 'init', 'upgrade', '--add-missing'], { cwd: ws });
    if (r.status !== 0) log.warn('Ruflo upgrade gặp lỗi — tiếp tục patch thủ công.');
    else log.ok('Ruflo upgrade xong.');
  } else {
    log.info(`Chạy: npx ${pkg} init --yes`);
    const r = run('npx', ['-y', pkg, 'init', '--yes'], { cwd: ws });
    if (r.status !== 0) {
      log.warn('Ruflo init thất bại — sẽ tạo settings.json thủ công ở bước sau.');
    } else {
      log.ok('Ruflo init xong.');
    }
  }
}

// Bước 3: Patch .claude/settings.json lên MAX POWER
function patchSettingsMaxPower(ws) {
  log.head('Bước 3: Patch .claude/settings.json lên MAX POWER');

  const claudeDir = path.join(ws, '.claude');
  fs.mkdirSync(claudeDir, { recursive: true });
  const settingsPath = path.join(claudeDir, 'settings.json');

  // Đọc settings hiện tại (nếu có) để merge không mất dữ liệu người dùng
  let existing = {};
  if (fs.existsSync(settingsPath)) {
    try { existing = JSON.parse(fs.readFileSync(settingsPath, 'utf8')); }
    catch { log.warn('settings.json hiện tại lỗi parse — ghi đè.'); }
  }

  // Lấy version từ package.json của workspace nếu có
  let pkgVersion = null;
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(ws, 'package.json'), 'utf8'));
    pkgVersion = pkg.version || null;
  } catch { /* ignore */ }

  const max = buildMaxPowerSettings(pkgVersion);

  // Merge: existing.customInstructions / permissions.allow được preserve
  if (existing.customInstructions && typeof existing.customInstructions === 'string') {
    // Giữ nguyên customInstructions cũ nếu người dùng đã viết
    max.customInstructions = existing.customInstructions;
  }
  if (Array.isArray(existing.permissions?.allow)) {
    const set = new Set([...(max.permissions.allow || []), ...existing.permissions.allow]);
    max.permissions.allow = [...set];
  }
  // Giữ mcpServers hiện có nếu đã có cấu hình khác
  if (existing.mcpServers) {
    max.mcpServers = { ...existing.mcpServers, ...max.mcpServers };
  }

  fs.writeFileSync(settingsPath, JSON.stringify(max, null, 2) + '\n', 'utf8');
  log.ok(`Đã ghi ${settingsPath}`);
  log.info('MAX POWER settings: topology=hierarchical-mesh, maxAgents=15, hybrid+HNSW,');
  log.info('  neural=on, daemon=10 workers, agentTeams=on, learning=on, security=on,');
  log.info('  skills=all, commands=all, agents=all+consensus+hiveMind, mcp=all,');
  log.info('  hooks=full (8 loại), statusline=detailed.');
}

// Bước 4: Tạo .claude-flow/runtime.json (runtime config max)
function writeRuntimeConfig(ws) {
  log.head('Bước 4: Tạo .claude-flow/runtime.json (runtime MAX)');
  const cfDir = path.join(ws, '.claude-flow');
  fs.mkdirSync(cfDir, { recursive: true });
  const runtime = {
    version: '3.34.0',
    mode: 'v3',
    topology: 'hierarchical-mesh',
    maxAgents: 15,
    memoryBackend: 'hybrid',
    enableHNSW: true,
    enableNeural: true,
    daemon: { autoStart: true },
    agentTeams: { enabled: true },
    learning: { enabled: true, autoTrain: true },
    security: { autoScan: true, scanOnEdit: true, cveCheck: true, threatModel: true },
    createdAt: new Date().toISOString(),
  };
  fs.writeFileSync(path.join(cfDir, 'runtime.json'), JSON.stringify(runtime, null, 2) + '\n', 'utf8');
  log.ok('Đã ghi .claude-flow/runtime.json');
}

// Bước 5: Patch .gitattributes + .gitignore (bảo vệ HLK/secrets)
function patchGitFiles(ws) {
  log.head('Bước 5: Patch .gitattributes + .gitignore');

  const gitattrLines = [
    '# HLK config — keep ours on merge',
    'HLK/config/hlk.config.json merge=ours',
    'HLK/wrappers/** merge=ours',
    'HLK/security/** merge=ours',
    'HLK/docs/** merge=ours',
    '.claude/settings.json merge=ours',
  ];
  const ga = path.join(ws, '.gitattributes');
  let gaContent = fs.existsSync(ga) ? fs.readFileSync(ga, 'utf8') : '';
  let gaMod = false;
  for (const line of gitattrLines) {
    if (!gaContent.includes(line)) {
      gaContent += (gaContent.endsWith('\n') ? '' : '\n') + line + '\n';
      gaMod = true;
    }
  }
  if (gaMod) { fs.writeFileSync(ga, gaContent, 'utf8'); log.ok('Đã cập nhật .gitattributes'); }
  else log.info('.gitattributes đã đủ HLK merge rules');

  const ignorePatterns = [
    'HLK/config/secrets.*', 'HLK/config/*.local.json', 'HLK/logs/',
    '*.rvf', '*.rvf.lock', 'agentdb.rvf', 'agentdb.rvf.lock',
    '.env', '.env.*', '!.env.example', '!.env.*.example', 'example.env',
    'HLK/dist/*.tgz', 'HLK/dist/',
    '.claude-flow/data/', '.swarm/', '.hive-mind/',
  ];
  const gi = path.join(ws, '.gitignore');
  let giContent = fs.existsSync(gi) ? fs.readFileSync(gi, 'utf8') : '';
  let giMod = false;
  for (const p of ignorePatterns) {
    if (!giContent.split('\n').some((l) => l.trim() === p)) {
      giContent += (giContent.endsWith('\n') ? '' : '\n') + p + '\n';
      giMod = true;
    }
  }
  if (giMod) { fs.writeFileSync(gi, giContent, 'utf8'); log.ok('Đã cập nhật .gitignore'); }
  else log.info('.gitignore đã bảo vệ đầy đủ');
}

// Bước 6: Cài HLK layer (nếu có HLK/setup/install.mjs trong repo này)
function installHlkLayer(ws) {
  log.head('Bước 6: Cài HLK layer (Harness & Logic Knowledge)');
  if (SKIP_HLK) { log.warn('--skip-hlk: bỏ qua.'); return; }

  // Guard check: nếu HLK đã cài trong workspace rồi thì bỏ qua
  const wsHlkConfig = path.join(ws, 'HLK', 'config', 'hlk.config.json');
  if (fs.existsSync(wsHlkConfig)) {
    log.ok('HLK đã cài trong workspace (có HLK/config/hlk.config.json) — bỏ qua bước cài.');
    return;
  }

  // Tìm HLK/setup/install.mjs từ repo hiện tại (đi lên từ __dirname = HLK/bin)
  // __dirname = <repo>/HLK/bin → đi lên 2 cấp = <repo>
  const repoRoot = path.resolve(__dirname, '..', '..');
  const hlkSetup = path.join(repoRoot, 'HLK', 'setup', 'install.mjs');
  if (!fs.existsSync(hlkSetup)) {
    log.warn(`Không tìm thấy ${hlkSetup} — bỏ qua HLK.`);
    log.info('Nếu muốn cài HLK, clone Loop_harness_ruflo rồi chạy script từ đó.');
    return;
  }

  log.info(`Chạy HLK installer cho workspace: ${ws}`);
  // HLK/setup/install.mjs hỗ trợ --path <dir> --yes
  const r = run(process.execPath, [hlkSetup, '--path', ws, '--yes'], { cwd: ws });
  if (r.status !== 0) {
    log.warn('HLK install gặp lỗi — tiếp tục (HLK là tùy chọn).');
  } else {
    log.ok('HLK layer đã cài xong cho workspace.');
  }
}

// Bước 7: Kích hoạt git hooks (nếu workspace có .git)
function enableGitHooks(ws) {
  log.head('Bước 7: Kích hoạt git hooks');
  if (!fs.existsSync(path.join(ws, '.git'))) {
    log.info('Workspace chưa có .git/ — bỏ qua git config hooks.');
    return;
  }
  const r = run('git', ['config', 'core.hooksPath', '.githooks'], { cwd: ws });
  if (r.status === 0) log.ok('Đã kích hoạt git config core.hooksPath .githooks');
  else log.warn('Không kích hoạt được core.hooksPath.');
}

// Bước 8: Verify — chạy ruflo doctor + status
function verifySetup(ws) {
  log.head('Bước 8: Verify — ruflo doctor + status');
  const pkg = RUFLO_VERSION === 'latest' ? 'ruflo@latest' : `ruflo@${RUFLO_VERSION}`;
  const rufloCmd = LOCAL ? 'ruflo' : pkg;  // --local: dùng npx ruflo (đã cài cục bộ)

  log.info('Chạy: ruflo doctor');
  const d = run('npx', [rufloCmd, 'doctor'], { cwd: ws });
  if (d.status !== 0) log.warn('ruflo doctor gặp cảnh báo — kiểm tra thủ công.');

  log.info('Chạy: ruflo status');
  const s = run('npx', [rufloCmd, 'status'], { cwd: ws });
  if (s.status !== 0) log.warn('ruflo status gặp lỗi — kiểm tra thủ công.');

  // HLK integrity verify nếu có
  const verify = path.join(ws, 'HLK', 'wrappers', 'hlk-verify-integrity.js');
  if (fs.existsSync(verify)) {
    log.info('Chạy: HLK integrity verify');
    const v = run(process.execPath, [verify], { cwd: ws });
    if (v.status !== 0) log.warn('HLK integrity verify FAILED — review HLK layer.');
    else log.ok('HLK integrity verify PASSED');
  }
}

// ============================================================================
// Bước 9: Cấu hình Devin CLI (.devin/)
// ----------------------------------------------------------------------------
// Devin CLI dùng:
//   .devin/config.json         — permissions, read_config_from
//   .devin/mcp_config.json     — MCP servers (shared với team)
//   .devin/hooks.v1.json       — lifecycle hooks (Claude Code compatible)
//   .devin/skills/             — skills (SKILL.md)
//   .devin/agents/             — custom subagent profiles
//   AGENTS.md                   — project rules
// ============================================================================
function setupDevinCli(ws) {
  log.head('Bước 9: Cấu hình Devin CLI (.devin/)');
  if (SKIP_DEVIN) { log.warn('--skip-devin: bỏ qua.'); return; }

  const devinDir = path.join(ws, '.devin');
  fs.mkdirSync(devinDir, { recursive: true });
  fs.mkdirSync(path.join(devinDir, 'skills'), { recursive: true });
  fs.mkdirSync(path.join(devinDir, 'agents'), { recursive: true });

  // --- .devin/config.json ---
  const configPath = path.join(devinDir, 'config.json');
  const devinConfig = {
    permissions: {
      allow: [
        'Exec(npx ruflo:*)',
        'Exec(npx claude-flow:*)',
        'Exec(npx @claude-flow/*:*)',
        'Exec(node:*)',
        'Exec(npm run:*)',
        'Exec(npm test:*)',
        'Exec(git status)',
        'Exec(git diff:*)',
        'Exec(git log:*)',
        'Exec(git add:*)',
        'Exec(git commit:*)',
        'Exec(git push)',
        'Exec(git config:*)',
        'Read(src/**)',
        'Read(tests/**)',
        'Read(docs/**)',
        'Read(.claude/**)',
        'Read(.devin/**)',
        'Read(HLK/**)',
      ],
      deny: ['Exec(sudo)', 'Exec(rm -rf /)', 'Read(.env)', 'Read(.env.*)'],
    },
    read_config_from: { claude: true, cursor: true, windsurf: true },
  };
  fs.writeFileSync(configPath, JSON.stringify(devinConfig, null, 2) + '\n', 'utf8');
  log.ok('Đã ghi .devin/config.json');

  // --- .devin/mcp_config.json ---
  const mcpConfigPath = path.join(devinDir, 'mcp_config.json');
  const devinMcp = {
    mcpServers: {
      'claude-flow': {
        command: 'node',
        args: ['HLK/wrappers/ruflo-hlk-mcp.mjs', 'mcp', 'start'],
      },
    },
  };
  fs.writeFileSync(mcpConfigPath, JSON.stringify(devinMcp, null, 2) + '\n', 'utf8');
  log.ok('Đã ghi .devin/mcp_config.json');

  // --- .devin/hooks.v1.json (Claude Code compatible) ---
  const hooksPath = path.join(devinDir, 'hooks.v1.json');
  const devinHooks = {
    PreToolUse: [
      {
        matcher: 'exec',
        hooks: [{
          type: 'command',
          command: 'node "$CLAUDE_PROJECT_DIR/HLK/wrappers/hlk-hook-bridge.mjs"',
          timeout: 5,
        }],
      },
    ],
    PostToolUse: [
      {
        matcher: 'edit|write',
        hooks: [{
          type: 'command',
          command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" post-edit',
          timeout: 10,
        }],
      },
    ],
    SessionStart: [
      {
        hooks: [{
          type: 'command',
          command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" session-restore',
          timeout: 15,
        }],
      },
    ],
    SessionEnd: [
      {
        hooks: [{
          type: 'command',
          command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs" session-end',
          timeout: 10,
        }],
      },
    ],
    Stop: [
      {
        hooks: [{
          type: 'command',
          command: 'node "$CLAUDE_PROJECT_DIR/.claude/helpers/auto-memory-hook.mjs" sync',
          timeout: 10,
        }],
      },
    ],
  };
  fs.writeFileSync(hooksPath, JSON.stringify(devinHooks, null, 2) + '\n', 'utf8');
  log.ok('Đã ghi .devin/hooks.v1.json (6 lifecycle events)');

  // --- Copy HLK skills sang .devin/skills/ nếu có ---
  const hlkSkillsSrc = path.join(ws, 'HLK', 'skills');
  if (fs.existsSync(hlkSkillsSrc)) {
    for (const entry of fs.readdirSync(hlkSkillsSrc, { withFileTypes: true })) {
      if (!entry.isDirectory() || !entry.name.startsWith('hlk-')) continue;
      const src = path.join(hlkSkillsSrc, entry.name);
      const dst = path.join(devinDir, 'skills', entry.name);
      copyRecursive(src, dst);
    }
    log.ok('Đã copy HLK skills sang .devin/skills/');
  }

  log.ok('Devin CLI cấu hình xong: config.json + mcp_config.json + hooks.v1.json + skills/');
}

// ============================================================================
// Bước 10: Cấu hình Antigravity CLI (agy)
// ----------------------------------------------------------------------------
// agy dùng:
//   ~/.gemini/antigravity-cli/settings.json  — settings chính (HOME level)
//   ~/.gemini/config/mcp_config.json         — MCP servers global (HOME level)
//   .agents/mcp_config.json                  — MCP servers workspace (agy đọc được)
//
// Lưu ý: project-local .antigravitycli/mcp_config.json bị agy IGNORE (bug đã biết),
//        chỉ HOME-level và .agents/mcp_config.json mới load MCP. Script ghi cả 2.
// ============================================================================
function setupAntigravityCli(ws) {
  log.head('Bước 10: Cấu hình Antigravity CLI (agy)');
  if (SKIP_AGY) { log.warn('--skip-agy: bỏ qua.'); return; }

  // --- .agents/mcp_config.json (workspace-level, agy đọc được) ---
  const agentsDir = path.join(ws, '.agents');
  // Xử lý trường hợp .agents là file (không phải dir) — đổi tên thành .agents.bak
  if (fs.existsSync(agentsDir) && !fs.statSync(agentsDir).isDirectory()) {
    const bak = agentsDir + '.bak.' + Date.now();
    log.warn(`.agents đang là file (không phải thư mục) — đổi tên thành ${path.basename(bak)}`);
    fs.renameSync(agentsDir, bak);
  }
  fs.mkdirSync(agentsDir, { recursive: true });
  const agyMcpPath = path.join(agentsDir, 'mcp_config.json');
  const agyMcp = {
    mcpServers: {
      'claude-flow': {
        command: 'node',
        args: ['HLK/wrappers/ruflo-hlk-mcp.mjs', 'mcp', 'start'],
      },
    },
  };
  fs.writeFileSync(agyMcpPath, JSON.stringify(agyMcp, null, 2) + '\n', 'utf8');
  log.ok('Đã ghi .agents/mcp_config.json (agy workspace MCP)');

  // --- .agents/config.toml (Codex CLI + agy chia sẻ) ---
  // Chỉ tạo nếu chưa có — không ghi đè config.toml hiện có của repo
  const agyTomlPath = path.join(agentsDir, 'config.toml');
  if (!fs.existsSync(agyTomlPath)) {
    const toml = [
      '# Antigravity CLI (agy) + Codex CLI config — MAX POWER',
      '# Tự sinh bởi hlk-setup-max-power.mjs',
      '',
      'model = "gemini-2.5-pro"',
      'approval_policy = "on-request"',
      'sandbox_mode = "workspace-write"',
      'web_search = "live"',
      '',
      '[features]',
      'child_agents_md = true',
      'shell_snapshot = true',
      'request_rule = true',
      'remote_compaction = true',
      '',
      '[mcp_servers.claude-flow]',
      'command = "node"',
      'args = ["HLK/wrappers/ruflo-hlk-mcp.mjs", "mcp", "start"]',
      'enabled = true',
      'tool_timeout_sec = 120',
      '',
      '[security]',
      'input_validation = true',
      'path_traversal_prevention = true',
      'secret_scanning = true',
      'cve_scanning = true',
      'max_file_size = 10485760',
      'blocked_patterns = ["\\\\.env$", "credentials\\\\.json$", "\\\\.pem$", "\\\\.key$"]',
      '',
      '[performance]',
      'max_agents = 15',
      'task_timeout = 300',
      'parallel_execution = true',
      'cache_enabled = true',
      '',
      '[neural]',
      'sona_enabled = true',
      'hnsw_enabled = true',
      'hnsw_m = 16',
      'hnsw_ef_construction = 200',
      'hnsw_ef_search = 100',
      'pattern_learning = true',
      '',
      '[swarm]',
      'default_topology = "hierarchical-mesh"',
      'default_strategy = "specialized"',
      'consensus = "raft"',
      'anti_drift = true',
      '',
      '[hooks]',
      'enabled = true',
      'pre_task = true',
      'post_task = true',
      'train_on_edit = true',
      '',
      '[workers]',
      'enabled = true',
      '',
      '[workers.audit]',
      'enabled = true',
      'priority = "critical"',
      'interval = 300',
      '',
      '[workers.optimize]',
      'enabled = true',
      'priority = "high"',
      'interval = 600',
      '',
      '[workers.consolidate]',
      'enabled = true',
      'priority = "low"',
      'interval = 1800',
      '',
    ].join('\n') + '\n';
    fs.writeFileSync(agyTomlPath, toml, 'utf8');
    log.ok('Đã ghi .agents/config.toml (agy + Codex MAX POWER)');
  } else {
    log.info('.agents/config.toml đã có — giữ nguyên (không ghi đè).');
  }

  // --- Tạo AGENTS.md nếu chưa có (agy + Devin CLI đều đọc) ---
  const agentsMd = path.join(ws, 'AGENTS.md');
  if (!fs.existsSync(agentsMd)) {
    fs.writeFileSync(agentsMd, [
      '# Project Agent Guide',
      '',
      '> Tự sinh bởi hlk-setup-max-power.mjs — điều chỉnh cho phù hợp dự án.',
      '',
      '## Workflow',
      '- Dùng ruflo cho orchestration: `npx ruflo swarm init --topology hierarchical-mesh --max-agents 15`',
      '- Memory: `npx ruflo memory store --key <k> --value <v> --namespace patterns`',
      '- Hooks: HLK PreToolUse hook tự kiểm tra secrets trước mỗi tool call.',
      '',
      '## Rules',
      '- KHÔNG commit secrets, .env, *.rvf, *.key, *.pem.',
      '- Luôn đọc file trước khi edit.',
      '- Test trước khi commit.',
      '',
      '## Providers',
      '- Claude (Anthropic): reasoning, architecture, security review.',
      '- Codex (OpenAI): implementation, optimization, bulk transforms.',
      '- Gemini (Google): multimodal, research, long-context.',
      '',
    ].join('\n') + '\n', 'utf8');
    log.ok('Đã tạo AGENTS.md (agy + Devin CLI đọc)');
  }

  // --- Gợi ý HOME-level config (không tự ghi vào HOME của user) ---
  log.info('agy HOME-level config (tùy chọn, chạy thủ công):');
  log.info('  agy mcp add claude-flow -- node HLK/wrappers/ruflo-hlk-mcp.mjs mcp start');
  log.info('  # Hoặc edit ~/.gemini/config/mcp_config.json');
  log.ok('Antigravity CLI (agy) cấu hình workspace xong.');
}

// ============================================================================
// Bước 11: Tinh chỉnh Provider (Claude, Codex, Gemini, OpenAI)
// ----------------------------------------------------------------------------
// Tạo .claude-flow/providers.json với routing rules cho từng provider.
// Ưu điểm: mỗi provider có cấu hình tối ưu riêng, ruflo swarm tự route.
// ============================================================================
function setupProviders(ws) {
  log.head('Bước 11: Tinh chỉnh Provider (Claude / Codex / Gemini / OpenAI)');
  if (SKIP_PROVIDERS) { log.warn('--skip-providers: bỏ qua.'); return; }

  const cfDir = path.join(ws, '.claude-flow');
  fs.mkdirSync(cfDir, { recursive: true });

  const providers = {
    _comment: 'Provider routing config — Tự sinh bởi hlk-setup-max-power.mjs',
    _updatedAt: new Date().toISOString(),
    default: PROVIDER,

    // --- Claude (Anthropic) — reasoning, architecture, security ---
    claude: {
      models: {
        default: 'claude-sonnet-5',
        heavy: 'claude-opus-4-1',
        fast: 'claude-haiku-4-5-20251001',
      },
      strengths: ['reasoning', 'architecture', 'security-review', 'planning', 'testing-strategy'],
      roles: ['architect', 'reviewer', 'security-architect', 'tester', 'researcher'],
      env: {
        ANTHROPIC_API_KEY: '${ANTHROPIC_API_KEY}',
      },
      mcpCommand: 'npx -y ruflo@latest mcp start',
      tuning: {
        maxTokens: 8192,
        temperature: 0.7,
        thinkingBudget: 'high',
        toolUseOptimized: true,
      },
    },

    // --- Codex (OpenAI) — implementation, optimization, bulk transforms ---
    codex: {
      models: {
        default: 'gpt-5.3-codex',
        heavy: 'gpt-5.3-codex',
        fast: 'gpt-4.1-mini',
      },
      strengths: ['implementation', 'optimization', 'bulk-transforms', 'refactoring', 'code-generation'],
      roles: ['coder', 'optimizer', 'refactorer', 'implementer-sparc-coder'],
      env: {
        OPENAI_API_KEY: '${OPENAI_API_KEY}',
      },
      mcpCommand: 'npx -y @claude-flow/codex@latest mcp start',
      tuning: {
        maxTokens: 16384,
        temperature: 0.3,
        fastMode: true,
        codemodPreferred: true,
      },
      configToml: {
        model: 'gpt-5.3-codex',
        approval_policy: 'on-request',
        sandbox_mode: 'workspace-write',
        web_search: 'cached',
      },
    },

    // --- Gemini (Google) — multimodal, research, long-context ---
    gemini: {
      models: {
        default: 'gemini-2.5-pro',
        heavy: 'gemini-2.5-pro',
        fast: 'gemini-2.5-flash',
      },
      strengths: ['multimodal', 'research', 'long-context', 'vision', 'documentation'],
      roles: ['researcher', 'docs-api-openapi', 'scout-explorer', 'data-ml-model'],
      env: {
        GOOGLE_API_KEY: '${GOOGLE_API_KEY}',
        GEMINI_API_KEY: '${GEMINI_API_KEY}',
      },
      mcpCommand: 'agy mcp start',
      tuning: {
        maxTokens: 1048576,
        temperature: 0.5,
        longContext: true,
        visionCapable: true,
      },
      agySettings: {
        model: 'Gemini 3.5 Flash (High)',
        enableTerminalSandbox: true,
        toolPermission: 'request-review',
      },
    },

    // --- OpenAI (direct, cho GPT-4.1 / o3) ---
    openai: {
      models: {
        default: 'gpt-4.1',
        heavy: 'o3',
        fast: 'gpt-4.1-mini',
      },
      strengths: ['reasoning', 'general-tasks', 'tool-use', 'multimodal'],
      roles: ['planner', 'architect', 'reviewer'],
      env: {
        OPENAI_API_KEY: '${OPENAI_API_KEY}',
      },
      mcpCommand: 'npx -y ruflo@latest mcp start',
      tuning: {
        maxTokens: 32768,
        temperature: 0.4,
        reasoningEffort: 'high',
      },
    },

    // --- OpenRouter (fallback multi-provider) ---
    openrouter: {
      models: {
        default: 'anthropic/claude-sonnet-5',
        heavy: 'anthropic/claude-opus-4-1',
        fast: 'google/gemini-2.5-flash',
      },
      strengths: ['fallback', 'multi-provider', 'cost-optimization'],
      roles: ['coordinator', 'load-balancer'],
      env: {
        OPENROUTER_API_KEY: '${OPENROUTER_API_KEY}',
      },
      mcpCommand: 'npx -y ruflo@latest mcp start',
      tuning: {
        maxTokens: 8192,
        temperature: 0.6,
        fallbackChain: ['anthropic/claude-sonnet-5', 'openai/gpt-4.1', 'google/gemini-2.5-pro'],
      },
    },

    // --- Routing rules: task type → provider ---
    routing: {
      'architecture': 'claude',
      'security': 'claude',
      'planning': 'claude',
      'testing-strategy': 'claude',
      'implementation': 'codex',
      'optimization': 'codex',
      'refactoring': 'codex',
      'bulk-transform': 'codex',
      'research': 'gemini',
      'documentation': 'gemini',
      'multimodal': 'gemini',
      'vision': 'gemini',
      'long-context': 'gemini',
      'fallback': 'openrouter',
    },

    // --- 3-tier model routing (ADR-026, ADR-143) ---
    tiers: {
      1: { handler: 'codemod', latency: '~1ms', cost: 0, intents: ['var-to-const', 'remove-console', 'add-logging'] },
      2: { handler: 'haiku', latency: '~500ms', cost: 0.0002, complexity: '<30%' },
      3: { handler: 'sonnet/opus', latency: '2-5s', cost: '0.003-0.015', complexity: '>30%' },
    },
  };

  const provPath = path.join(cfDir, 'providers.json');
  fs.writeFileSync(provPath, JSON.stringify(providers, null, 2) + '\n', 'utf8');
  log.ok(`Đã ghi .claude-flow/providers.json (default: ${PROVIDER})`);
  log.info('Providers: claude (reasoning) | codex (impl) | gemini (research) | openai | openrouter (fallback)');
  log.info('Routing: architecture→claude, implementation→codex, research→gemini, fallback→openrouter');
  log.info('3-tier: codemod($0) → haiku($0.0002) → sonnet/opus($0.003-0.015)');

  // --- Cập nhật .agents/config.toml model theo provider mặc định ---
  if (!fs.existsSync(path.join(ws, '.agents', 'config.toml'))) {
    // Đã tạo ở bước 10 nếu agy không skip
  } else {
    // Patch model trong config.toml hiện có theo provider
    const tomlPath = path.join(ws, '.agents', 'config.toml');
    let content = fs.readFileSync(tomlPath, 'utf8');
    const modelMap = {
      claude: 'claude-sonnet-5',
      codex: 'gpt-5.3-codex',
      gemini: 'gemini-2.5-pro',
      openai: 'gpt-4.1',
    };
    const newModel = modelMap[PROVIDER] || 'claude-sonnet-5';
    // Chỉ patch dòng model = "..." ở top-level (không phải trong [profiles])
    content = content.replace(/^model\s*=\s*"[^"]*"/m, `model = "${newModel}"`);
    fs.writeFileSync(tomlPath, content, 'utf8');
    log.ok(`Đã patch .agents/config.toml model = "${newModel}" (provider: ${PROVIDER})`);
  }
}

// Bước 12: In tóm tắt MAX POWER
function printSummary(ws) {
  log.head('Tóm tắt thiết lập MAX POWER');
  log.ok(`Workspace: ${ws}`);
  log.ok(`Mode: ${LOCAL ? 'CỤC BỘ (local)' : 'GLOBAL/npx'}`);
  log.ok(`Provider mặc định: ${PROVIDER}`);
  log.ok('');
  log.ok('[Claude Code] .claude/settings.json → MAX POWER (hierarchical-mesh, 15 agents, hybrid+HNSW)');
  log.ok('[Claude Code] .claude-flow/runtime.json → runtime MAX');
  log.ok('[Claude Code] Hooks: 8 loại (PreToolUse, PostToolUse, UserPromptSubmit, SessionStart, SessionEnd, Stop, PreCompact, SubagentStop)');
  log.ok('[Claude Code] Daemon: 10 workers (map, audit, optimize, consolidate, testgaps, ultralearn, deepdive, document, refactor, benchmark)');
  log.ok('[Claude Code] Agent Teams + Learning + Security + Skills/Commands/Agents/MCP ALL');
  if (!SKIP_DEVIN) {
    log.ok('[Devin CLI] .devin/config.json + mcp_config.json + hooks.v1.json (6 events) + skills/');
  }
  if (!SKIP_AGY) {
    log.ok('[Antigravity CLI] .agents/mcp_config.json + config.toml + AGENTS.md');
  }
  if (!SKIP_PROVIDERS) {
    log.ok('[Providers] .claude-flow/providers.json (claude+codex+gemini+openai+openrouter, 3-tier routing)');
  }
  log.ok('[HLK] layer đã cài (nếu không --skip-hlk)');
  log.ok('[Git] hooks: core.hooksPath .githooks (nếu có .git)');
  log.info('');
  log.info('Các bước tiếp theo:');
  if (LOCAL) {
    log.info('  0. Ruflo đã cài cục bộ: npx ruflo <command>  (chạy trong workspace)');
  } else {
    log.info('  0. Dùng: npx ruflo@latest <command>  (hoặc ruflo <command> nếu đã global)');
  }
  log.info('  1. Mở HLK/config/secrets.env và điền API keys / tokens thật.');
  log.info('  2. Đặt env vars cho provider: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY...');
  log.info('  3. Khởi động lại Claude Code / Devin CLI / agy để MCP server load.');
  log.info('  4. Test swarm: npx ruflo swarm init --topology hierarchical-mesh --max-agents 15');
  log.info('  5. Test memory: npx ruflo memory store --key test --value ok --namespace patterns');
  log.info('  6. Test daemon: npx ruflo daemon status');
  log.info('  7. Update sau: npm run update:max-power -- --path <ws>  (hoặc --local)');
  log.info('  8. Đọc AGENTS.md / CLAUDE.md để hiểu workflow full chain.');
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  process.stderr.write('\n');
  process.stderr.write('╔═══════════════════════════════════════════════════════════╗\n');
  process.stderr.write('║  Ruflo MAX POWER Setup — Full Chain / Full Flow / Max Cfg  ║\n');
  process.stderr.write('╚═══════════════════════════════════════════════════════════╝\n\n');

  // Bước 0: prerequisites (kiểm tra Node/npm/git, không exit nếu thiếu ruflo)
  checkPrerequisites();

  // Bước 1: Hỏi tất cả tham số (workspace, local/global, provider, version, tính năng, xác nhận)
  // Nếu --yes: bỏ qua hỏi, dùng mặc định
  await askAllParams();

  const ws = path.resolve(USER_PATH);

  // Bước 2-11: thực thi thiết lập
  installRuflo(ws);
  patchSettingsMaxPower(ws);
  writeRuntimeConfig(ws);
  patchGitFiles(ws);
  installHlkLayer(ws);
  enableGitHooks(ws);
  setupDevinCli(ws);
  setupAntigravityCli(ws);
  setupProviders(ws);
  verifySetup(ws);

  // Tóm tắt
  printSummary(ws);

  process.stderr.write('\n');
  log.ok('Ruflo MAX POWER setup hoàn tất.');
  process.exit(0);
}

main().catch((e) => {
  log.err(`Lỗi không xử lý được: ${e?.stack || e?.message || e}`);
  process.exit(1);
});
