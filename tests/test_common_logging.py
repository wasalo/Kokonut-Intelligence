"""Tests for services.common.logging — structured logging setup."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.common.logging import get_logger, setup_logging, _CONFIGURED


@pytest.fixture(autouse=True)
def _reset_configured():
    """Reset the module-level _CONFIGURED flag between tests."""
    import services.common.logging as mod
    mod._CONFIGURED = False
    yield
    mod._CONFIGURED = False


def test_get_logger_returns_logger():
    """get_logger returns a logging.Logger instance."""
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "kokonut.test.module"


def test_get_logger_prefixes_kokonut():
    """Names not starting with 'kokonut.' get the prefix added."""
    logger = get_logger("ingestion.weather")
    assert logger.name == "kokonut.ingestion.weather"


def test_get_logger_preserves_kokonut_prefix():
    """Names already starting with 'kokonut.' are not double-prefixed."""
    logger = get_logger("kokonut.migration.runner")
    assert logger.name == "kokonut.migration.runner"


@patch.dict(os.environ, {"KOKONUT_LOG_LEVEL": "DEBUG"})
def test_setup_logging_respects_env_var():
    """setup_logging reads KOKONUT_LOG_LEVEL from the environment."""
    setup_logging()
    root = logging.getLogger("kokonut")
    assert root.level == logging.DEBUG


@patch.dict(os.environ, {"KOKONUT_LOG_LEVEL": "WARNING"})
def test_setup_logging_warning_level():
    """KOKONUT_LOG_LEVEL=WARNING sets root to WARNING."""
    setup_logging()
    root = logging.getLogger("kokonut")
    assert root.level == logging.WARNING


def test_setup_logging_adds_handlers():
    """setup_logging adds stderr and stdout handlers to the root logger."""
    setup_logging()
    root = logging.getLogger("kokonut")
    assert len(root.handlers) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
