#!/usr/bin/env python3
"""
apply_ahd_patch.py — surgical cherry-pick AHD commits từ upstream.

Cách dùng:
    python .devin/scripts/apply_ahd_patch.py --upstream PATH --since DATE --until DATE [--dry-run] [--auto-commit] [--worktree DIR]

Logic:
1. Validate input (SHA, branch, worktree).
2. Guard: không chạy trực tiếp trên main/master trừ khi --force.
3. Tạo feature branch từ main, stash local changes.
4. Liệt kê commit trong khoảng thời gian.
5. Với mỗi commit, lấy diff từng file.
6. Map path và normalize, chặn path traversal.
7. Bỏ qua file protected, Docs/, README.md, hoặc file mới ở thư mục rủi ro.
8. Apply nội dung, normalize text references, verify.
9. Nếu verify fail, rollback targeted theo patched_files.
10. Chỉ commit khi --auto-commit; mặc định in diff summary.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[2]


def _audit_log(event: str, **kwargs: Any) -> None:
    """Ghi security event vào .devin/logs/security_audit.log."""
    log_dir = REPO_ROOT / ".devin" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "security_audit.log"
    entry = {"event": event, **kwargs}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def validate_sha(sha: str) -> bool:
    """SHA phải là hex 7-40 ký tự."""
    return bool(re.fullmatch(r"[0-9a-f]{7,40}", sha))


def validate_worktree_path(path: str, repo_root: Path) -> Path | None:
    """Worktree phải là relative path, không chứa .., nằm trong repo root."""
    if path.startswith(("/", "\\")) or ":" in path[:2]:
        return None
    if ".." in Path(path).parts:
        return None
    resolved = (repo_root / path).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return None
    return resolved


def guard_main_branch(force: bool) -> tuple[bool, str]:
    """Không cho chạy trực tiếp trên main/master trừ khi --force."""
    code, branch, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
    branch = branch.strip()
    if branch in ("main", "master") and not force:
        return False, branch
    return True, branch


def setup_feature_branch() -> str:
    """Tạo feature branch từ main, stash local changes."""
    import time
    branch = f"feat/ahd-update-{int(time.time())}"
    run_cmd(["git", "checkout", "-b", branch], cwd=REPO_ROOT)
    return branch


def setup_worktree(worktree_path: Path) -> Path:
    """Tạo worktree từ main."""
    worktree_path.mkdir(parents=True, exist_ok=True)
    run_cmd(["git", "worktree", "add", str(worktree_path), "main"], cwd=REPO_ROOT)
    return worktree_path


def stash_local_changes() -> bool:
    """Stash local changes chưa commit."""
    code, out, _ = run_cmd(["git", "status", "--short"], cwd=REPO_ROOT)
    if not out.strip():
        return False
    run_cmd(["git", "stash", "push", "-m", "pre-ahd-patch"], cwd=REPO_ROOT)
    return True


def pop_stash() -> None:
    run_cmd(["git", "stash", "pop"], cwd=REPO_ROOT)


# Ánh xạ cấu trúc upstream -> local
PATH_MAP: dict[str, str] = {
    "distill/canon/": ".devin/canon/",
    "distill/skills/": ".devin/skills/",
    "distill/orchestrator/workers/": ".devin/agents/workers/",
    "distill/orchestrator/": ".devin/agents/",
    "distill/agents/": ".devin/agents/",
    "scripts/": ".devin/scripts/",
    "core/assets/runtime/hooks/": ".devin/hooks/",
    "adapters/": ".devin/adapters/",
}

# File/thư mục tuyệt đối không được đụng
PROTECTED_PATTERNS = [
    ".env",
    "*.pem",
    "*.key",
    "secrets/*",
    "credentials/*",
    "HLK/*",
    ".devin/hooks/",
    ".devin/config.json",
    ".devin/mcp_config.json",
    ".devin/canon/BOOT_PROTOCOL.md",
    ".devin/canon/CORE_CANON.md",
    ".devin/canon/REDLINES.md",
    ".devin/AGENTS.md",
    ".devin/AGENTS_full.md",
    ".claude/settings.json",
    ".gitignore",
    ".gitattributes",
]

# Các thư mục upstream chỉ là docs/promo, không deploy
SKIP_UPSTREAM_DIRS = ["Docs/", "README", "promo/", ".github/"]

# Các thư mục không được tạo file mới
RISKY_NEW_DIRS = [".devin/adapters/", ".devin/scripts/", ".devin/tests/"]


def load_tracker() -> dict[str, Any]:
    tracker = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"
    with open(tracker, "r", encoding="utf-8") as f:
        return json.load(f)


def get_protected_files() -> list[str]:
    data = load_tracker()
    for s in data.get("sources", []):
        if s.get("id") == "ahd-main-engine":
            return list(set(s.get("protected_files", []) + PROTECTED_PATTERNS))
    return PROTECTED_PATTERNS


def map_path(rel: str, repo_root: Path = REPO_ROOT) -> str | None:
    """Ánh xạ đường dẫn upstream sang local, chuẩn hóa và chặn path traversal."""
    for up, loc in PATH_MAP.items():
        if rel.startswith(up):
            mapped = loc + rel[len(up):]
            resolved = (repo_root / mapped).resolve()
            try:
                resolved.relative_to(repo_root)
            except ValueError:
                _audit_log("path-traversal-blocked", rel=rel, mapped=str(mapped))
                print(f"[WARN] path traversal blocked: {rel} -> {mapped}")
                return None
            return str(resolved.relative_to(repo_root)).replace("\\", "/")
    if rel == "AGENTS.md":
        resolved = (repo_root / ".devin" / "AGENTS.md").resolve()
        return str(resolved.relative_to(repo_root)).replace("\\", "/")
    return None


def is_protected(path: str, protected: list[str]) -> bool:
    """Kiểm tra path có thuộc protected patterns không, dùng path đã chuẩn hóa."""
    norm = Path(path).as_posix().lower()
    for p in protected:
        pl = p.lower()
        # Hỗ trợ glob cơ bản: *, ?
        if any(c in pl for c in "*?"):
            if _glob_match(norm, pl):
                _audit_log("protected-file-blocked", path=path, pattern=p)
                return True
            continue
        if pl.endswith("/**"):
            prefix = pl[:-3]
            if norm == prefix or norm.startswith(prefix + "/"):
                _audit_log("protected-file-blocked", path=path, pattern=p)
                return True
        elif norm == pl or norm.startswith(pl + "/") or norm.endswith("/" + pl) or "/" + pl in norm:
            _audit_log("protected-file-blocked", path=path, pattern=p)
            return True
    return False


def _glob_match(name: str, pat: str) -> bool:
    """fnmatch đơn giản hỗ trợ * và ?."""
    pat = pat.replace(".", r"\.")
    pat = pat.replace("*", ".*")
    pat = pat.replace("?", ".")
    return bool(re.fullmatch(pat, name))


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120, input_text: str = "") -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, input=input_text)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def get_commits(upstream: Path, since: str, until: str) -> list[tuple[str, str]]:
    cmd = ["git", "-C", str(upstream), "log", f"--since={since}", f"--until={until}", "--oneline", "--reverse"]
    code, out, _ = run_cmd(cmd)
    if code != 0:
        return []
    return [(line[:7], line[8:].strip()) for line in out.splitlines() if line.strip()]


def get_changed_files(upstream: Path, sha: str) -> list[str]:
    cmd = ["git", "-C", str(upstream), "diff-tree", "--no-commit-id", "--name-only", "-r", sha]
    _, out, _ = run_cmd(cmd)
    return [l.strip() for l in out.splitlines() if l.strip()]


def get_file_at_rev(upstream: Path, rev: str, path: str) -> str | None:
    code, out, _ = run_cmd(["git", "-C", str(upstream), "show", f"{rev}:{path}"], timeout=30)
    return out if code == 0 else None


def is_upstream_skip(rel: str) -> bool:
    for d in SKIP_UPSTREAM_DIRS:
        if rel.startswith(d) or rel == d.rstrip("/"):
            return True
    return False


def is_risky_new(target: str) -> bool:
    for d in RISKY_NEW_DIRS:
        if target.startswith(d):
            return True
    return False


def _text_replacements() -> list[tuple[str, str]]:
    """Bảng thay thế text cho normalizer."""
    repl = []
    for up, loc in PATH_MAP.items():
        # Chỉ thay thế text references, không thay code logic
        repl.append((up, loc))
    # Bổ sung các thay thế rõ ràng
    repl.append(("scripts/verify.py", "tools/verify-workspace.ps1"))
    repl.append(("scripts/detect.py", ".devin/scripts/plan_dispatch.py"))
    return repl


def normalize_text_after_merge(paths: list[str]) -> None:
    """Chuẩn hóa text references trong các file vừa patch."""
    repl = _text_replacements()
    for p in paths:
        f = REPO_ROOT / p
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        ext = f.suffix
        if ext == ".md":
            new_text = text
            for old, new in repl:
                # Tránh thay thế bên trong code block
                parts = re.split(r"(```[\s\S]*?```|`[^`]*`)", new_text)
                for i in range(len(parts)):
                    if not parts[i].startswith("`"):
                        parts[i] = parts[i].replace(old, new)
                new_text = "".join(parts)
            if new_text != text:
                f.write_text(new_text, encoding="utf-8")
        elif ext == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            data = _normalize_json(data, repl)
            new_text = json.dumps(data, ensure_ascii=False, indent=2)
            if new_text != text:
                f.write_text(new_text + "\n", encoding="utf-8")
        elif ext == ".py":
            new_text = _normalize_py(text, repl)
            if new_text != text:
                f.write_text(new_text, encoding="utf-8")


def _normalize_json(data: Any, repl: list[tuple[str, str]]) -> Any:
    if isinstance(data, dict):
        return {k: _normalize_json(v, repl) for k, v in data.items()}
    if isinstance(data, list):
        return [_normalize_json(v, repl) for v in data]
    if isinstance(data, str):
        for old, new in repl:
            data = data.replace(old, new)
    return data


def _normalize_py(text: str, repl: list[tuple[str, str]]) -> str:
    """Chỉ thay thế comments/docstrings, không thay tên biến/hàm."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expr, ast.Assign)) and isinstance(getattr(node, "value", None), ast.Constant):
            c = node.value
            if isinstance(c.value, str):
                new_val = c.value
                for old, new in repl:
                    new_val = new_val.replace(old, new)
                if new_val != c.value:
                    # Thay thế trong source đơn giản
                    text = text.replace(c.value, new_val, 1)
    return text


