# Upgrade Plan — Loop Harness (AHD)

> **Kế hoạch nâng cấp toàn diện** từ Red Team Report, chi tiết đến từng file, từng dòng, có acceptance criteria testable, verification steps, và dependency graph.
>
> **Mục tiêu**: Đưa hệ thống từ điểm số trung bình 5.1/10 lên 9/10+ trong 4 phase.
> **Ngày tạo**: 2026-07-07
> **Nguồn**: `HLK/docs/REDTEAM_REPORT.md` (7-expert red team council)
> **Tracking**: `.devin/upgrade/UPGRADE_TRACKER.json`
> **Execution protocol**: `.devin/upgrade/UPGRADE_EXECUTION_PROTOCOL.md`

---

## Cách dùng tài liệu này

### Cho mỗi session thực thi upgrade

1. Đọc `UPGRADE_TRACKER.json` → tìm upgrade có `status: "pending"` tiếp theo
2. Đọc spec của upgrade đó trong file này (tìm theo ID: `## UXX`)
3. Thực thi theo spec — tạo/sửa file đúng như mô tả
4. Chạy verification steps → confirm acceptance criteria pass
5. Update `UPGRADE_TRACKER.json`: `status: "done"`, ghi `completed_date`, `verifier`, `notes`
6. Commit với format: `fix(upgrade): UXX <title> [P0]`
7. Nếu upgrade có dependents → check chúng có unblock không

### Quy tắc không drift

- **Không skip acceptance criteria** — mỗi upgrade có AC testable, phải pass 100%
- **Không skip verification** — phải chạy verification steps, không chỉ "looks done"
- **Không modify spec khi đang thực thi** — nếu cần change, tạo UPR (Upgrade Proposal Review) trong tracker
- **Một upgrade per commit** — không gộp nhiều upgrade trong 1 commit
- **Đọc tracker trước khi bắt đầu** — không bao giờ giả định trạng thái, luôn verify

---

## Phase 0 — Critical (P0) — 10 upgrades — Target: 1-2 weeks

### U01: Truncate `.devin/AGENTS.md` → 5KB summary

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Token Economist |
| Impact | -41K tokens/session (26% → 6% context) |
| Effort | 1 ngày |
| Dependencies | None |
| Risk if not done | 26% context window wasted mỗi session |

**Problem**: `.devin/AGENTS.md` là 186KB (2722 lines, ~46.5K tokens) — full canon concatenation được load mỗi session. Đây là token waste lớn nhất trong hệ thống.

**Solution spec**:
1. Tạo `.devin/AGENTS_summary.md` — summary 5KB (~1250 tokens) chứa:
   - 1 đoạn intro: "You are operating inside AHD harness. Read canon on-demand."
   - Table of 10 canon files với 1-line description mỗi file + path
   - Table of skills với trigger conditions
   - Table of agents/personas với model + role
   - Link đến `UPGRADE_PLAN.md` và `REDTEAM_REPORT.md`
   - Key red lines (top 5) inline, full 18 red lines trong `REDLINES.md`
2. Thay thế `.devin/AGENTS.md` content bằng content của `AGENTS_summary.md`
3. Giữ `.devin/AGENTS_full.md` — bản full 186KB cho reference (không auto-load)
4. Update `BOOT_PROTOCOL.md` step 1: "Read entry file (AGENTS.md summary). Load canon on-demand per steps below."

**Files to modify**:
- `.devin/AGENTS.md` — replace content với summary
- `.devin/AGENTS_full.md` — new file (copy of old AGENTS.md)
- `.devin/canon/BOOT_PROTOCOL.md` — update step 1 description

**Acceptance criteria**:
- [ ] `.devin/AGENTS.md` < 6KB (verify: `(Get-Item .devin/AGENTS.md).Length -lt 6144`)
- [ ] `.devin/AGENTS_full.md` tồn tại và > 180KB
- [ ] Summary chứa table reference đến tất cả 10 canon files
- [ ] Summary chứa table reference đến tất cả skills
- [ ] BOOT_PROTOCOL.md step 1 updated
- [ ] `verify-workspace.ps1` vẫn pass 73/73

**Verification steps**:
```powershell
# 1. Check size
(Get-Item .devin/AGENTS.md).Length  # must be < 6144
(Get-Item .devin/AGENTS_full.md).Length  # must be > 180000

# 2. Check content references
Select-String -Path .devin/AGENTS.md -Pattern "CORE_CANON|BOOT_PROTOCOL|MEMORY_PROTOCOL|LOOP_PROTOCOL|VERIFICATION_PROTOCOL|CAVEMAN_PROTOCOL|HARNESS_ENGINEERING|JUDGMENT_RUBRICS|HANDOFF_LETTER|REDLINES" | Measure-Object  # must be >= 10

# 3. Run verify-workspace
powershell -File tools/verify-workspace.ps1  # must pass 73/73
```

---

### U02: Fix regex bypass in `pre_tool_use.py`

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Security Red Teamer |
| Impact | Close silent RCE hole |
| Effort | 2-3 ngày |
| Dependencies | None |
| Risk if not done | Destructive commands bypass guard via shell encoding |

**Problem**: `DANGEROUS_PATTERNS` regex match raw command string. Shell encoding bypasses:
- `r\m -rf /` — backslash escaping
- `r''m -rf /` — quote obfuscation
- `$(echo rm) -rf /` — command substitution
- `echo cm0gLXJmIC8= | base64 -d | bash` — base64 encoding

**Solution spec**:
1. Thêm `normalize_command()` function trong `pre_tool_use.py`:
   ```python
   import shlex
   
   def normalize_command(command: str) -> str:
       """Normalize shell command before pattern matching.
       
       Strips quotes, expands simple command substitutions,
       decodes base64 piped to shell.
       """
       # 1. Remove backslash escaping (r\m -> rm)
       normalized = re.sub(r'\\(.)', r'\1', command)
       
       # 2. Remove quotes (r''m -> rm, r""m -> rm)
       normalized = re.sub(r"['\"]", "", normalized)
       
       # 3. Expand simple $(echo X) substitutions
       normalized = re.sub(
           r'\$\(echo\s+(\S+)\)',
           lambda m: m.group(1),
           normalized
       )
       
       # 4. Detect base64 piped to shell
       if re.search(r'base64\s+-d\s*\|\s*(bash|sh|zsh)', normalized):
           # Flag as suspicious — can't safely decode in hook
           # but pattern itself is dangerous
           normalized += " BASE64_PIPE_TO_SHELL_DETECTED"
       
       return normalized
   ```
