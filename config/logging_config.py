"""
Centralized logging configuration for the proactive reporting agent.
"""

import logging
import logging.config
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to write logs to file. Logs always go to stdout.
    """
    Path("logs").mkdir(exist_ok=True)

    handlers: dict = {
        "console": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": "detailed",
            "stream": "ext://sys.stdout",
        }
    }

    if log_file:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "detailed",
            "filename": log_file,
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "encoding": "utf-8",
        }

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": (
                    "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {
                "format": "%(levelname)s | %(name)s | %(message)s",
            },
        },
        "handlers": handlers,
        "loggers": {
            "src": {
                "level": log_level,
                "handlers": list(handlers.keys()),
                "propagate": False,
            },
            "config": {
                "level": log_level,
                "handlers": list(handlers.keys()),
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    }

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger. Use this in every module:

        from config.logging_config import get_logger
        logger = get_logger(__name__)

    Args:
        name: Usually __name__ of the calling module.

    Returns:
        Configured Logger instance.
    """
    return logging.getLogger(name)
