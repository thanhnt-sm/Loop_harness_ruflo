#!/usr/bin/env python3
import os
import sys
import subprocess

def main():
    """
    Shim wrapper để gọi vào core CLI trong thư mục HLK.
    """
    # Lấy đường dẫn của workspace root
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    core_cli_path = os.path.join(workspace_root, "HLK", "chain", "audit", "bounded_audit.py")
    
    if not os.path.exists(core_cli_path):
        print(f"Error: Core CLI not found at {core_cli_path}", file=sys.stderr)
        sys.exit(1)

    # Xây dựng command argument list (passthrough arguments)
    cmd = [sys.executable, core_cli_path] + sys.argv[1:]
    
    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Shim error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
