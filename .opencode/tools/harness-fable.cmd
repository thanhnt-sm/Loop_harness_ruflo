@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
if "%~1"=="" (set "SESSION=test-session") else (set "SESSION=%~1")
if not "%~2"=="" (set "FAST=%~2") else (set "FAST=")
"%PYTHON%" .devin\scripts\fable_judge_compensation.py "%SESSION%" %FAST%
