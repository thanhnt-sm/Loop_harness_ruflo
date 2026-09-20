#!/usr/bin/env node
/**
 * HLK Loop Runner — vòng lặp tự học theo triết lý ruflo
 * ------------------------------------------------------
 * Mục đích tổng thể:
 *   Đọc pipeline từ hlk-loop.config.json, tự tính "wave" (nhóm bước có thể
 *   chạy song song dựa trên đồ thị phụ thuộc), spawn mỗi bước thành một
 *   session agent ĐỘC LẬP (tiến trình con riêng), rồi thu hoạch mục
 *   "## Learnings" từ báo cáo để tích lũy tri thức (self-learn):
 *     - Ghi dồn vào HLK/reports/learnings.md
 *     - Đẩy vào bộ nhớ ruflo (memory namespace "patterns") nếu bật
 *
 * Giải thuật chính:
 *   1. Nạp config + trạng thái checkpoint (HLK/logs/loop-state.json)
 *   2. Tính toposort theo depends_on → chia thành các wave song song
 *   3. Bước nào đã có báo cáo hợp lệ (có mục Learnings) thì bỏ qua (idempotent)
 *   4. Chạy song song các bước trong wave (trừ bước serial_only chạy một mình)
 *   5. Sau mỗi wave: thu hoạch learnings, cập nhật checkpoint
 *   6. Khi mọi bước xong → exit 3 (DONE); còn việc → exit 0 (CONTINUE)
 *
 * Cách dùng:
 *   node HLK/loop/hlk-loop.mjs             # chạy 1 iteration (1 lượt các wave còn thiếu)
 *   node HLK/loop/hlk-loop.mjs --dry-run   # chỉ in kế hoạch wave, không chạy gì
 *   node HLK/loop/hlk-loop.mjs --status    # xem trạng thái checkpoint hiện tại
 *   node HLK/loop/hlk-loop.mjs --reset     # xóa checkpoint, bắt đầu lại từ đầu
 *
 * Exit codes (tương thích scripts/loop-checkpoint.mjs):
 *   0 = CONTINUE (còn bước chưa xong, gọi lại để tiếp tục)
 *   1 = ERROR
 *   3 = DONE (tất cả bước đã hoàn thành)
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync, appendFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Bước 0: Xác định thư mục gốc repo (HLK/loop/ → lùi 2 cấp)
const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..', '..');
const CONFIG_PATH = join(__dirname, 'hlk-loop.config.json');

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');
const STATUS = args.includes('--status');
const RESET = args.includes('--reset');

// ---------- Tiện ích ----------

function log(msg) {
  // Log tiếng Việt kèm timestamp để dễ theo dõi khi chạy tự động
  console.log(`[HLK-LOOP ${new Date().toISOString()}] ${msg}`);
}

function loadJson(path, fallback = null) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return fallback;
  }
}

// ---------- Bước 1: Nạp config và checkpoint ----------

const config = loadJson(CONFIG_PATH);
if (!config) {
  console.error(`[HLK-LOOP] Không đọc được config: ${CONFIG_PATH}`);
  process.exit(1);
}

const STATE_PATH = join(ROOT, config.loop.state_file);
const LEARNINGS_PATH = join(ROOT, config.loop.learnings_file);

function loadState() {
  return loadJson(STATE_PATH, { iteration: 0, completed: [], harvested: [], history: [] });
}

function saveState(state) {
  mkdirSync(dirname(STATE_PATH), { recursive: true });
  writeFileSync(STATE_PATH, JSON.stringify(state, null, 2), 'utf8');
}

if (RESET) {
  // Xóa checkpoint để chạy lại từ đầu (KHÔNG xóa báo cáo đã có)
  if (existsSync(STATE_PATH)) rmSync(STATE_PATH);
  log('Đã reset checkpoint. Báo cáo cũ trong HLK/reports/ vẫn giữ nguyên.');
  process.exit(0);
}

// ---------- Bước 2: Kiểm tra bước nào đã hoàn thành ----------

/**
 * Một bước được coi là HOÀN THÀNH khi file báo cáo tồn tại
 * và có mục "## Learnings" (chứng tỏ agent đã chạy trọn vẹn quy trình tự học).
 */
function isStepDone(step) {
  const reportPath = join(ROOT, step.report);
  if (!existsSync(reportPath)) return false;
  const content = readFileSync(reportPath, 'utf8');
  return /##\s*Learnings/i.test(content);
}

// ---------- Bước 3: Tính wave song song từ đồ thị phụ thuộc ----------

