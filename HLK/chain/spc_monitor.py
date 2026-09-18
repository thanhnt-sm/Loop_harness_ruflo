import json
import os

class DriftDetector:
    def __init__(self, plan_dir=".devin/plan_state"):
        self.plan_dir = plan_dir

    def get_active_plan(self):
        plan_path = os.path.join(self.plan_dir, "active_plan.json")
        if not os.path.exists(plan_path):
            return None
        with open(plan_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def detect_drift(self, action_log):
        """
        Kiểm tra xem action có bị trượt khỏi plan không.
        action_log: dictionary chứa thông tin hành động (vd: {"type": "file_edit", "path": "path/to/file"})
        """
        plan = self.get_active_plan()
        if not plan:
            # Nếu không có plan, có thể cho phép hoặc chặn tùy chính sách.
            # Tạm thời cho phép nếu không có active plan.
            return False, "Không có active plan."

        if action_log.get("type") in ["file_edit", "file_create", "file_delete"]:
            target_file = action_log.get("path")
            allowed_files = plan.get("allowed_files", [])
            if target_file and target_file not in allowed_files:
                return True, f"Drift detected: Sửa file {target_file} không nằm trong allowed_files của plan."

        return False, "Action hợp lệ theo plan."

def check_drift(action_log):
    detector = DriftDetector()
    return detector.detect_drift(action_log)