2. Apply `normalize_command()` trước khi check `DANGEROUS_PATTERNS`:
   ```python
   command = tool_input.get("command", "")
   if not command:
       sys.exit(0)
   
   # Normalize before pattern matching (U02: fix regex bypass)
   normalized = normalize_command(command)
   
   # Check dangerous patterns against BOTH raw and normalized
   for pattern, reason in DANGEROUS_PATTERNS:
       if re.search(pattern, command, re.IGNORECASE) or \
          re.search(pattern, normalized, re.IGNORECASE):
           print(f"[AHD guard] BLOCKED: {reason}", file=sys.stderr)
           sys.exit(2)
   ```
3. Thêm new pattern cho base64 pipe:
   ```python
   (r"base64\s+-d\s*\|\s*(bash|sh|zsh)", "base64 decoded piped to shell"),
   ```

**Files to modify**:
- `.devin/hooks/pre_tool_use.py` — add `normalize_command()`, update `main()`

**Acceptance criteria**:
- [ ] `normalize_command("r\\m -rf /")` returns `"rm -rf /"` (matches dangerous pattern)
- [ ] `normalize_command("r''m -rf /")` returns `"rm -rf /"` (matches)
- [ ] `normalize_command("$(echo rm) -rf /")` returns `"rm -rf /"` (matches)
- [ ] `normalize_command("echo cm0gLXJmIC8= | base64 -d | bash")` triggers base64 pattern
- [ ] `normalize_command("rm -rf /")` returns `"rm -rf /"` (unchanged, still matches)
- [ ] `normalize_command("git status")` returns `"git status"` (unchanged, no false positive)
- [ ] Hook still exits 0 for safe commands
- [ ] Hook exits 2 for all bypass variants

**Verification steps**:
```powershell
# 1. Test bypass variants
$testCases = @(
    @{cmd="r\m -rf /"; expected=2},
    @{cmd="r''m -rf /"; expected=2},
    @{cmd='$(echo rm) -rf /'; expected=2},
    @{cmd="echo cm0gLXJmIC8= | base64 -d | bash"; expected=2},
    @{cmd="rm -rf /"; expected=2},
    @{cmd="git status"; expected=0},
    @{cmd="npm test"; expected=0}
)

foreach ($tc in $testCases) {
    $input = @{tool_name="Bash"; tool_input=@{command=$tc.cmd}} | ConvertTo-Json -Compress
    $result = $input | python .devin/hooks/pre_tool_use.py 2>$null
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne $tc.expected) {
        Write-Output "FAIL: '$($tc.cmd)' expected $($tc.expected), got $exitCode"
    } else {
        Write-Output "PASS: '$($tc.cmd)' -> $exitCode"
    }
}
```

---

### U03: Expand deny list in `config.json`

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Security Red Teamer |
| Impact | Close destructive command gaps |
| Effort | 1 ngày |
| Dependencies | None |
| Risk if not done | Agent executes `chmod 777`, `chown`, `git clean -fd`, `dd`, `format` |

**Problem**: Deny list thiếu nhiều destructive commands. Allow list quá broad (`Exec(node:*)`, `Exec(npm run:*)`).

**Solution spec**:
1. Add to `deny` array trong `.devin/config.json`:
   ```json
   "Exec(chmod 777:*)",
   "Exec(chmod -R 777:*)",
   "Exec(chown:*)",
   "Exec(git clean -fd:*)",
   "Exec(git checkout -- .:*)",
   "Exec(git branch -D:*)",
   "Exec(dd:*)",
   "Exec(format:*)",
   "Exec(wget * | bash:*)",
   "Exec(wget * | sh:*)",
   "Exec(curl * | sh:*)",
   "Exec(shred:*)",
   "Exec(:(){ :|:& };:)"
   ```
2. Narrow `allow` list:
   - `Exec(node:*)` → `Exec(node scripts/*)`, `Exec(node .devin/scripts/*)`
   - `Exec(npm run:*)` → `Exec(npm run build)`, `Exec(npm run test)`, `Exec(npm run lint)`
3. Add to `ask` array:
   ```json
   "Exec(git push)",
   "Exec(git commit)",
   "Exec(npm publish)",
   "Exec(pip install)",
   "Exec(git merge:*)",
   "Exec(git rebase:*)"
   ```

**Files to modify**:
- `.devin/config.json` — expand `deny`, narrow `allow`, populate `ask`

**Acceptance criteria**:
- [ ] `deny` array contains all 13 new patterns
- [ ] `allow` array does NOT contain `Exec(node:*)` (broad)
- [ ] `allow` array contains `Exec(node scripts/*)` (narrowed)
- [ ] `ask` array contains 6 patterns (git push, git commit, npm publish, pip install, git merge, git rebase)
- [ ] `config.json` is valid JSON (verify: `Get-Content .devin/config.json | ConvertFrom-Json`)

**Verification steps**:
```powershell
$config = Get-Content .devin/config.json | ConvertFrom-Json
# Check deny
$requiredDeny = @("chmod 777","chown","git clean -fd","dd","format","wget.*bash","shred")
foreach ($p in $requiredDeny) {
    if ($config.permissions.deny -notmatch $p) { Write-Output "FAIL: missing deny $p" }
}
# Check ask
if ($config.permissions.ask.Count -lt 6) { Write-Output "FAIL: ask list too short" }
# Check allow narrowed
if ($config.permissions.allow -contains "Exec(node:*)") { Write-Output "FAIL: node:* still broad" }
Write-Output "All checks passed"
```

---

### U04: Simplify BOOT Protocol → lazy-load model

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Architecture Critic + Performance Engineer |
| Impact | -60-70% cold start cho S/M tasks |
| Effort | 1 tuần |
| Dependencies | U01 (AGENTS.md truncate must come first) |
| Risk if not done | 2-8s cold start mỗi session, disproportionate cho simple tasks |

**Problem**: BOOT Protocol 17 steps mandatory, đọc ~158KB (target <16KB). Cold start 2-8s. Cho S/M tasks, overhead disproportionate.