def verify(patched_files: list[str]) -> bool:
    """Verify pipeline: py_compile, import smoke, qa_doc_audit."""
    # py_compile cho .py mới/thay đổi
    py_files = [f for f in patched_files if f.endswith(".py")]
    for pf in py_files:
        f = REPO_ROOT / pf
        if not f.exists():
            continue
        code, out, err = run_cmd([sys.executable, "-m", "py_compile", str(f)], cwd=REPO_ROOT)
        if code != 0:
            print(f"[FAIL] py_compile {pf}: {err or out}")
            return False

    # import smoke test
    code, out, err = run_cmd([sys.executable, "tools/import_smoke_test.py"], cwd=REPO_ROOT)
    if code != 0:
        print(f"[FAIL] import smoke test: {err or out}")
        return False

    # qa_doc_audit
    code, out, err = run_cmd([sys.executable, ".devin/scripts/qa_doc_audit.py"], cwd=REPO_ROOT)
    if code != 0:
        print(f"[FAIL] qa_doc_audit: {err or out}")
        return False
    try:
        report = json.loads(out)
    except json.JSONDecodeError:
        print("[FAIL] qa_doc_audit output not JSON")
        return False
    if report.get("stale_refs"):
        print(f"[FAIL] stale refs found: {report['stale_refs'][:5]}")
        return False

    # workspace verify
    for script in [
        ["pwsh", "tools/verify-workspace.ps1"],
        ["node", "HLK/wrappers/hlk-verify-integrity.js"],
    ]:
        code, out, err = run_cmd(script, cwd=REPO_ROOT, timeout=180)
        if code != 0:
            print(f"[FAIL] {' '.join(script)} exit {code}")
            print(err or out)
            return False
    return True


