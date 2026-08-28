import type { Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"

/**
 * Harness hook bridge — wires the Devin harness Python hooks (`.devin/hooks/*.py`)
 * into opencode's plugin event surface.
 *
 * Safety contract (hard):
 *  - BEST-EFFORT + FAIL-OPEN: any missing python, missing script, timeout, or exception
 *    is caught and only logged via console.error. It NEVER blocks or delays opencode.
 *  - The Devin `pre_tool_use` guard is invoked in ADVISORY mode only (payload is a
 *    schema-shimmed event, stdout is discarded). It does NOT gate opencode tool execution.
 *  - Fire-and-forget with a short timeout: hook runs do not block the tool-call path (no self-DoS).
 *  - ENABLED BY DEFAULT. Opt-out via OPENCODE_HARNESS_HOOKS=0 (kill switch).
 */
const ROOT = process.env.INIT_CWD ?? process.cwd()
const HOOKS = `${ROOT}/.devin/hooks`

// Bật mặc định; tắt hẳn bằng OPENCODE_HARNESS_HOOKS=0.
const DISABLED = process.env.OPENCODE_HARNESS_HOOKS === "0"
const ENABLED = !DISABLED

const PY_CANDIDATES = [
  process.env.OPENCODE_HARNESS_PYTHON,
  // Windows venv (hợp lệ cho PATH này) trước tiên.
  `${ROOT}/.venv/Scripts/python.exe`,
  `${ROOT}/.venv/bin/python`,
  process.platform === "win32" ? "python" : "python3",
].filter(Boolean) as string[]

interface HookEvent {
  hook: string
  phase: string
  tool?: string
  data?: unknown
  ts: string
}

// Resolve a working python once (cache). Null => hooks are skipped (fail-open).
let resolvedPy: string | null | undefined

function resolvePython(): string | null {
  if (resolvedPy !== undefined) return resolvedPy
  resolvedPy = PY_CANDIDATES.find((p) => existsSync(p)) ?? null
  return resolvedPy
}

async function runHook(
  hook: string,
  payload: unknown,
  args: string[] = []
): Promise<void> {
  if (!ENABLED) return
  const py = resolvePython()
  if (!py) {
    console.error(`[harness-hook:${hook}] no python found — skipped`)
    return
  }
  const script = `${HOOKS}/${hook}.py`
  try {
    const { execFile } = await import("node:child_process")
    const { promisify } = await import("node:util")
    const pexec = promisify(execFile)
    const input = JSON.stringify(payload ?? {})
    // Fire-and-forget, short timeout, never block the caller.
    pexec(
      py,
      [script, ...args],
      {
        input,
        maxBuffer: 256_000,
        timeout: 1_500,
        env: { ...process.env, OPENCODE_HARNESS: "1", AHD_ROOT: ROOT },
        cwd: ROOT,
      }
    ).catch((e: unknown) => {
      const msg = e instanceof Error ? e.message : String(e)
      console.error(`[harness-hook:${hook}] skipped (best-effort): ${msg.slice(0, 300)}`)
    })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    console.error(`[harness-hook:${hook}] skipped (best-effort): ${msg.slice(0, 300)}`)
  }
}

/** Nén terminal output cho các lệnh dài (git diff/status, ls) — migrated từ harness-plugin.js cũ. */
function compressTerminalOutput(raw: string, command: string): string {
  if (!raw || !command) return raw
  try {
    if (command.startsWith("git diff")) return compressGitDiff(raw)
    if (command.startsWith("git status")) return compressGitStatus(raw)
    if (command.match(/^ls\s+.*-[lL]/)) return compressLs(raw)
    return raw
  } catch {
    // Fail-open: không bao giờ làm vỡ output tool.
    return raw
  }
}

function compressGitDiff(output: string): string {
  const lines = output.split("\n")
  const result: string[] = []
  let unchanged = 0
  for (const line of lines) {
    if (line.startsWith(" ") && !line.startsWith("+++") && !line.startsWith("---") && !line.startsWith("@@")) {
      unchanged++
      if (unchanged === 1) result.push("  [... unchanged context collapsed ...]")
    } else {
      if (unchanged > 1) result.push(`  [... ${unchanged - 1} more unchanged lines ...]`)
      unchanged = 0
      result.push(line)
    }
  }
  if (unchanged > 1) result.push(`  [... ${unchanged - 1} more unchanged lines ...]`)
  return result.join("\n")
}

function compressGitStatus(output: string): string {
  const lines = output.split("\n")
  let staged = 0
  let unstaged = 0
  let untracked = 0
  for (const line of lines) {
    const stripped = line.trimStart()
    if (/^[MADRC]/.test(stripped) && !/^[\s\t]/.test(line)) staged++
    else if (/^[MADRC]/.test(stripped) && /^[\s\t]/.test(line)) unstaged++
    else if (stripped.startsWith("??")) untracked++
  }
  const parts: string[] = []
  if (staged) parts.push(`${staged} staged`)
  if (unstaged) parts.push(`${unstaged} unstaged`)
  if (untracked) parts.push(`${untracked} untracked`)
  return parts.length ? `[git status: ${parts.join(", ")}]` : "[git status: clean]"
}

function compressLs(output: string): string {
  return output
    .split("\n")
    .map((l) => {
      const parts = l.split(/\s+/)
      return parts.length >= 9 ? parts.slice(8).join(" ") : l
    })
    .join("\n")
}

export default (): Plugin => {
  // OFF by default: return an empty plugin so opencode is untouched unless opted in.
  if (!ENABLED) return {}

  return {
    "tool.execute.before": async (input) => {
      const tool = (input?.tool as string) ?? (input as any)?.toolName ?? "unknown"
      const ev: HookEvent = {
        hook: "pre_tool_use",
        phase: "before",
        tool,
        data: { args: (input as any)?.args ?? {} },
        ts: new Date().toISOString(),
      }
      await runHook("pre_tool_use", ev)
    },
    "tool.execute.after": async (input, output) => {
      const tool = (input?.tool as string) ?? (input as any)?.toolName ?? "unknown"
      // Nén terminal output cho git/ls (fail-open, không block).
      try {
        if (
          tool === "bash" &&
          output?.args?.command &&
          typeof (output?.output ?? "").toString === "function"
        ) {
          const cmd = String(output.args.command)
          const raw = output.output == null ? "" : output.output.toString()
          const compressed = compressTerminalOutput(raw, cmd)
          if (compressed !== raw && output) {
            ;(output as any).output = compressed
          }
        }
      } catch {
        /* fail-open */
      }
      await runHook("post_tool_use", {
        hook: "post_tool_use",
        phase: "after",
        tool,
        ts: new Date().toISOString(),
      })
    },
    event: async (ev) => {
      const name = (ev as any)?.name ?? (ev as any)?.type ?? ""
      const s = String(name).toLowerCase()
      try {
        if (s.includes("session_start") || s === "session.start") {
          await runHook("session_start", { session: ev })
        } else if (s.includes("session_end") || s === "session.idle" || s === "session.stop") {
          await runHook("session_end", { session: ev })
        } else if (s.includes("message") || s === "message.created") {
          await runHook("user_prompt_submit", { message: ev })
        }
      } catch {
        /* fail-open */
      }
    },
  }
}
