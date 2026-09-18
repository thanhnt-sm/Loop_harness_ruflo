import sys
import os

# Thêm đường dẫn HLK vào sys.path để import được module từ HLK/chain
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from HLK.chain.spc_monitor import check_drift
except ImportError:
    check_drift = None

def pre_action_hook(action_log):
    """
    Hook được gọi trước khi một hành động (tool_use) được thực thi.
    """
    if check_drift:
        is_drift, message = check_drift(action_log)
        if is_drift:
            print(f"[Plan Enforce Blocked]: {message}", file=sys.stderr)
            # Trả về False hoặc raise Exception để chặn hành động
            return False
    return True

# Các logic enforce khác có thể thêm ở đây
