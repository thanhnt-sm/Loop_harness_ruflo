@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
if "%~1"=="" (
    echo Usage: harness-bestofn.cmd ^<task^> [n_candidates]
    exit /b 1
)
"%PYTHON%" .devin\scripts\best_of_n.py %*