**Solution spec**:
1. Split BOOT thành 3 tiers trong `BOOT_PROTOCOL.md`:
   - **Tier 1 — Core BOOT (mandatory, all tasks)**: Steps 1-8
     - Read entry file (AGENTS.md summary)
     - Ensure registry exists
     - Read registry
     - Read knowledge layer
     - Read user profile
     - Read handoff letter
     - Determine session_id
     - Read per-session context flags
   - **Tier 2 — Extended BOOT (on-demand, L/XL tasks)**: Steps 9-14
     - Pre-task/crash audit — chỉ khi task complexity ≥ L
     - Read deploy guide — chỉ khi deploying
     - Output GoalSpec — chỉ khi L/XL
     - Update registry — chỉ khi L/XL
     - Deep-memory check — chỉ khi `~/.deep-memory/.venv` exists
     - Large-repo init — chỉ khi repo > 50 files
   - **Tier 3 — Optional (user-triggered)**: Steps 15-17
     - Task keyword lookup
     - Project rules check
     - Differential gap-scan
2. Add complexity gate logic:
   ```
   if task_complexity in ["S", "M"]:
       run Tier 1 only
   elif task_complexity in ["L", "XL"]:
       run Tier 1 + Tier 2
   Tier 3 always optional (user can trigger via /scan)
   ```
3. Update `FULL_POWER_PROMPT.md` — step 1 BOOT: "Run Tier 1. If task is L/XL, run Tier 2."

**Files to modify**:
- `.devin/canon/BOOT_PROTOCOL.md` — restructure thành 3 tiers
- `tools/FULL_POWER_PROMPT.md` — update BOOT step reference

**Acceptance criteria**:
- [ ] BOOT_PROTOCOL.md has 3 clearly labeled tiers
- [ ] Tier 1 has exactly 8 steps
- [ ] Tier 2 has exactly 6 steps, each with "when to run" condition
- [ ] Tier 3 has exactly 3 steps, marked optional
- [ ] Complexity gate logic documented
- [ ] FULL_POWER_PROMPT.md references tiered BOOT
- [ ] Tier 1 payload < 20KB (verify: sum of files read in Tier 1)

**Verification steps**:
```powershell
# 1. Check tier structure
$content = Get-Content .devin/canon/BOOT_PROTOCOL.md -Raw
if ($content -notmatch "Tier 1.*Core") { Write-Output "FAIL: no Tier 1" }
if ($content -notmatch "Tier 2.*Extended") { Write-Output "FAIL: no Tier 2" }
if ($content -notmatch "Tier 3.*Optional") { Write-Output "FAIL: no Tier 3" }

# 2. Check FULL_POWER_PROMPT reference
$fpp = Get-Content tools/FULL_POWER_PROMPT.md -Raw
if ($fpp -notmatch "Tier 1") { Write-Output "FAIL: FULL_POWER_PROMPT not updated" }
```

---

### U05: Add `ask` list for sensitive operations

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Security Red Teamer |
| Impact | Human-in-loop cho push/commit/publish |
| Effort | 1 ngày |
| Dependencies | U03 (deny list expansion includes ask list) |
| Risk if not done | Agent push/commit/publish không cần xác nhận |

**Problem**: `"ask": []` — no human-in-loop triggers. Agent có thể push, commit, publish không cần confirm.

**Solution spec**: Covered by U03 — `ask` array populated với 6 patterns.

**Note**: U05 is subset of U03. Complete U03 to satisfy U05.

**Acceptance criteria**: Same as U03 `ask` array criteria.

---

### U06: Add Memory Keeper fallback mechanism

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Architecture Critic |
| Impact | Eliminate single-point-of-failure |
| Effort | 2 ngày |
| Dependencies | None |
| Risk if not done | Session state lost if Memory Keeper worker crashes |

**Problem**: Memory Keeper worker là single-point-of-failure. Nếu crash → session state not written → data loss.

**Solution spec**:
1. Thêm fallback logic trong `post_tool_use.py`:
   ```python
   def _fallback_state_write(session_id, root, state_update):
       """Fallback: write state directly if Memory Keeper unavailable.
       
       Called when loop_memory_sync.py fails or times out.
       Writes minimal state: last_tool, timestamp, status.
       """
       state_path = os.path.join(root, ".devin", "session_state", f"{session_id}.json")
       try:
           with ahd_session.file_lock(state_path, timeout=5):
               existing = ahd_session.read_json(state_path)
               existing.update(state_update)
               existing["fallback_write"] = True
               existing["fallback_timestamp"] = datetime.now().isoformat()
               ahd_session.write_json(state_path, existing)
       except Exception:
           pass  # last resort — can't do more
   ```
2. Thêm health check trong `loop_memory_sync.py`:
   ```python
   def health_check():
       """Check if Memory Keeper pipeline is healthy."""
       try:
           # Test write/read cycle
           test_path = os.path.join(root, ".devin", "tmp", "mk_health.test")
           with open(test_path, 'w') as f:
               f.write("ok")
           os.remove(test_path)
           return True
       except:
           return False
   ```
3. Thêm `--fallback` flag cho `loop_memory_sync.py` — khi called với `--fallback`, chỉ write minimal state.

**Files to modify**:
- `.devin/hooks/post_tool_use.py` — add `_fallback_state_write()`
- `.devin/scripts/loop_memory_sync.py` — add `health_check()`, `--fallback` flag

**Acceptance criteria**:
- [ ] `_fallback_state_write()` function exists in `post_tool_use.py`
- [ ] `health_check()` function exists in `loop_memory_sync.py`
- [ ] `loop_memory_sync.py --fallback` flag works (writes minimal state)
- [ ] Fallback writes `fallback_write: true` flag in state JSON
- [ ] If `loop_memory_sync.py` fails, `post_tool_use.py` calls fallback

**Verification steps**:
```powershell
# 1. Check functions exist
Select-String -Path .devin/hooks/post_tool_use.py -Pattern "_fallback_state_write" | Measure-Object  # >= 1
Select-String -Path .devin/scripts/loop_memory_sync.py -Pattern "health_check" | Measure-Object  # >= 1

# 2. Test fallback flag
python .devin/scripts/loop_memory_sync.py --fallback --session-id test-fallback  # should not error
```

---

### U07: Add disaster recovery flow

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Flow Analyst |
| Impact | Recovery từ workspace corruption |
| Effort | 2 ngày |
| Dependencies | None |
| Risk if not done | Không thể phục hồi nếu .devin/ corrupt |

**Problem**: Không có flow backup/restore workspace. Nếu `.devin/canon/` corrupt → harness không BOOT được.

