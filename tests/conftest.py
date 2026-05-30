import os
import tempfile

# redirect log file to tmp dir
temp_log_dir = tempfile.mkdtemp(prefix="tracker_tests_")
os.environ["LOG_DIR"] = temp_log_dir
print(f"\n[Test Setup] Redirected test logs to: {temp_log_dir}")
