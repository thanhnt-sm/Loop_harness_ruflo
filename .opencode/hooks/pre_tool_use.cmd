@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
set "TOOL=%~1"
set "ARGS=%~2"
"%PYTHON%" -c "import json, os; tool = os.environ.get('TOOL', ''); args = os.environ.get('ARGS', ''); ctx = {'tool': tool, 'args': args, 'compress': False, 'mask': False}; ctx['compress'] = tool in ('bash', 'git'); ctx['mask'] = tool in ('read', 'grep', 'glob', 'ls'); print(json.dumps(ctx))"