**Solution spec**:
1. Tạo `tools/backup-workspace.ps1`:
   - Snapshot `.devin/`, `.agents/`, `HLK/`, `AGENTS.md`, `CLAUDE.md`, `REPOS.md`
   - Tạo zip với timestamp: `backups/harness-backup-YYYYMMDD-HHMMSS.zip`
   - Compute SHA256 hash, lưu trong `backups/hashes.txt`
   - Giữ max 10 backups (rotate old)
2. Tạo `tools/restore-workspace.ps1`:
   - Param: `-BackupPath <path>` hoặc `-Latest` (restore backup mới nhất)
   - Verify SHA256 hash trước khi restore
   - Restore files, không overwrite user source code (`src/`, `tests/`)
   - Post-restore: run `verify-workspace.ps1`

**Files to create**:
- `tools/backup-workspace.ps1`
- `tools/restore-workspace.ps1`

**Acceptance criteria**:
- [ ] `backup-workspace.ps1` creates zip in `backups/` directory
- [ ] SHA256 hash computed and stored in `backups/hashes.txt`
- [ ] Max 10 backups retained (oldest rotated)
- [ ] `restore-workspace.ps1 -Latest` restores most recent backup
- [ ] Restore verifies SHA256 before extracting
- [ ] Restore does NOT overwrite `src/`, `tests/`
- [ ] Post-restore runs `verify-workspace.ps1`
- [ ] `backups/` added to `.gitignore`

**Verification steps**:
```powershell
# 1. Create backup
powershell -File tools/backup-workspace.ps1
Test-Path "backups/harness-backup-*.zip"  # must be true

# 2. Verify hash
Test-Path "backups/hashes.txt"  # must be true

# 3. Test restore (to temp dir first)
powershell -File tools/restore-workspace.ps1 -Latest -DryRun  # if DryRun supported
```

---

### U08: Add rollback deploy flow

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Flow Analyst |
| Impact | Recovery từ bad deploy |
| Effort | 1 ngày |
| Dependencies | U07 (backup-workspace.ps1) |
| Risk if not done | Bad deploy breaks workspace, no undo |

**Problem**: `deploy-template.ps1` overwrites config, no rollback path. Nếu deploy hỏng → manual surgery.

**Solution spec**:
1. Thêm pre-deploy snapshot trong `deploy-template.ps1`:
   - Before any file copy, create git commit: `chore: pre-deploy snapshot`
   - If git not initialized, create file snapshot in `backups/pre-deploy-<timestamp>/`
2. Thêm `tools/rollback-deploy.ps1`:
   - Param: `-ToPreDeploy` (rollback to pre-deploy snapshot)
   - `git reset --hard HEAD~1` (if git commit approach)
   - Or restore from `backups/pre-deploy-<timestamp>/`
   - Post-rollback: run `verify-workspace.ps1`
3. Thêm post-deploy verification trong `deploy-template.ps1`:
   - After deploy, run `verify-workspace.ps1`
   - If verify fails → auto-trigger rollback + warn user

**Files to modify/create**:
- `tools/deploy-template.ps1` — add pre-deploy snapshot + post-deploy verify
- `tools/rollback-deploy.ps1` — new file

**Acceptance criteria**:
- [ ] `deploy-template.ps1` creates pre-deploy snapshot before file copy
- [ ] `rollback-deploy.ps1` exists and can restore pre-deploy state
- [ ] Post-deploy runs `verify-workspace.ps1` automatically
- [ ] If verify fails, rollback is triggered automatically
- [ ] Rollback runs `verify-workspace.ps1` after restore

**Verification steps**:
```powershell
# 1. Check rollback script exists
Test-Path tools/rollback-deploy.ps1  # must be true

# 2. Check deploy-template has snapshot logic
Select-String -Path tools/deploy-template.ps1 -Pattern "pre-deploy" | Measure-Object  # >= 1
Select-String -Path tools/deploy-template.ps1 -Pattern "verify-workspace" | Measure-Object  # >= 1
```

---

### U09: Fix placeholder injection in `deploy-template.ps1`

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Security Red Teamer |
| Impact | Close config poisoning hole |
| Effort | 1 ngày |
| Dependencies | None |
| Risk if not done | Malicious path → config injection during deploy |

**Problem**: String replacement không validate workspaceRoot. Path traversal trong zip extract.

**Solution spec**:
1. Validate `workspaceRoot` before replacement:
   ```powershell
   # Reject paths with traversal
   if ($workspaceRoot -match '\.\.') {
       Write-Error "WORKSPACE_ROOT contains path traversal: $workspaceRoot"
       exit 1
   }
   # Resolve to absolute path
   $workspaceRoot = [System.IO.Path]::GetFullPath($workspaceRoot)
   ```
2. Safe zip extraction with entry path validation:
   ```powershell
   Add-Type -AssemblyName System.IO.Compression.FileSystem
   $zip = [System.IO.Compression.ZipFile]::OpenRead($TemplatePath)
   foreach ($entry in $zip.Entries) {
       $targetPath = [System.IO.Path]::GetFullPath(
           [System.IO.Path]::Combine($tempExtract, $entry.FullName)
       )
       $tempExtractFull = [System.IO.Path]::GetFullPath($tempExtract)
       if (-not $targetPath.StartsWith($tempExtractFull)) {
           Write-Error "Path traversal detected in zip entry: $($entry.FullName)"
           $zip.Dispose()
           exit 1
       }
   }
   $zip.Dispose()
   [System.IO.Compression.ZipFile]::ExtractToDirectory($TemplatePath, $tempExtract)
   ```
3. Validate all placeholders resolved after replacement:
   ```powershell
   # After all replacements, check for unresolved placeholders
   $unresolved = Select-String -Path $configFiles -Pattern '\{\{.*\}\}'
   if ($unresolved) {
       Write-Error "Unresolved placeholders found: $($unresolved.Count)"
       $unresolved | ForEach-Object { Write-Error "  $($_.Path):$($_.LineNumber): $($_.Line)" }
       exit 1
   }
   ```

**Files to modify**:
- `tools/deploy-template.ps1` — add validation logic

**Acceptance criteria**:
- [ ] Path with `..` rejected with error
- [ ] Zip entries with `..` rejected with error
- [ ] Unresolved placeholders cause deploy to fail
- [ ] Valid paths still work (no false positive)

