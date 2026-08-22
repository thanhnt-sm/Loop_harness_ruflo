#!/bin/bash
# find_python.sh — shared cross-platform python detection cho opencode hooks
# Source: source .opencode/hooks/find_python.sh
# Output: PYTHON variable = path to python executable, or empty string

find_python() {
    if [ -f ".venv/Scripts/python.exe" ]; then
        echo ".venv/Scripts/python.exe"
    elif [ -f ".venv/bin/python" ]; then
        echo ".venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        echo "python3"
    elif command -v python >/dev/null 2>&1; then
        echo "python"
    else
        echo ""
    fi
}

PYTHON=$(find_python)
