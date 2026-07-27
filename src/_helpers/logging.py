"""Sets up the app's logger."""

import logging
import logging.config
from os import environ
from pathlib import Path
from sys import stderr
from typing import Any

from .constants import LOG_DIRECTORY


def _get_logging_config() -> dict[str, Any]:
    """Generates a fresh config dict based on current state.

    Returns:
        dict: The logging-compatible dictionary, that can be used to configure
            the logger of the library.
    """
    env_log_dir = environ.get("LOG_DIR")
    log_dir = Path(env_log_dir) if env_log_dir else LOG_DIRECTORY
    log_file = log_dir / "financial_tracker.log"

    file_handler_enabled = True
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"WARNING: Could not create log directory {log_dir} ({error}). File logging disabled.", file=stderr)
        file_handler_enabled = False

    # define config dict
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {"format": "%(levelname)s: %(message)s"},
            "detailed": {
                "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "simple",
                "stream": "ext://sys.stderr",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": log_file,
                "mode": "a",
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 3,
            },
        },
        "loggers": {
            "": {
                "level": "CRITICAL",
                "handlers": ["stderr", "file"],
            },
            "financial_tracker": {
                "level": "DEBUG",
                "handlers": ["stderr", "file"],
                "propagate": False,
            },
        },
    }

    if not file_handler_enabled:
        del config["handlers"]["file"]
        config["loggers"][""]["handlers"].remove("file")
        config["loggers"]["financial_tracker"]["handlers"].remove("file")

    return config


def setup_logger() -> None:
    """Sets up the logger of the library."""
    logging.config.dictConfig(_get_logging_config())