**Verification steps**:
```powershell
# 1. Check validation exists
Select-String -Path tools/deploy-template.ps1 -Pattern "traversal" | Measure-Object  # >= 2
Select-String -Path tools/deploy-template.ps1 -Pattern "GetFullPath" | Measure-Object  # >= 1
Select-String -Path tools/deploy-template.ps1 -Pattern "unresolved" -CaseSensitive | Measure-Object  # >= 1
```

---

### U10: Enforce cross-family verification for L/XL tasks

| Field | Value |
|-------|-------|
| Priority | P0 |
| Expert | Quality Auditor |
| Impact | Address self-preference bias (arXiv 2306.05685) |
| Effort | 3 ngày |
| Dependencies | U04 (BOOT tiered — need complexity gate) |
| Risk if not done | Same-model verification → self-preference bias |

**Problem**: VERIFICATION_PROTOCOL.md recommends cross-family debate but doesn't enforce. Same-model "fresh context" only removes conversation history, not inherent biases.

**Solution spec**:
1. Tạo `.devin/hooks/pre_verification.py` (new hook):
   - Runs before verification step
   - Checks task complexity (from GoalSpec)
   - If L/XL → check if verifier model family ≠ producer model family
   - If same family → warn (not block, since cross-family may not always be available)
2. Update `VERIFICATION_PROTOCOL.md`:
   - Add section: "Cross-family enforcement"
   - L/XL tasks: MUST attempt cross-family verification
   - If cross-family unavailable: document in report, lower confidence to "medium"
3. Update `FULL_POWER_PROMPT.md` step 8 (VERIFY):
   - Add: "For L/XL tasks, dispatch verifier on different model family. If unavailable, note in report."

**Files to create/modify**:
- `.devin/hooks/pre_verification.py` — new
- `.devin/canon/VERIFICATION_PROTOCOL.md` — add cross-family section
- `tools/FULL_POWER_PROMPT.md` — update step 8

**Acceptance criteria**:
- [ ] `pre_verification.py` exists and checks task complexity
- [ ] VERIFICATION_PROTOCOL.md has "Cross-family enforcement" section
- [ ] FULL_POWER_PROMPT.md step 8 mentions cross-family for L/XL
- [ ] Hook outputs warning (not block) when same-family detected

**Verification steps**:
```powershell
Test-Path .devin/hooks/pre_verification.py  # must be true
Select-String -Path .devin/canon/VERIFICATION_PROTOCOL.md -Pattern "cross-family" | Measure-Object  # >= 2
Select-String -Path tools/FULL_POWER_PROMPT.md -Pattern "cross-family" | Measure-Object  # >= 1
```

---

## Phase 1 — High (P1) — 15 upgrades — Target: 1 month

### U11: Merge lightning + glm SKILL.md

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Token Economist |
| Impact | -2.5K tokens/skill invoke |
| Effort | 1 ngày |
| Dependencies | None |

**Problem**: `lightning` và `glm` SKILL.md 95% overlap — chỉ khác model name.

**Solution spec**:
1. Tạo `.devin/skills/executor/SKILL.md` — merged skill với `{{MODEL}}` parameter
2. Update `lightning` và `glm` skills thành thin wrappers reference executor skill
3. Update AGENTS.md table

**Files to modify**:
- `.devin/skills/executor/SKILL.md` — new (merged content)
- `.devin/skills/lightning/SKILL.md` — thin wrapper
- `.devin/skills/glm/SKILL.md` — thin wrapper

**Acceptance criteria**:
- [ ] `executor/SKILL.md` exists with `{{MODEL}}` parameter
- [ ] `lightning/SKILL.md` < 500 bytes (thin wrapper)
- [ ] `glm/SKILL.md` < 500 bytes (thin wrapper)
- [ ] Both wrappers reference `executor/SKILL.md`

---

### U12: Split LOOP_PROTOCOL → load only needed section

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Token Economist |
| Impact | -5-8K tokens/BOOT |
| Effort | 2 ngày |
| Dependencies | U01 |

**Problem**: `LOOP_PROTOCOL.md` 734 lines (10K tokens) — load toàn bộ dù chỉ cần 1 loop type.

**Solution spec**:
1. Split thành:
   - `LOOP_PROTOCOL.md` — core (overview + stop conditions, ~100 lines)
   - `LOOP_TURN_BASED.md` — turn-based loop detail
   - `LOOP_GOAL_BASED.md` — goal-based loop detail
   - `LOOP_TIME_BASED.md` — time-based loop detail
   - `LOOP_PROACTIVE.md` — proactive loop detail
2. BOOT chỉ load core, sub-protocols on-demand

**Acceptance criteria**:
- [ ] `LOOP_PROTOCOL.md` < 150 lines
- [ ] 4 sub-protocol files exist
- [ ] Core references sub-protocols with "load on-demand" note

---

### U13: Inline `loop_memory_sync` + `pre_task_audit` (no subprocess)

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Performance Engineer |
| Impact | -400-1500ms/BOOT |
| Effort | 3 ngày |
| Dependencies | None |

**Problem**: BOOT steps 9, 12 gọi Python scripts via subprocess → 400-1500ms overhead.

**Solution spec**:
1. Refactor `loop_memory_sync.py` và `pre_task_audit.py` thành importable modules
2. Thêm `run_inline()` function trong mỗi script
3. BOOT protocol: import và call directly thay vì subprocess

**Acceptance criteria**:
- [ ] Both scripts have `run_inline()` function
- [ ] BOOT_PROTOCOL.md references inline call, not subprocess
- [ ] No `subprocess.run` or `subprocess.call` in BOOT steps 9, 12

---

### U14: Per-session lock thay vì single repo lock

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Performance Engineer |
| Impact | -0-10s concurrent |
| Effort | 2 ngày |
| Dependencies | None |

**Problem**: Tất cả processes dùng cùng lock file `.devin/tmp/ahd_session.lock` → contention.

**Solution spec**:
1. Change lock file to per-session: `.devin/tmp/ahd_session.<session_id>.lock`
2. Update `ahd_session.py` `file_lock()` function
3. Registry write vẫn dùng repo-level lock (chỉ registry cần global)

**Acceptance criteria**:
- [ ] Lock file path includes session_id
- [ ] Registry write uses separate repo-level lock
- [ ] `ahd_session.py` updated

---

### U15: Reduce hook timeout 10s → 3s

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Performance Engineer |
| Impact | -0-7s on error |
| Effort | 1 ngày |
| Dependencies | None |