def commit_changes(sha: str, msg: str, auto_commit: bool) -> bool:
    run_cmd(["git", "add", "-A"], cwd=REPO_ROOT)
    code, out, _ = run_cmd(["git", "diff", "--cached", "--stat"], cwd=REPO_ROOT)
    if not out.strip():
        return True
    if not auto_commit:
        print("[INFO] Staged changes. Run `git commit` manually to approve.")
        print(out)
        return True
    code, out, err = run_cmd([
        "git", "commit", "-m", f"cherry-pick AHD {sha}: {msg}",
        "-m", "Path-mapped from upstream masteryee-labs/Tool.Agent-Harness-Deploy.",
        "-m", "Verified: verify-workspace.ps1 + hlk-verify-integrity.js PASS.",
        "-m", "Generated with [Devin](https://devin.ai)",
        "-m", "Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>",
    ], cwd=REPO_ROOT)
    if code != 0:
        print(f"[FAIL] commit: {err}")
        return False
    return True


def rollback_patched_files(patched_files: list[str]) -> None:
    """Rollback chỉ các file đã patch."""
    if not patched_files:
        return
    cmd = ["git", "checkout", "--"]
    for pf in patched_files:
        target = REPO_ROOT / pf
        if target.exists():
            cmd.append(pf)
    run_cmd(cmd, cwd=REPO_ROOT)
    _audit_log("rollback-executed", files=patched_files)


