@echo off
REM Ruflo HLK Launcher — Windows Command Prompt
REM Tự động set NODE_OPTIONS trỏ đến HLK loader rồi chạy bin/cli.js.

setlocal

REM Xác định đường dẫn dựa trên vị trí file .cmd này
set "WRAPPER_DIR=%~dp0"
set "REPO_ROOT=%WRAPPER_DIR%..\.."
set "LOADER_URL=file://%REPO_ROOT%\HLK\wrappers\hlk-loader.js"
set "CLI_PATH=%REPO_ROOT%\bin\cli.js"

REM Chuẩn bị NODE_OPTIONS
if "%NODE_OPTIONS%"=="" (
    set "NODE_OPTIONS=--import=%LOADER_URL%"
) else (
    echo %NODE_OPTIONS% | findstr /C:"--import=" >nul || (
        set "NODE_OPTIONS=%NODE_OPTIONS% --import=%LOADER_URL%"
    )
)

REM Chạy Node
node "%CLI_PATH%" %*