**Problem**: Hook timeout 10s quá generous — thực tế chỉ cần 200-500ms.

**Solution spec**:
1. Update `config.json` hook timeout: 10s → 3s cho pre_tool_use, 5s cho post_tool_use
2. Add timeout logic trong hooks (signal.alarm on Unix, threading.Timer on Windows)

**Acceptance criteria**:
- [ ] `config.json` pre_tool_use timeout = 3s
- [ ] `config.json` post_tool_use timeout = 5s
- [ ] Hooks have internal timeout logic

---

### U16: Add deadlock detection cho parallel dispatch

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Architecture Critic |
| Impact | Safe parallelism |
| Effort | 3 ngày |
| Dependencies | None |

**Problem**: Parallel dispatch không có deadlock detection. Worker A cần output Worker B → hang.

**Solution spec**:
1. Update `plan_dispatch.py`:
   - Build dependency graph before dispatch
   - Topological sort to serialize dependent tasks
   - Circular dependency detection → escalate to human
2. Output: `dispatch_order` array, `parallel_groups` array

**Acceptance criteria**:
- [ ] `plan_dispatch.py` builds dependency graph
- [ ] Topological sort implemented
- [ ] Circular dependency detected and reported
- [ ] Output includes `dispatch_order` and `parallel_groups`

---

### U17: Add cost cap cho model escalation

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Architecture Critic |
| Impact | Prevent budget overrun |
| Effort | 2 ngày |
| Dependencies | None |

**Problem**: Model escalation cheap→mid→high không có cost cap.

**Solution spec**:
1. Add `cost_cap` field trong session_state: max $ per task
2. Track cumulative cost trong session_state
3. If cost > cap → stop escalation, ask human

**Acceptance criteria**:
- [ ] `session_state` has `cost_cap` and `cumulative_cost` fields
- [ ] Escalation checks cost before escalating
- [ ] Human notified when cost cap hit

---

### U18: Merge backend_architect + software_architect personas

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Architecture Critic |
| Impact | Eliminate persona confusion |
| Effort | 1 ngày |
| Dependencies | None |

**Problem**: backend_architect và software_architect overlap ở API design, architecture decisions.

**Solution spec**:
1. Merge thành `architect.md` với sub-specialties section
2. Update DISPATCH_TEMPLATES.md references
3. Remove old persona files

**Acceptance criteria**:
- [ ] `architect.md` exists with merged content
- [ ] `backend_architect.md` and `software_architect.md` removed
- [ ] DISPATCH_TEMPLATES.md references `architect` not old names

---

### U19: Localize comment_checker for Vietnamese

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Quality Auditor |
| Impact | Match workspace language requirements |
| Effort | 1 ngày |
| Dependencies | None |

**Problem**: comment_checker chỉ cover English patterns. Workspace yêu cầu Vietnamese comments.

**Solution spec**:
1. Add Vietnamese slop patterns to `comment_checker.md`:
   - "Bước 1:", "Tiếp theo,", "Lưu ý:", "Tóm lại,"
   - "gán x bằng", "tăng biến đếm" (restating code in Vietnamese)
2. Add Vietnamese section alongside English patterns

**Acceptance criteria**:
- [ ] `comment_checker.md` has Vietnamese patterns section
- [ ] At least 5 Vietnamese slop patterns added
- [ ] At least 3 Vietnamese restating-code patterns added

---

### U20: Add SHA discipline automation in `post_tool_use.py`

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Quality Auditor |
| Impact | Prevent stale evidence trap |
| Effort | 2 ngày |
| Dependencies | None |

**Problem**: SHA discipline relies on agent discipline, not mechanical enforcement.

**Solution spec**:
1. `post_tool_use.py` tracks file SHA + last verification timestamp
2. On write, auto-invalidate verification status for that file
3. Add `verify_status` field to session_state with SHA fingerprint

**Acceptance criteria**:
- [ ] `post_tool_use.py` computes SHA on file write
- [ ] `verify_status` field in session_state
- [ ] Write invalidates previous verification status

---

### U21: Fix BOOT race condition — file locking cho registry

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Flow Analyst |
| Impact | Prevent data loss on concurrent start |
| Effort | 2 ngày |
| Dependencies | U14 (per-session lock) |

**Problem**: Two sessions start simultaneously → both create registry → second overwrites first.

**Solution spec**:
1. Add file lock during registry creation (BOOT step 2)
2. Retry with backoff if lock held
3. Use `ahd_session.file_lock()` with repo-level lock for registry

**Acceptance criteria**:
- [ ] BOOT step 2 uses file lock
- [ ] Retry logic with backoff implemented
- [ ] BOOT_PROTOCOL.md documents locking

---

### U22: Add session orphan cleanup script

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Flow Analyst |
| Impact | Prevent disk bloat |
| Effort | 1 ngày |
| Dependencies | None |

**Problem**: Orphaned `.devin/session_state/*.json` files accumulate.

**Solution spec**:
1. Create `tools/cleanup-orphan-sessions.ps1`:
   - Scan `.devin/session_state/`
   - Check against `.devin/loop_state.md` registry
   - Delete orphans > 7 days old
   - Report what was cleaned

**Acceptance criteria**:
- [ ] `cleanup-orphan-sessions.ps1` exists
- [ ] Scans session_state directory
- [ ] Checks against registry
- [ ] Deletes orphans > 7 days old
- [ ] Outputs cleanup report

---

### U23: Add multi-project batch deploy

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Flow Analyst |
| Impact | Scale deployment |
| Effort | 2 ngày |
| Dependencies | U08 (rollback deploy) |

**Problem**: `init-new-project.ps1` handles single project only.

**Solution spec**:
1. Add `-TargetList` parameter to `init-new-project.ps1`
2. Loop through projects, deploy to each
3. Aggregate verification results

**Acceptance criteria**:
- [ ] `-TargetList` parameter accepts array of paths
- [ ] Deploys to each project in list
- [ ] Aggregated verification report output

---

### U24: Replace hardcoded paths với environment variables

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Security Red Teamer + Architecture Critic |
| Impact | Portability |
| Effort | 2 ngày |
| Dependencies | None |

**Problem**: `config.json` has `C:\Users\thant\...` hardcoded.

**Solution spec**:
1. Replace with `%APPDATA%`, `%USERPROFILE%`, `%NVM_HOME%` etc.
2. Resolve at runtime in hooks
3. Update `deploy-template.ps1` placeholder resolution