/**
 * Chia các bước thành wave: wave N gồm các bước mà mọi phụ thuộc
 * đều nằm ở wave trước đó → mọi bước cùng wave chạy SONG SONG được.
 */
function computeWaves(steps) {
  const waves = [];
  const placed = new Set();
  let remaining = [...steps];
  while (remaining.length > 0) {
    const wave = remaining.filter((s) => s.depends_on.every((d) => placed.has(d)));
    if (wave.length === 0) {
      console.error('[HLK-LOOP] Phát hiện phụ thuộc vòng tròn trong config!');
      process.exit(1);
    }
    wave.forEach((s) => placed.add(s.id));
    remaining = remaining.filter((s) => !placed.has(s.id));
    waves.push(wave);
  }
  return waves;
}

// ---------- Bước 4: Chạy một bước bằng session agent độc lập ----------

function runStep(step) {
  return new Promise((resolvePromise) => {
    const promptFile = step.prompt;
    const reportFile = step.report;
    // Thay placeholder trong args_template bằng đường dẫn thực tế
    const argsResolved = config.runner.args_template.map((a) =>
      a.replaceAll('{promptFile}', promptFile).replaceAll('{reportFile}', reportFile)
    );

    if (config.runner.mode === 'manual') {
      // Chế độ manual: chỉ in hướng dẫn — dành cho agent ngoài (Devin/Claude Code) tự nhận việc
      log(`[MANUAL] Bước ${step.id} (${step.name}): thực thi prompt "${promptFile}" → ghi báo cáo "${reportFile}"`);
      resolvePromise({ step, ok: false, manual: true });
      return;
    }

    log(`▶ Spawn session độc lập cho bước ${step.id} (${step.name})...`);
    const child = spawn(config.runner.command, argsResolved, {
      cwd: ROOT,
      shell: process.platform === 'win32', // Windows cần shell để resolve npx
      stdio: 'inherit',
    });

    // Bảo vệ: timeout để loop không treo vô hạn khi một session bị kẹt
    const timer = setTimeout(() => {
      log(`⏱ Bước ${step.id} vượt quá timeout — hủy tiến trình con.`);
      child.kill('SIGTERM');
    }, config.runner.timeout_ms || 1800000);

    child.on('exit', (code) => {
      clearTimeout(timer);
      // Thành công thực sự = tiến trình exit 0 VÀ báo cáo có mục Learnings
      const ok = code === 0 && isStepDone(step);
      log(`${ok ? '✅' : '❌'} Bước ${step.id} kết thúc (exit=${code}, report=${ok ? 'hợp lệ' : 'chưa đạt'})`);
      resolvePromise({ step, ok });
    });
    child.on('error', (err) => {
      clearTimeout(timer);
      log(`❌ Bước ${step.id} lỗi spawn: ${err.message}`);
      resolvePromise({ step, ok: false });
    });
  });
}

// ---------- Bước 5: Thu hoạch learnings từ báo cáo (self-learn) ----------

