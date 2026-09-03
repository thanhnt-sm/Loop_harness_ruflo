/**
 * hlk-guardian.ts — Command Code MOD (loadable plugin)
 *
 * Ủy quyền 1 mod chuyên cho HLK: thay vì tạo nhiều slash command, mod này
 * expose 1 inline tool `hlk_status` + 1 slash command `/hlk-quick` + 1 hook
 * lifecycle observer tự verify HLK mỗi session start.
 *
 * Load bằng: `cmd --mod ./.commandcode/mods/hlk-guardian.ts`
 * Hoặc đặt trong `.commandcode/mods/` để tự load.
 *
 * Spec: commandcode.ai/docs/mods (ModApi) — bundled skill `mod-builder`.
 */

import type { Mod, ModApi } from "command-code/mod-api";

export default function hlkGuardian(api: ModApi): Mod {
  // Track session start count
  let sessionStarts = 0;

  api.on("session.start", async (event) => {
    sessionStarts++;
    if (sessionStarts % 1 === 0) {
      // Run on every session start. Fail-open.
      try {
        const { execFile } = await import("node:child_process");
        const { promisify } = await import("node:util");
        const pexec = promisify(execFile);
        await pexec("node", ["HLK/bin/hlk-status.mjs", "--self-test"], {
          timeout: 5000,
          cwd: event.cwd,
        }).catch(() => {
          /* fail-open */
        });
      } catch {
        /* fail-open */
      }
    }
  });

  return {
    name: "hlk-guardian",
    version: "1.0.0",
    description:
      "HLK Guardian — tự verify HLK mỗi session start; expose hlk_status tool + /hlk-quick command.",

    commands: [
      {
        name: "hlk-quick",
        description:
          "Quick HLK diagnostic — chạy hlk-status self-test + verify-integrity song song, in verdict 1 dòng.",
        async handler(args: string) {
          try {
            const { execFile } = await import("node:child_process");
            const { promisify } = await import("node:util");
            const pexec = promisify(execFile);
            const cwd = process.cwd();
            const [status, integrity] = await Promise.all([
              pexec("node", ["HLK/bin/hlk-status.mjs", "--self-test"], { timeout: 8000, cwd }).catch((e) => ({ stderr: String(e), stdout: "" })),
              pexec("node", ["HLK/wrappers/hlk-verify-integrity.js"], { timeout: 8000, cwd }).catch((e) => ({ stderr: String(e), stdout: "" })),
            ]);
            const ok = !status.stderr && !integrity.stderr;
            return {
              ok,
              text: ok
                ? `HLK OK (${new Date().toISOString()})`
                : `HLK degraded: status=${status.stderr || "ok"} | integrity=${integrity.stderr || "ok"}`,
            };
          } catch (e) {
            return { ok: false, text: `hlk-guardian error: ${e}` };
          }
        },
      },
    ],

    tools: [
      {
        name: "hlk_status",
        description:
          "Read HLK config version + feature toggles + sanitizer health. Use before any HLK-touching operation.",
        input: {
          type: "object",
          properties: {
            includeRedactPatterns: { type: "boolean", default: false },
          },
        },
        async execute(input: { includeRedactPatterns?: boolean }) {
          try {
            const { readFile } = await import("node:fs/promises");
            const path = await import("node:path");
            const cfgPath = path.join(process.cwd(), "HLK", "config", "hlk.config.json");
            const raw = await readFile(cfgPath, "utf-8");
            const cfg = JSON.parse(raw);
            const out: Record<string, unknown> = {
              ok: true,
              version: cfg.version,
              hlk_enabled: cfg.hlk_enabled,
              features: cfg.features,
              sanitize_replacement: cfg.security_rules?.redact_replacement,
              telemetry_blocked: Object.keys(cfg.telemetry_overrides || {}).length,
            };
            if (input.includeRedactPatterns) {
              out.redact_pattern_count = (cfg.security_rules?.redact_patterns || []).length;
            }
            return { ok: true, text: JSON.stringify(out, null, 2) };
          } catch (e) {
            return { ok: false, text: `hlk_status error: ${e}` };
          }
        },
      },
    ],
  };
}
