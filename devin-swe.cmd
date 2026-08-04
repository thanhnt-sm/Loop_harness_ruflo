@echo off
set "WS_ROOT=%~dp0"
if "%WS_ROOT:~-1%"=="\" set "WS_ROOT=%WS_ROOT:~0,-1%"
set "NODE_DIR=%WS_ROOT%\.tools\node"
if exist "%NODE_DIR%\node.exe" set "PATH=%NODE_DIR%;%PATH%"
set "NODE_PATH=%WS_ROOT%\node_modules"
set "DEVIN_MODEL=swe-1-7"
echo Devin CLI + Ruflo Autopilot
echo Model: SWE-1.7 Max (FREE beta, coding-tuned)
devin %*
