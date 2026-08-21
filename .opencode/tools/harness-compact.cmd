@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
if "%~1"=="" (set "SESSION=test-session") else (set "SESSION=%~1")
if "%~2"=="" (set "LEVEL=full") else (set "LEVEL=%~2")
"%PYTHON%" .devin\hooks\context_compaction.py "%SESSION%" "%LEVEL%"
