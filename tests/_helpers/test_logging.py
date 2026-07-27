"""Unit tests for `_helpers.logging`."""

from pathlib import Path

import pytest

from _helpers.logging import _get_logging_config


class TestGetLoggingConfig:
    """Tests for `_get_logging_config`."""

    def test_uses_the_log_dir_env_var_override_when_set(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        """`LOG_DIR` takes priority over the default `LOG_DIRECTORY`."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))

        config = _get_logging_config()

        assert config["handlers"]["file"]["filename"] == tmp_path / "financial_tracker.log"

    def test_creates_the_log_directory_if_missing(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The log directory is created if it doesn't already exist."""
        log_dir = tmp_path / "does" / "not" / "exist"
        monkeypatch.setenv("LOG_DIR", str(log_dir))

        _get_logging_config()

        assert log_dir.is_dir()

    def test_file_handler_appends_and_rotates(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The file handler is a rotating handler, opened in append mode."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))

        handler_config = _get_logging_config()["handlers"]["file"]

        assert handler_config["class"] == "logging.handlers.RotatingFileHandler"
        assert handler_config["mode"] == "a"
        assert handler_config["maxBytes"] > 0
        assert handler_config["backupCount"] > 0

    def test_both_handlers_log_at_debug_level(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verbosity is no longer gated behind a flag: both handlers are always DEBUG."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))

        config = _get_logging_config()

        assert config["handlers"]["stderr"]["level"] == "DEBUG"
        assert config["handlers"]["file"]["level"] == "DEBUG"

    def test_disables_file_logging_if_the_log_directory_cannot_be_created(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A directory-creation failure degrades gracefully instead of crashing."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path / "unwritable"))

        def raise_os_error(*args: object, **kwargs: object) -> None:
            raise OSError("no permission")

        monkeypatch.setattr(Path, "mkdir", raise_os_error)

        config = _get_logging_config()

        assert "file" not in config["handlers"]
        assert "file" not in config["loggers"][""]["handlers"]
        assert "file" not in config["loggers"]["financial_tracker"]["handlers"]
