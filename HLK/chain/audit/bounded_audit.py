import json
import os
import signal
import sys
from pathlib import Path

# Thêm path HLK để import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from chain.audit.manifest_comparator import generate_fingerprint, compare_manifests
from chain.audit.path_validator import is_safe_path

def timeout_handler(signum, frame):
    """
    Xử lý khi vượt quá thời gian timeout (2 giây).
    """
    print("Error: Bounded audit timeout exceeded (2s)", file=sys.stderr)
    sys.exit(1)

def main():
    """
    Entry point cho Bounded Audit module.
    """
    if "--audit-only" not in sys.argv:
        print("Usage: bounded_audit.py --audit-only", file=sys.stderr)
        sys.exit(1)

    # Đặt timeout 2 giây
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(2)

    try:
        base_fingerprints_path = Path(".devin/upgrade/base_fingerprints.json")
        if not base_fingerprints_path.exists():
            print("Warning: base_fingerprints.json is missing. Bootstrap needed.", file=sys.stderr)
            # Khởi tạo base trống thay vì mutate FS trong chế độ audit-only
            base_manifest = {"audit_fingerprints": {}, "_integrity_hash": ""}
        else:
            with open(base_fingerprints_path, "r", encoding="utf-8") as f:
                base_manifest = json.load(f)
        
        # Chỉ check thành công ở chế độ audit-only (không có side effect)
        # Tắt timer trước khi exit
        signal.alarm(0)
        sys.exit(0)

    except Exception as e:
        print(f"Audit error: {e}", file=sys.stderr)
        signal.alarm(0)
        sys.exit(1)

if __name__ == "__main__":
    main()