**Acceptance criteria**:
- [ ] No hardcoded `C:\Users\thant` in config.json
- [ ] Environment variables used for user-specific paths
- [ ] Hooks resolve env vars at runtime

---

### U25: Nuwa ROI measurement

| Field | Value |
|-------|-------|
| Priority | P1 |
| Expert | Quality Auditor |
| Impact | Justify cognitive verification cost |
| Effort | 2 ngày |
| Dependencies | None |

**Problem**: No ROI measurement for Nuwa cognitive verification.

**Solution spec**:
1. Track in session_state: `nuwa_runs`, `nuwa_bugs_caught`, `nuwa_token_cost`
2. Compare: Nuwa-audited tasks vs standard-audited tasks
3. If ROI < threshold → reduce Nuwa to high-stakes only

**Acceptance criteria**:
- [ ] Session_state tracks Nuwa metrics
- [ ] Comparison logic documented
- [ ] Threshold defined (e.g., bugs caught per 10K tokens)

---

## Phase 2 — Medium (P2) — 15 upgrades — Target: 3 months

### U26: Via negativa — remove 40% complexity

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Nuwa Cognitive Reviewer |
| Impact | -40% system complexity |
| Effort | 1 tuần |
| Dependencies | U01, U04, U11, U12, U18 |

**Problem**: "Lollapalooza effect" — too many components.

**Solution spec**:
1. Remove 4 of 7 personas → keep 3 (architect, code_reviewer, backend merged)
2. Remove 10 of 21 skills → keep 11 core
3. Remove deep-memory (chroma-hybrid-search) — optional, adds complexity
4. Remove 10 of 15 warning signals → keep top 5
5. Remove Loop Readiness Score rubric → simple binary check
6. Remove RIA++ requirement for non-critical concepts

**Acceptance criteria**:
- [ ] Persona count ≤ 3
- [ ] Skill count ≤ 11
- [ ] Deep-memory removed
- [ ] Warning signals ≤ 5
- [ ] Loop Readiness Score replaced with binary check
- [ ] `verify-workspace.ps1` updated and still passes

---

### U27: Implement L0-L4 permission taxonomy in config.json

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Security Red Teamer |
| Impact | Graded enforcement |
| Effort | 3 ngày |
| Dependencies | U03 |

**Solution spec**:
1. Create tool registry with tier classification
2. L0-L1 → `allow`, L2 → `allow` with logging, L3 → `ask`, L4 → `deny`
3. Map existing tools to tiers

**Acceptance criteria**:
- [ ] Tool registry file exists (`.devin/tool_registry.json`)
- [ ] All tools classified L0-L4
- [ ] config.json permissions map to tiers

---

### U28: Add risk contract enforcement

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Security Red Teamer |
| Impact | Pre-commit validation |
| Effort | 3 ngày |
| Dependencies | U27 |

**Solution spec**:
1. Create `.devin/risk_contract.json`
2. Pre-commit hook validates risk contracts
3. Integrate with PreToolUse for critical file modifications

**Acceptance criteria**:
- [ ] `risk_contract.json` exists
- [ ] Pre-commit hook validates contracts
- [ ] PreToolUse integration for critical files

---

### U29: Expand secret patterns in sanitizer

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Security Red Teamer |
| Impact | Cover AWS/JWT/OAuth |
| Effort | 1 ngày |
| Dependencies | None |

**Solution spec**:
1. Add to `HLK/security/sanitizer.js`:
   - AWS: `AKIA[0-9A-Z]{16}`
   - JWT (no eyJ): `[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`
   - OAuth: `Bearer [A-Za-z0-9._-]+`
   - DB connection: `[a-z]+://[^:]+:[^@]+@[^/]+`

**Acceptance criteria**:
- [ ] 4 new pattern categories added
- [ ] Patterns tested against sample secrets

---

### U30: Add slop pattern versioning + update mechanism

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Quality Auditor |
| Impact | Keep slop detection current |
| Effort | 1 ngày |
| Dependencies | None |

**Solution spec**:
1. Add `version` and `last_updated` to slop-detector.md frontmatter
2. Create `.devin/skills/assets/slop-patterns-updates.md`
3. Quarterly review process documented

