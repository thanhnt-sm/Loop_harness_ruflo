@echo off
set "WS_ROOT=%~dp0"
if "%WS_ROOT:~-1%"=="\" set "WS_ROOT=%WS_ROOT:~0,-1%"
set "NODE_DIR=%WS_ROOT%\.tools\node"
if exist "%NODE_DIR%\node.exe" set "PATH=%NODE_DIR%;%PATH%"
set "NODE_PATH=%WS_ROOT%\node_modules"
REM Model mac dinh: glm-5-2 (FREE, khong ton quota Pro)
REM De doi model: set DEVIN_MODEL=swe-1-7  truoc khi chay
if "%DEVIN_MODEL%"=="" set "DEVIN_MODEL=glm-5-2"
echo Devin CLI + Ruflo Autopilot
echo Model: %DEVIN_MODEL%
devin %*
