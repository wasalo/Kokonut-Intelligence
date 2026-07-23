"""Tests for services.security.interceptor — CapabilityInterceptor."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import grpc
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.security.interceptor import CapabilityInterceptor


@pytest.fixture
def interceptor():
    return CapabilityInterceptor(audit_logger=MagicMock())


@pytest.fixture
def read_handler_details():
    details = MagicMock()
    details.method = "/some.Service/ReadData"
    details.invocation_metadata = []
    return details


@pytest.fixture
def write_handler_details():
    details = MagicMock()
    details.method = "/some.Service/WriteData"
    details.invocation_metadata = [("x-capability-token", "tok_abc123")]
    return details


@pytest.fixture
def stream_handler_details():
    details = MagicMock()
    details.method = "/some.Service/StreamEvents"
    details.invocation_metadata = [("x-api-key", "key-123")]
    return details


def test_read_methods_pass_through(interceptor, read_handler_details):
    """Read-only methods are not intercepted — continuation is called directly."""
    continuation = MagicMock()
    result = interceptor.intercept_service(continuation, read_handler_details)
    continuation.assert_called_once_with(read_handler_details)


def test_write_without_token_returns_unauth(interceptor):
    """Write methods without any auth return a handler that raises UNAUTHENTICATED."""
    details = MagicMock()
    details.method = "/some.Service/Write"
    details.invocation_metadata = []

    continuation = MagicMock()
    handler = interceptor.intercept_service(continuation, details)
    # Continuation should NOT have been called — an error handler is returned
    continuation.assert_not_called()
    assert handler is not None


def test_write_with_api_key_passes(interceptor, stream_handler_details):
    """Write methods with an API key pass through to the continuation."""
    continuation = MagicMock()
    interceptor.intercept_service(continuation, stream_handler_details)
    continuation.assert_called_once_with(stream_handler_details)


@patch("services.security.capabilities.CapabilityManager")
def test_write_with_valid_token_passes(MockManager, interceptor, write_handler_details):
    """Write methods with a valid capability token pass through."""
    manager_instance = MagicMock()
    manager_instance.verify.return_value = {"holder": "agent-1", "capability": {}, "token_id": "tok-id"}
    MockManager.return_value = manager_instance

    continuation = MagicMock()
    interceptor.intercept_service(continuation, write_handler_details)
    continuation.assert_called_once_with(write_handler_details)


@patch("services.security.capabilities.CapabilityManager")
def test_write_with_invalid_token_denies(MockManager, interceptor):
    """Write methods with an invalid token return an error handler without calling continuation."""
    manager_instance = MagicMock()
    manager_instance.verify.return_value = None
    MockManager.return_value = manager_instance

    details = MagicMock()
    details.method = "/some.Service/Write"
    details.invocation_metadata = [("x-capability-token", "bad-token")]

    continuation = MagicMock()
    handler = interceptor.intercept_service(continuation, details)
    # Continuation should NOT have been called
    continuation.assert_not_called()
    assert handler is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
