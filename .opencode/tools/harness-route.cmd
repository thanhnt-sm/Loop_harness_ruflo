@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
if "%~1"=="" (
    echo Usage: harness-route.cmd ^<task_description^>
    exit /b 1
)
set "TASK=%~1"
"%PYTHON%" .devin\scripts\auto_model_router.py "%TASK%" --estimate-cost