function harvestLearnings(step, state) {
  const reportPath = join(ROOT, step.report);
  if (!existsSync(reportPath) || state.harvested.includes(step.id)) return;
  const content = readFileSync(reportPath, 'utf8');
  // Cắt phần sau tiêu đề "## Learnings" đến hết file hoặc heading kế tiếp
  const match = content.match(/##\s*Learnings\s*\n([\s\S]*?)(?=\n##\s|$)/i);
  if (!match) return;
  const block = [
    `\n### [${new Date().toISOString()}] Bước ${step.id} — ${step.name}`,
    match[1].trim(),
    '',
  ].join('\n');
  mkdirSync(dirname(LEARNINGS_PATH), { recursive: true });
  if (!existsSync(LEARNINGS_PATH)) {
    writeFileSync(LEARNINGS_PATH, '# HLK Loop — Sổ tích lũy tri thức (Learnings)\n', 'utf8');
  }
  appendFileSync(LEARNINGS_PATH, block, 'utf8');
  state.harvested.push(step.id);
  log(`📚 Đã thu hoạch learnings của bước ${step.id} vào ${config.loop.learnings_file}`);

  // Đẩy vào bộ nhớ ruflo để các agent/session khác tra cứu lại (best-effort, lỗi không chặn loop)
  if (config.loop.store_learnings_to_memory) {
    const value = match[1].trim().slice(0, 4000);
    const mem = spawn(
      'npx',
      ['claude-flow', 'memory', 'store', '--namespace', config.loop.memory_namespace,
       '--key', `hlk-loop-${step.id}-${step.name}`, '--value', value],
      { cwd: ROOT, shell: process.platform === 'win32', stdio: 'ignore' }
    );
    mem.on('error', () => log(`⚠ Không đẩy được learnings bước ${step.id} vào memory (bỏ qua).`));
  }
}

// ---------- Bước 6: Vòng lặp chính ----------

/**
 * Auto-sync HLK/chain/ → mirrors mỗi iteration (Plan 8 phase 1).
 * Best-effort: nếu fail, log warning + tiếp tục loop (không block).
 */
function autoSyncMirrors() {
  return new Promise((resolvePromise) => {
    if (DRY_RUN || STATUS || RESET) {
      log('⏭ Bỏ qua auto-sync (dry-run / status / reset mode)');
      resolvePromise();
      return;
    }
    log('🔄 Auto-sync HLK → mirrors...');
    const isWindows = process.platform === 'win32';
    const pyCmd = isWindows ? 'py' : 'python3';
    const child = spawn(
      pyCmd, ['HLK/scripts/sync_to_mirrors.py', '--target', 'all'],
      { cwd: ROOT, stdio: 'pipe', shell: isWindows }
    );
    let stdout_buf = '';
    let stderr_buf = '';
    child.stdout.on('data', (d) => { stdout_buf += d.toString(); });
    child.stderr.on('data', (d) => { stderr_buf += d.toString(); });
    child.on('exit', (code) => {
      if (code === 0) {
        const lines = stdout_buf.split('\n').filter(l => l.includes('created/updated')).length;
        log(`✅ Auto-sync done: ${lines} file(s) updated`);
      } else {
        log(`⚠ Auto-sync fail (code=${code}, stderr=${stderr_buf.slice(0, 200)})`);
      }
      resolvePromise();
    });
    child.on('error', (err) => {
      log(`⚠ Auto-sync spawn error: ${err.message}`);
      resolvePromise();
    });
  });
}

async function main() {
  await autoSyncMirrors();
  const state = loadState();
  const waves = computeWaves(config.steps);

  if (STATUS) {
    // In trạng thái hiện tại rồi thoát
    log(`Iteration: ${state.iteration}`);
    config.steps.forEach((s) => log(`  Bước ${s.id} (${s.name}): ${isStepDone(s) ? '✅ xong' : '⬜ chưa'}`));
    process.exit(0);
  }

  state.iteration += 1;
  log(`=== Iteration ${state.iteration}/${config.loop.max_iterations} ===`);

  if (state.iteration > config.loop.max_iterations) {
    log('Đã vượt max_iterations — dừng để tránh loop vô hạn.');
    process.exit(1);
  }

  let anyPending = false;
  for (let i = 0; i < waves.length; i++) {
    const pending = waves[i].filter((s) => !isStepDone(s));
    // Thu hoạch learnings cho các bước đã xong từ trước (kể cả do agent ngoài chạy)
    waves[i].filter(isStepDone).forEach((s) => harvestLearnings(s, state));
    if (pending.length === 0) continue;
    anyPending = true;

    log(`— Wave ${i + 1}: ${pending.map((s) => s.id).join(', ')} (${pending.length} bước song song)`);
    if (DRY_RUN) continue;

    // Bước ghi code (serial_only) phải chạy MỘT MÌNH để tránh 2 writer cùng worktree
    const parallel = pending.filter((s) => !s.serial_only);
    const serial = pending.filter((s) => s.serial_only);
    const results = await Promise.all(parallel.map(runStep));
    for (const s of serial) results.push(await runStep(s));

    // Thu hoạch learnings của các bước vừa thành công
    results.filter((r) => r.ok).forEach((r) => harvestLearnings(r.step, state));
    state.history.push({
      at: new Date().toISOString(),
      wave: i + 1,
      results: results.map((r) => ({ id: r.step.id, ok: r.ok })),
    });

    // Nếu cả wave thất bại → dừng iteration này (lần gọi sau sẽ thử lại)
    if (results.every((r) => !r.ok)) {
      log('⚠ Toàn bộ wave thất bại — dừng iteration, lần chạy sau sẽ thử lại.');
      break;
    }
  }

  state.completed = config.steps.filter(isStepDone).map((s) => s.id);
  saveState(state);

  if (state.completed.length === config.steps.length) {
    log('🎉 DONE — toàn bộ pipeline HLK đã hoàn thành, learnings đã tích lũy.');
    process.exit(3);
  }
  log(`CONTINUE — đã xong ${state.completed.length}/${config.steps.length} bước.${anyPending && DRY_RUN ? ' (dry-run: chưa chạy gì)' : ''}`);
  process.exit(0);
}

main().catch((err) => {
  console.error('[HLK-LOOP] Lỗi không mong đợi:', err);
  process.exit(1);
});
