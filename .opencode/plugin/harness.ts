import type { Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"

/**
 * Harness hook bridge — wires the Devin harness Python hooks (`.devin/hooks/*.py`)
 * into opencode's plugin event surface, OPT-IN and NON-INTERFERING.
 *
 * Safety contract (hard):
 *  - OFF BY DEFAULT. The bridge does NOTHING unless `OPENCODE_HARNESS_HOOKS=1`.
 *    Default zero side effects -> cannot corrupt Devin `.devin/` state or break other providers.
 *  - BEST-EFFORT + FAIL-OPEN: any missing python, missing script, timeout, or exception is caught
 *    and only logged via console.error. It NEVER blocks or delays opencode.
 *  - The Devin `pre_tool_use` guard is invoked in ADVISORY mode only (payload is a schema-shimmed
 *    event, stdout is discarded). It does NOT gate opencode tool execution.
 *  - Fire-and-forget with a short timeout: hook runs do not block the tool-call path (no self-DoS).
 */
const ROOT = process.env.INIT_CWD ?? process.cwd()
const HOOKS = `${ROOT}/.devin/hooks`
const ENABLED = process.env.OPENCODE_HARNESS_HOOKS === "1"

const PY_CANDIDATES = [
  process.env.OPENCODE_HARNESS_PYTHON,
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

async function runHook(hook: string, payload: unknown): Promise<void> {
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
    pexec(py, [script], {
      input,
      maxBuffer: 256_000,
      timeout: 1_500,
      env: { ...process.env, OPENCODE_HARNESS: "1", AHD_ROOT: ROOT },
      cwd: ROOT,
    }).catch((e: unknown) => {
      const msg = e instanceof Error ? e.message : String(e)
      console.error(`[harness-hook:${hook}] skipped (best-effort): ${msg.slice(0, 300)}`)
    })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    console.error(`[harness-hook:${hook}] skipped (best-effort): ${msg.slice(0, 300)}`)
  }
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
    "tool.execute.after": async (input) => {
      const tool = (input?.tool as string) ?? (input as any)?.toolName ?? "unknown"
      await runHook("post_tool_use", {
        hook: "post_tool_use",
        phase: "after",
        tool,
        ts: new Date().toISOString(),
      } satisfies HookEvent)
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
