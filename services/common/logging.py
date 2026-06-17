"""
Structured Logging Setup

Provides a consistent logging configuration for all Kokonut services.
CLI modules continue to use print() for user-facing output.
Operational modules (ingestion, analytics, etc.) use this for log routing.

Usage:
    from services.common.logging import get_logger
    logger = get_logger("ingestion.weather")
    logger.info("Fetched weather for %s", location_name)
"""

import logging
import os
import sys

_CONFIGURED = False


def setup_logging():
    """Configure root logger once. Respects KOKONUT_LOG_LEVEL env var."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level_name = os.environ.get("KOKONUT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger("kokonut")
    root.setLevel(level)

    if not root.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(fmt)
        root.addHandler(stderr_handler)

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
        stdout_handler.setFormatter(fmt)
        root.addHandler(stdout_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger under the kokonut root.

    Args:
        name: Logger name, e.g. "ingestion.weather", "migration.runner".
              Automatically prefixed with "kokonut.".
    """
    setup_logging()
    if name.startswith("kokonut."):
        return logging.getLogger(name)
    return logging.getLogger(f"kokonut.{name}")
