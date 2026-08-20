@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
if "%~1"=="" (set "SESSION=session_%RANDOM%") else (set "SESSION=%~1")
"%PYTHON%" .devin\scripts\cost_dashboard.py >nul 2>&1
if exist ".opencode\session_state\tool_outputs" (
    for /f "skip=100 delims=" %%a in ('dir /b /o-d ".opencode\session_state\tool_outputs\*.txt" 2^>nul') do del ".opencode\session_state\tool_outputs\%%a" 2>nul
)
echo Harness: Session %SESSION% ended