def merge_3way(local_text: str, base_text: str, remote_text: str, resolve_theirs: bool = False) -> str | None:
    """Chạy git merge-file 3-way, trả nội dung merge hoặc None nếu conflict.
    Nếu resolve_theirs=True, xung đột sẽ được giải quyết theo phía remote (upstream)."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-local") as lf:
        lf.write(local_text)
        local_path = lf.name
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-base") as bf:
        bf.write(base_text)
        base_path = bf.name
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-remote") as rf:
        rf.write(remote_text)
        remote_path = rf.name
    try:
        cmd = ["git", "merge-file", "-p"]
        if resolve_theirs:
            cmd.append("--theirs")
        cmd.extend([local_path, base_path, remote_path])
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if proc.returncode != 0:
            # Có conflict
            return None
        return proc.stdout
    finally:
        for p in [local_path, base_path, remote_path]:
            try:
                Path(p).unlink()
            except OSError:
                pass


def apply_commit(upstream: Path, sha: str, msg: str, protected: list[str], dry_run: bool, auto_commit: bool,
                 allow_partial: bool = False, use_3way: bool = False,
                 resolve_theirs: bool = False, allow_risky_new: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"sha": sha, "msg": msg, "status": "pending", "applied": [], "skipped": [], "error": ""}
    patched_files: list[str] = []

    files = get_changed_files(upstream, sha)
    if not files:
        result["status"] = "skipped"
        return result

    code, parent, _ = run_cmd(["git", "-C", str(upstream), "rev-parse", f"{sha}^"])
    if code != 0:
        result["status"] = "error"
        result["error"] = "cannot resolve parent"
        return result
    parent = parent.strip()

    blocked = []
    for rel in files:
        if is_upstream_skip(rel):
            continue
        mapped = map_path(rel)
        if not mapped:
            blocked.append(f"unmapped:{rel}")
            continue
        if is_protected(mapped, protected):
            blocked.append(f"protected:{mapped}")
            continue
        old_exists = get_file_at_rev(upstream, parent, rel) is not None
        new_exists = get_file_at_rev(upstream, sha, rel) is not None
        if not old_exists and new_exists and is_risky_new(mapped) and not allow_risky_new:
            blocked.append(f"risky-new:{mapped}")

    if blocked and not allow_partial:
        result["status"] = "blocked"
        result["skipped"] = blocked
        return result

    try:
        for rel in files:
            if is_upstream_skip(rel):
                continue
            mapped = map_path(rel)
            if not mapped:
                result["skipped"].append(rel)
                continue
            if is_protected(mapped, protected):
                result["skipped"].append(mapped)
                continue

            old_text = get_file_at_rev(upstream, parent, rel)
            new_text = get_file_at_rev(upstream, sha, rel)
            target = REPO_ROOT / mapped

            if new_text is None:
                result["skipped"].append(f"delete:{mapped}")
                continue

            if old_text is None:
                if target.exists():
                    result["skipped"].append(f"exists:{mapped}")
                    continue
                if is_risky_new(mapped) and not allow_risky_new:
                    result["skipped"].append(f"risky-new:{mapped}")
                    continue
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(new_text, encoding="utf-8")
                result["applied"].append(mapped)
                patched_files.append(mapped)
                continue

            local_text = target.read_text(encoding="utf-8", errors="replace") if target.exists() else None
            if local_text is not None and local_text != old_text:
                if use_3way and old_text is not None and new_text is not None:
                    merged = merge_3way(local_text, old_text, new_text, resolve_theirs)
                    if merged is None:
                        result["skipped"].append(f"3way-conflict:{mapped}")
                        continue
                    if dry_run:
                        result["applied"].append(f"3way:{mapped}")
                        continue
                    target.write_text(merged, encoding="utf-8")
                    result["applied"].append(f"3way:{mapped}")
                    patched_files.append(mapped)
                    continue
                result["skipped"].append(f"diverged:{mapped}")
                continue

            if local_text is None and is_risky_new(mapped) and not allow_risky_new:
                result["skipped"].append(f"risky-new:{mapped}")
                continue

            if dry_run:
                result["applied"].append(mapped)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_text, encoding="utf-8")
            result["applied"].append(mapped)
            patched_files.append(mapped)

        if not result["applied"]:
            result["status"] = "skipped"
            return result

        if dry_run:
            result["status"] = "dry-run"
            return result

        # Normalize text references
        normalize_text_after_merge(patched_files)

        # Verify
        if not verify(patched_files):
            rollback_patched_files(patched_files)
            result["status"] = "verify-failed"
            result["error"] = "verify failed, rolled back"
            return result

        if not commit_changes(sha, msg, auto_commit):
            rollback_patched_files(patched_files)
            result["status"] = "commit-failed"
            result["error"] = "commit failed, rolled back"
            return result

        result["status"] = "applied"
        return result

    except Exception as e:
        rollback_patched_files(patched_files)
        result["status"] = "error"
        result["error"] = f"exception: {e}"
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default="", help="Path to cloned AHD upstream")
    parser.add_argument("--since", default="2026-07-15", help="Start date")
    parser.add_argument("--until", default="2026-08-10", help="End date")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen")
    parser.add_argument("--auto-commit", action="store_true", help="Auto-commit after verify (default: no)")
    parser.add_argument("--worktree", default="", help="Run in a git worktree")
    parser.add_argument("--force", action="store_true", help="Allow running on main/master")
    parser.add_argument("--allow-partial", action="store_true", help="Apply non-protected files even if commit contains protected files")
    parser.add_argument("--3way", dest="use_3way", action="store_true", help="Use 3-way merge for diverged files")
    parser.add_argument("--resolve-theirs", action="store_true", help="Resolve 3-way conflicts by preferring upstream (theirs)")
    parser.add_argument("--allow-risky-new", action="store_true", help="Allow creating new files in adapters/scripts")
    args = parser.parse_args()

    # Guard branch
    ok, branch = guard_main_branch(args.force)
    if not ok:
        print(f"[ERROR] Cannot run on '{branch}'. Use feature branch or --force.")
        return 1

    # Validate upstream/worktree paths
    upstream = Path(args.upstream) if args.upstream else Path(tempfile.gettempdir()) / "ahd-upstream"
    if not upstream.exists():
        print(f"[ERROR] Upstream not found: {upstream}")
        return 1

    worktree: Path | None = None
    if args.worktree:
        wp = validate_worktree_path(args.worktree, REPO_ROOT)
        if not wp:
            print(f"[ERROR] Invalid worktree path: {args.worktree}")
            return 1
        worktree = wp

    original_cwd = REPO_ROOT
    stashed = False
    try:
        if worktree:
            setup_worktree(worktree)
            original_cwd = worktree
        else:
            stashed = stash_local_changes()

        protected = get_protected_files()
        commits = get_commits(upstream, args.since, args.until)
        if not commits:
            print("[INFO] No commits found.")
            return 0

        results: list[dict[str, Any]] = []
        for sha, msg in commits:
            if not validate_sha(sha):
                print(f"[SKIP] Invalid SHA: {sha}")
                continue
            print(f"\n[COMMIT] {sha} {msg}")
            res = apply_commit(
                upstream, sha, msg, protected, args.dry_run, args.auto_commit,
                args.allow_partial, args.use_3way, args.resolve_theirs, args.allow_risky_new
            )
            results.append(res)
            print(f"  status: {res['status']}")
            if res["applied"]:
                print(f"  applied: {res['applied']}")
            if res["skipped"]:
                print(f"  skipped: {res['skipped']}")
            if res["error"]:
                print(f"  error: {res['error']}")

        # Ghi report
        report_path = REPO_ROOT / ".devin" / "metadata" / "AHD_PATCH_REPORT.md"
        lines = ["# AHD Cherry-Pick Report", "", f"Upstream: {upstream}", f"Range: {args.since} .. {args.until}", ""]
        for r in results:
            lines.append(f"## {r['sha']} — {r['msg']}")
            lines.append(f"- **status**: {r['status']}")
            lines.append(f"- **applied**: {', '.join(r['applied']) or 'none'}")
            lines.append(f"- **skipped**: {', '.join(r['skipped']) or 'none'}")
            if r["error"]:
                lines.append(f"- **error**: {r['error']}")
            lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n[OK] Report: {report_path}")
        return 0
    finally:
        if stashed:
            pop_stash()


if __name__ == "__main__":
    sys.exit(main())
