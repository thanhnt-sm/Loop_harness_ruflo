@echo off
setlocal
set "PYTHONIOENCODING=utf-8"

:: Cross-platform python detection (Windows)
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

set "TOOL=%~1"
set "ARGS=%~2"

:: Save context for post-tool-use (dùng env vars, không string interpolation)
"%PYTHON%" -c "import json, os; tool = os.environ.get('TOOL', ''); args = os.environ.get('ARGS', ''); ctx = {'tool': tool, 'args': args, 'compress': False, 'mask': False}; ctx['compress'] = tool in ('bash', 'git'); ctx['mask'] = tool in ('read', 'grep', 'glob', 'ls'); print(json.dumps(ctx))" 2>nul

:: Delegate sang Devin pre_tool_use.py (9 gates enforcement)
:: Dùng Python generate JSON thay echo — chống special char injection (&, <, >, |)
if exist ".devin\hooks\pre_tool_use.py" (
    "%PYTHON%" -c "import json, sys, os; hook_input = {'tool_name': os.environ.get('TOOL', ''), 'tool_input': {'command': os.environ.get('ARGS', '')}, 'session_id': 'opencode-session'}; json.dump(hook_input, sys.stdout)" | "%PYTHON%" .devin\hooks\pre_tool_use.py 2>&1
    if errorlevel 2 (
        echo [opencode guard] BLOCKED by Devin pre_tool_use.py >&2
        exit /b 2
    )
)

:: Run hook integrity check (C1) — best-effort
if exist ".devin\scripts\hook_integrity.py" (
    "%PYTHON%" .devin\scripts\hook_integrity.py --verify >nul 2>&1
)
