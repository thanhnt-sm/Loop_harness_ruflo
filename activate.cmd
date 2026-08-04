@echo off
set "WS_ROOT=%~dp0"
if "%WS_ROOT:~-1%"=="\" set "WS_ROOT=%WS_ROOT:~0,-1%"
set "NODE_DIR=%WS_ROOT%\.tools\node"
if not exist "%NODE_DIR%\node.exe" (echo LOI: Khong tim thay Node portable & exit /b 1)
set "PATH=%NODE_DIR%;%PATH%"
set "NODE_PATH=%WS_ROOT%\node_modules"
echo Node portable da kich hoat
endlocal & set "PATH=%NODE_DIR%;%PATH%" & set "NODE_PATH=%WS_ROOT%\node_modules"
