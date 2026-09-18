import pytest
import subprocess
import os
import sys

def test_audit_shim_success():
    """
    Test chạy shim script trả về exit code 0 khi chạy với --audit-only
    """
    shim_path = os.path.join(".devin", "scripts", "audit_shim.py")
    result = subprocess.run([sys.executable, shim_path, "--audit-only"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Warning: base_fingerprints.json is missing." in result.stderr

def test_audit_shim_missing_args():
    """
    Test chạy shim script không có argument trả về exit code 1
    """
    shim_path = os.path.join(".devin", "scripts", "audit_shim.py")
    result = subprocess.run([sys.executable, shim_path], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Usage: bounded_audit.py --audit-only" in result.stderr
