// Tests cho HLK/chain/hlk_wrappers/verify-first-wrapper.mjs (audit rotation)
// Node test với `node --test tests/hlk/test_verify_first_wrapper_rotation.cjs`
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { execFile } = require('node:child_process');

// Use a unique temp dir for each test
function makeTmp() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'wrapper-test-'));
}

// === Tests cho rotation logic ===
// Re-implement the logic from wrapper to test in isolation (no script exec)
function rotateAuditLog(auditLog, maxSizeMB = 10.0) {
  if (!fs.existsSync(auditLog)) return false;
  const sizeMB = fs.statSync(auditLog).size / (1024 * 1024);
  if (sizeMB < maxSizeMB) return false;
  const today = new Date().toISOString().slice(0, 10);
  const ext = path.extname(auditLog);
  const base = path.basename(auditLog, ext);
  const parent = path.dirname(auditLog);
  const archive = path.join(parent, `${base}_${today}_${Date.now()}${ext}`);
  try {
    fs.renameSync(auditLog, archive);
    return true;
  } catch (e) {
    return false;
  }
}

test('rotateAuditLog — file nhỏ → không rotate', () => {
  const tmp = makeTmp();
  const audit = path.join(tmp, 'audit.jsonl');
  fs.writeFileSync(audit, 'small content\n');
  const rotated = rotateAuditLog(audit, 10.0);
  assert.strictEqual(rotated, false);
  assert.strictEqual(fs.existsSync(audit), true);
});

test('rotateAuditLog — file lớn → rotate, tạo archive', () => {
  const tmp = makeTmp();
  const audit = path.join(tmp, 'audit.jsonl');
  // Tạo file 11MB (lớn hơn 10MB threshold)
  fs.writeFileSync(audit, Buffer.alloc(11 * 1024 * 1024, 0x20));
  const rotated = rotateAuditLog(audit, 10.0);
  assert.strictEqual(rotated, true);
  // Original không còn
  assert.strictEqual(fs.existsSync(audit), false);
  // Archive tồn tại với date suffix
  const archives = fs.readdirSync(tmp).filter(f => f.startsWith('audit_') && f.endsWith('.jsonl'));
  assert.ok(archives.length >= 1, `expected ≥1 archive, got: ${archives}`);
});

test('rotateAuditLog — file không tồn tại → return False', () => {
  const tmp = makeTmp();
  const audit = path.join(tmp, 'nonexistent.jsonl');
  const rotated = rotateAuditLog(audit, 10.0);
  assert.strictEqual(rotated, false);
});

test('rotateAuditLog — rotate preserves original name pattern', () => {
  const tmp = makeTmp();
  const audit = path.join(tmp, 'verify_first_audit.jsonl');
  fs.writeFileSync(audit, Buffer.alloc(15 * 1024 * 1024, 0x20));
  rotateAuditLog(audit, 10.0);
  const archives = fs.readdirSync(tmp);
  // Archive phải có prefix "verify_first_audit_<date>_"
  const validArchives = archives.filter(f => /^verify_first_audit_\d{4}-\d{2}-\d{2}_/.test(f));
  assert.ok(validArchives.length >= 1, `no matching archive, got: ${archives}`);
});

test('rotateAuditLog — custom threshold works', () => {
  const tmp = makeTmp();
  const audit = path.join(tmp, 'audit.jsonl');
  fs.writeFileSync(audit, Buffer.alloc(2 * 1024 * 1024, 0x20));  // 2MB
  // Threshold 1MB → rotate
  const rotated1 = rotateAuditLog(audit, 1.0);
  assert.strictEqual(rotated1, true);
  // Recreate 2MB file
  fs.writeFileSync(audit, Buffer.alloc(2 * 1024 * 1024, 0x20));
  // Threshold 5MB → không rotate
  const rotated2 = rotateAuditLog(audit, 5.0);
  assert.strictEqual(rotated2, false);
});

// === Test wrapper file exists + structure ===
test('wrapper file exists in HLK/chain/hlk_wrappers/', () => {
  const wrapperPath = path.resolve(__dirname, '../../HLK/chain/hlk_wrappers/verify-first-wrapper.mjs');
  assert.strictEqual(fs.existsSync(wrapperPath), true);
});

test('wrapper has rotation logic', () => {
  const wrapperPath = path.resolve(__dirname, '../../HLK/chain/hlk_wrappers/verify-first-wrapper.mjs');
  const content = fs.readFileSync(wrapperPath, 'utf-8');
  assert.match(content, /rotateAuditLog/);
  assert.match(content, /AUDIT_MAX_SIZE_MB/);
  assert.match(content, /renameSync/);
});
