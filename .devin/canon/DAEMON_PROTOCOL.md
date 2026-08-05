# U38: Daemonize aide-memory MCP

> Source: Performance Engineer. Impact: -500-2000ms/session.

## Problem

Each session spawns a new aide-memory MCP process. Cold start costs 500-2000ms.
With a daemon, sessions connect to an existing process — startup < 100ms.

## Solution

### Architecture

```
┌─────────────┐     IPC (stdio/socket)     ┌──────────────┐
│  Session 1  │ ────────────────────────── │              │
│  Session 2  │ ────────────────────────── │  aide-memory │
│  Session 3  │ ────────────────────────── │   daemon     │
└─────────────┘                            └──────────────┘
                                                    │
                                           ┌────────┴───────┐
                                           │  Memory store  │
                                           │  (file-based)  │
                                           └────────────────┘
```

### Daemon mode

The daemon is a long-running Node.js process that:
1. Loads aide-memory once at startup
2. Listens for IPC connections (stdin/stdout JSON-RPC or Unix socket)
3. Serves multiple sessions concurrently
4. Persists memory to disk

### IPC protocol

Uses JSON-RPC over stdio (same as MCP protocol):
- Client sends: `{"jsonrpc":"2.0","method":"aide_recall","params":{...},"id":1}`
- Server responds: `{"jsonrpc":"2.0","result":{...},"id":1}`

### Startup

```bash
# Start daemon (background)
node $APPDATA/nvm/v18.20.0/node_modules/aide-memory/daemon.js &

# Or via script
pwsh tools/aide-memory-daemon.ps1 start
```

### Session connection

Sessions connect to the daemon instead of spawning new process:
```json
{
  "mcpServers": {
    "aide-memory": {
      "type": "stdio",
      "command": "node",
      "args": ["$APPDATA/nvm/v18.20.0/node_modules/aide-memory/client.js"],
      "env": { "AIDE_MEMORY_DAEMON": "1" }
    }
  }
}
```

### Health check

```bash
pwsh tools/aide-memory-daemon.ps1 status
# Output: daemon running (PID 12345), uptime 2h 15m, 5 sessions connected
```

### Stop daemon

```bash
pwsh tools/aide-memory-daemon.ps1 stop
```

## Acceptance criteria status

- [x] Daemon mode documented (this file)
- [ ] IPC connection works (requires aide-memory upstream support)
- [ ] Startup time < 100ms when daemon running (requires implementation)

## Implementation notes

> **Note**: Full daemonization requires upstream aide-memory package support.
> This document defines the architecture and interface. Implementation is
> deferred until aide-memory adds daemon mode, or a wrapper daemon is built.

### Wrapper daemon approach (interim)

A wrapper daemon can be built that:
1. Spawns aide-memory as a child process
2. Keeps it alive between sessions
3. Routes IPC from new sessions to the existing process

This avoids modifying aide-memory upstream but adds a thin proxy layer.

### Performance target

| Metric | Without daemon | With daemon | Target |
|--------|---------------|-------------|--------|
| Cold start | 500-2000ms | <100ms | <100ms |
| Memory usage | 1 process/session | 1 process + N clients | Lower |
| Recall latency | Same | Same | Same |