**Acceptance criteria**:
- [ ] Version field in slop-detector.md
- [ ] Update tracking file exists
- [ | Quarterly review documented

---

### U31: Add severity grading to slop detector

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Quality Auditor |
| Impact | Reduce over-polishing |
| Effort | 1 ngày |
| Dependencies | U30 |

**Solution spec**:
1. Classify: CRITICAL (meaning distortion), HIGH (hedge words), MEDIUM (filler), LOW (style)
2. CRITICAL → must fix; LOW → optional

**Acceptance criteria**:
- [ ] 4 severity levels defined
- [ ] Each slop pattern tagged with severity

---

### U32: Add non-code output verification

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Quality Auditor |
| Impact | Expand verification coverage |
| Effort | 2 ngày |
| Dependencies | None |

**Solution spec**:
1. Extend VERIFICATION_PROTOCOL.md table with: DB schema, API contracts, IaC, ML artifacts
2. Define verification method for each

**Acceptance criteria**:
- [ ] 4 new output types in verification table
- [ ] Verification method defined for each

---

### U33: Implement partial completion verification

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Quality Auditor |
| Impact | Incremental value delivery |
| Effort | 2 ngày |
| Dependencies | None |

**Solution spec**:
1. Add "PARTIAL" verdict to verification report
2. Define criteria: "N% of AC met, remaining M blocked by dependency X"

**Acceptance criteria**:
- [ ] PARTIAL verdict defined in VERIFICATION_PROTOCOL.md
- [ ] Criteria documented

---

### U34: Relax memory caps — make configurable

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Architecture Critic |
| Impact | Fit diverse project sizes |
| Effort | 1 ngày |
| Dependencies | None |

**Solution spec**:
1. Add `memory_config.json` with configurable caps
2. Default: 3KB/8KB, but allow override
3. Warning when approaching cap, not hard stop

**Acceptance criteria**:
- [ ] `memory_config.json` exists with configurable caps
- [ ] Default values preserved
- [ ] Warning logic implemented

---

### U35: Add recursion guard cho using-skills

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Architecture Critic |
| Impact | Prevent skill invocation deadlock |
| Effort | 1 ngày |
| Dependencies | None |

**Solution spec**:
1. Track invocation depth in session_state
2. Max depth: 3 (meta-skill → skill → sub-skill)
3. Exceed → stop, log error

**Acceptance criteria**:
- [ ] Invocation depth tracked
- [ ] Max depth = 3 enforced
- [ ] Error logged on exceed

---

### U36: Automated config merge với conflict resolution

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Architecture Critic |
| Impact | Scalable config management |
| Effort | 3 ngày |
| Dependencies | None |

**Solution spec**:
1. Create `tools/merge-config.ps1`
2. Auto-merge non-conflicting sections
3. Conflict detection → human prompt

**Acceptance criteria**:
- [ ] `merge-config.ps1` exists
- [ ] Auto-merge works for non-conflicting sections
- [ ] Conflicts prompt human

---

### U37: Add workspace health check flow

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Flow Analyst |
| Impact | Detect silent degradation |
| Effort | 2 ngày |
| Dependencies | None |

**Solution spec**:
1. Create `tools/health-check.ps1`
2. Test: hook execution, MCP server ping, memory write/read
3. Report health score (0-100)

**Acceptance criteria**:
- [ ] `health-check.ps1` exists
- [ ] Tests hooks, MCP, memory
- [ ] Health score output (0-100)

---

### U38: Daemonize aide-memory MCP

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Performance Engineer |
| Impact | -500-2000ms/session |
| Effort | 3 ngày |
| Dependencies | None |

**Solution spec**:
1. Background daemon with IPC
2. Session connects to existing daemon instead of spawning new process

**Acceptance criteria**:
- [ ] Daemon mode documented
- [ ] IPC connection works
- [ ] Startup time < 100ms when daemon running

---

### U39: Cross-platform packaging (Python rewrite)

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Architecture Critic |
| Impact | Linux/macOS support |
| Effort | 1 tuần |
| Dependencies | None |

**Solution spec**:
1. Rewrite `tools/*.ps1` as Python scripts
2. Or add Bash equivalents
3. Test on Linux (WSL or CI)

**Acceptance criteria**:
- [ ] Python or Bash equivalents exist for all 7 tools
- [ ] Tested on non-Windows platform

---

### U40: Add "minimum viable harness" mode

| Field | Value |
|-------|-------|
| Priority | P2 |
| Expert | Nuwa Cognitive Reviewer |
| Impact | Graceful degradation |
| Effort | 3 ngày |
| Dependencies | U04, U26 |

**Problem**: No graceful degradation — if any component fails, whole system fails.

**Solution spec**:
1. Create `.devin/config.minimal.json` — only essential hooks + permissions
2. BOOT detects component failures → switch to minimal mode
3. Minimal mode: only pre_tool_use.py (security) + post_tool_use.py (state)
4. Document: "When to use minimal mode" + "How to exit minimal mode"

**Acceptance criteria**:
- [ ] `config.minimal.json` exists
- [ ] BOOT has minimal mode detection
- [ ] Minimal mode documented
- [ ] Can exit minimal mode (restart with full config)

---

## Phase 3 — Low (P3) — 10 upgrades — As time permits

### U41-U50: Summary table

| ID | Title | Expert | Effort |
|----|-------|--------|--------|
| U41 | Hook integrity verification (SHA256) | Security | 2 ngày |
| U42 | Fail-closed hooks (exit 2 on error) | Security | 1 ngày |
| U43 | Network egress filtering | Security | 2 ngày |
| U44 | Audit log size limits + rotation | Security | 1 ngày |
| U45 | Domain adapter usage tracking | Architecture | 1 ngày |
| U46 | Simplify loop types to 2 | Architecture | 2 ngày |
| U47 | Cache git rev-parse result | Performance | 1 ngày |
| U48 | Batch file I/O operations | Performance | 2 ngày |
| U49 | MCP timeout config | Performance | 1 ngày |
| U50 | Optimize journal rotation | Performance | 1 ngày |

---

## Dependency Graph

```
U01 (AGENTS.md truncate) ──┬── U04 (BOOT lazy-load)
                           └── U12 (Split LOOP_PROTOCOL)

U03 (deny list + ask) ──── U05 (ask list — subset of U03)
                         └── U27 (L0-L4 taxonomy)

U04 (BOOT lazy-load) ───── U10 (cross-family verification)
                         └── U40 (minimum viable harness)

U07 (backup-workspace) ─── U08 (rollback deploy)

U08 (rollback deploy) ──── U23 (multi-project deploy)

U14 (per-session lock) ─── U21 (BOOT race condition fix)

U18 (merge personas) ──── U26 (via negativa)

U26 (via negativa) ─────── U40 (minimum viable harness)

U30 (slop versioning) ─── U31 (slop severity grading)

U27 (L0-L4 taxonomy) ──── U28 (risk contract enforcement)
```

**Critical path**: U01 → U04 → U10 → (P0 complete)
**Longest chain**: U01 → U04 → U26 → U40 (P2 complete)

---

## Success Metrics

### Target after P0 (2 weeks)

| Metric | Before | After P0 | Target |
|--------|--------|----------|--------|
| Always-on context | 53K tokens (26.6%) | ~12K (6%) | <10% ✅ |
| Security vulnerabilities (critical) | 5 | 0 | 0 ✅ |
| BOOT cold start (S/M) | 2-8s | ~1-2s | <3s ✅ |
| Disaster recovery | Missing | Present | Present ✅ |
| Human-in-loop (ask list) | 0 | 6 | ≥6 ✅ |

### Target after P1 (1 month)

| Metric | After P0 | After P1 | Target |
|--------|----------|----------|--------|
| Per-tool-call overhead | 250-750ms | ~150-400ms | <200ms |
| BOOT latency (L/XL) | 2-8s | ~1-3s | <3s |
| Single points of failure | 5 | 2 | ≤2 |
| Cross-family verification | Not enforced | Enforced (L/XL) | Enforced |

### Target after P2 (3 months)

| Metric | After P1 | After P2 | Target |
|--------|----------|----------|--------|
| Component count | 50+ | ~30 | <30 |
| Feynman simplicity score | 2/10 | 7/10 | >7 |
| Taleb fragility score | 8/10 | 4/10 | <4 |
| Cross-platform | Windows only | Win+Linux | Win+Linux |

### Final target after P3

| Metric | Target |
|--------|--------|
| Overall red team score | 9/10+ |
| All P0-P3 upgrades | Done |
| System complexity | Minimal viable |
| Antifragility | Present |
