"""
Centralised logging setup.

Logs go to both stdout (for container/host visibility) and a rotating file
(persistent request/error history). Called once at application startup.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import Settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(settings: Settings) -> logging.Logger:
    """Configure the root logger and return the app logger."""
    log_path = settings.log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers when uvicorn reloads the module.
    root.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Quiet down noisy third-party access logs; we do our own request logging.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger("app")
    logger.info("Logging initialised (level=%s, file=%s)", settings.log_level, log_path)
    return logger
