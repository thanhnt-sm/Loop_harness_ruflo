#!/usr/bin/env node
/**
 * hlk-check-merge-ours.mjs
 * ========================
 * Deterministic gate cho merge=ours log — nhắc review khi upstream sửa file HLK
 * mà merge=ours giữ bản địa (đóng băng security patch).
 *
 * Nguyên tắc:
 *  - Pending = dòng log dạng `(merge active) GIỮ bản địa: <path>` chưa được --ack.
 *  - Dòng informational (`NGOÀI merge`, `bỏ qua`) KHÔNG tính pending.
 *  - Reviewed-tracker: HLK/logs/merge-ours-reviewed.json — list {ts, path, reviewedAt}.
 *  - Exit code: 0 = không còn pending; 1 = còn pending (CI/doctor/post-merge gate).
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-check-merge-ours.mjs [--json] [--ack <timestamp>] [--help]
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOG_PATH = path.resolve(__dirname, '../logs/merge-ours.log');
const REVIEWED_PATH = path.resolve(__dirname, '../logs/merge-ours-reviewed.json');

const args = process.argv.slice(2);
const AS_JSON = args.includes('--json');
const ACK = args.indexOf('--ack') !== -1 ? args[args.indexOf('--ack') + 1] : null;
const HELP = args.includes('--help') || args.includes('-h');

if (HELP) {
  process.stdout.write(`hlk-check-merge-ours.mjs — gate review cho merge=ours log

  node HLK/git-tools/hlk-check-merge-ours.mjs [--json] [--ack <ts>]

  --ack <ts>   Đánh dấu dòng log có timestamp <ts> đã được review.
  --json       Output JSON (exit 0 khi hết pending, 1 khi còn pending).
`);
  process.exit(0);
}

function readJsonOrEmpty(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch {
    return [];
  }
}

function pendingItems() {
  if (!fs.existsSync(LOG_PATH)) return [];
  const lines = fs.readFileSync(LOG_PATH, 'utf8').split('\n');
  const reviewed = new Set(readJsonOrEmpty(REVIEWED_PATH).map((r) => r.ts));
  const pending = [];
  for (const line of lines) {
    if (!line.includes('GIỮ bản địa')) continue;
    if (line.includes('NGOÀI merge') || line.includes('bỏ qua')) continue;
    const m = line.match(/^\[([^\]]+)\]/);
    if (!m) continue;
    const ts = m[1];
    if (reviewed.has(ts)) continue;
    pending.push({ ts, line: line.trim(), reviewed: false });
  }
  return pending;
}

if (ACK) {
  if (!fs.existsSync(LOG_PATH)) {
    process.stderr.write(`[HLK] Không có ${LOG_PATH}\n`);
    process.exit(1);
  }
  const logText = fs.readFileSync(LOG_PATH, 'utf8');
  const match = logText.split('\n').find((l) => l.startsWith(`[${ACK}]`) && l.includes('GIỮ bản địa'));
  if (!match) {
    process.stderr.write(`[HLK] Không tìm thấy dòng merge=ours chưa review với timestamp ${ACK}\n`);
    process.exit(1);
  }
  const tracker = readJsonOrEmpty(REVIEWED_PATH);
  if (!tracker.some((r) => r.ts === ACK)) {
    const fileMatch = match.match(/GIỮ bản địa:\s*(.+?)\s*$/);
    tracker.push({
      ts: ACK,
      path: fileMatch ? fileMatch[1].trim() : '(unknown)',
      reviewedAt: new Date().toISOString(),
    });
    fs.mkdirSync(path.dirname(REVIEWED_PATH), { recursive: true });
    fs.writeFileSync(REVIEWED_PATH, JSON.stringify(tracker, null, 2), 'utf8');
  }
  if (AS_JSON) process.stdout.write(JSON.stringify({ ack: ACK }, null, 2) + '\n');
  else process.stdout.write(`✅ [HLK] Đã đánh dấu review: ${ACK}\n`);
  process.exit(0);
}

const pending = pendingItems();
if (AS_JSON) {
  process.stdout.write(JSON.stringify({ pending, count: pending.length }, null, 2) + '\n');
} else if (pending.length === 0) {
  process.stdout.write('✅ [HLK] Không có merge=ours cần review.\n');
} else {
  process.stdout.write(`⚠️  [HLK] ${pending.length} file HLK bị giữ bản địa (merge=ours) chưa review:\n`);
  for (const p of pending) process.stdout.write(`  - [${p.ts}] ${p.line}\n`);
  process.stdout.write('   → Review thủ công security patch; sau đó: node HLK/git-tools/hlk-check-merge-ours.mjs --ack <ts>\n');
}
process.exit(pending.length === 0 ? 0 : 1);
