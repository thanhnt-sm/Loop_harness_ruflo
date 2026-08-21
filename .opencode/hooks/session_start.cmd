@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
if "%~1"=="" (set "SESSION=test-session") else (set "SESSION=%~1")
"%PYTHON%" .devin\hooks\prompt_cache_metrics.py "%SESSION%" >nul 2>&1
if not exist ".opencode\session_state" mkdir ".opencode\session_state"
if not exist ".opencode\session_state\tool_outputs" mkdir ".opencode\session_state\tool_outputs"
if not exist ".opencode\session_state\compaction" mkdir ".opencode\session_state\compaction"
echo Harness initialized for session: %SESSION%
