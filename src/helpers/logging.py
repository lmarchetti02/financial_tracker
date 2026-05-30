import logging
import logging.config
from os import W_OK, access, environ
from pathlib import Path
from sys import stderr
from typing import Any

from .constants import DEBUGGING


def _get_logging_config(is_debugging: bool) -> dict[str, Any]:
    """Generates a fresh config dict based on current state.

    Args:
        is_debugging (bool): Whether the user has selected the verbose "DEBUGGING"
            mode or not (via 'export DEEBUGGING="True"').

    Returns:
        dict: The logging-compatible dictionary, that can be used to configure
            the logger of the library.
    """
    # check if dirs are writable
    is_cwd_writable = access(Path.cwd(), W_OK)
    is_home_writable = access(Path.home(), W_OK)

    env_log_dir = environ.get("LOG_DIR")
    base_dir = Path(env_log_dir) if env_log_dir else Path.cwd()

    # define log path
    log_file = base_dir / "financial_tracker.log"
    if not is_cwd_writable and is_home_writable:
        log_file = Path.home() / "financial_tracker.log"
        print(f"WARNING: CWD is read-only. Logging to {log_file}.", file=stderr)

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
                "level": "DEBUG" if is_debugging else "WARNING",
                "formatter": "simple",
                "stream": "ext://sys.stderr",
            },
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": log_file,
                "mode": "w",
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

    # fallback if no path is writable
    if not is_cwd_writable and not is_home_writable:
        print("WARNING: Neither CWD nor home are writable. File logging disabled.", file=stderr)

        # remove log file from config
        del config["handlers"]["file"]
        config["loggers"][""]["handlers"].remove("file")
        config["loggers"]["financial_tracker"]["handlers"].remove("file")

    return config


def setup_logger() -> None:
    """Sets up the logger of the library."""
    new_config = _get_logging_config(DEBUGGING)
    logging.config.dictConfig(new_config)
