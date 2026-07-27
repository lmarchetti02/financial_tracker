"""Shared pytest fixtures."""

import os
import tempfile

import pytest

# redirect log file to tmp dir
temp_log_dir = tempfile.mkdtemp(prefix="tracker_tests_")
os.environ["LOG_DIR"] = temp_log_dir
print(f"\n[Test Setup] Redirected test logs to: {temp_log_dir}")

import database.db_operations.config as db_config  # noqa: E402
import database.db_operations.generic as db_generic  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_app_directory(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirects every DB file path to a temp dir instead of the real `~/Library/Application Support/Financial Tracker/`.

    `get_db_path`/`get_config_db_path` each build their path directly from their own module-level
    `APP_DIRECTORY` binding, so both must be patched to keep every test off the user's real data.
    """
    monkeypatch.setattr(db_generic, "APP_DIRECTORY", tmp_path)
    monkeypatch.setattr(db_config, "APP_DIRECTORY", tmp_path)
