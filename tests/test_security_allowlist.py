"""Tests for services.security.execution_allowlist — allow/deny list operations."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.security.execution_allowlist import (
    ALLOWED_EVENT_HANDLERS,
    ALLOWED_SCHEDULED_MODULES,
    validate_event_handler,
    validate_scheduled_module,
)


def test_allowed_event_handlers_is_frozen_set():
    """ALLOWED_EVENT_HANDLERS is a frozenset of tuples."""
    assert isinstance(ALLOWED_EVENT_HANDLERS, frozenset)
    for entry in ALLOWED_EVENT_HANDLERS:
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        assert isinstance(entry[0], str)
        assert isinstance(entry[1], str)


def test_allowed_scheduled_modules_is_frozen_set():
    """ALLOWED_SCHEDULED_MODULES is a frozenset of strings."""
    assert isinstance(ALLOWED_SCHEDULED_MODULES, frozenset)
    for entry in ALLOWED_SCHEDULED_MODULES:
        assert isinstance(entry, str)


def test_validate_event_handler_allowed():
    """validate_event_handler does not raise for allowlisted handlers."""
    module, func = next(iter(ALLOWED_EVENT_HANDLERS))
    validate_event_handler(module, func)  # Should not raise


def test_validate_event_handler_denied():
    """validate_event_handler raises ValueError for non-allowlisted handlers."""
    with pytest.raises(ValueError, match="not allowlisted"):
        validate_event_handler("services.evil.module", "malicious_func")


def test_validate_scheduled_module_allowed():
    """validate_scheduled_module does not raise for allowlisted modules."""
    module = next(iter(ALLOWED_SCHEDULED_MODULES))
    validate_scheduled_module(module)  # Should not raise


def test_validate_scheduled_module_denied():
    """validate_scheduled_module raises ValueError for non-allowlisted modules."""
    with pytest.raises(ValueError, match="not allowlisted"):
        validate_scheduled_module("services.unauthorized.scheduler")


def test_event_handlers_contain_known_handlers():
    """ALLOWED_EVENT_HANDLERS contains the expected cache event handlers."""
    assert ("services.cache.events", "handle_metric_computed") in ALLOWED_EVENT_HANDLERS
    assert ("services.cache.events", "handle_crisp_scored") in ALLOWED_EVENT_HANDLERS


def test_scheduled_modules_contain_known_modules():
    """ALLOWED_SCHEDULED_MODULES contains expected ingestion modules."""
    assert "services.ingestion.weather" in ALLOWED_SCHEDULED_MODULES
    assert "services.metrics" in ALLOWED_SCHEDULED_MODULES
    assert "services.events" in ALLOWED_SCHEDULED_MODULES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
