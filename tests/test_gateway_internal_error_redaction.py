"""Gateway internal errors do not expose exception diagnostics in logs."""

from unittest.mock import patch

from services.gateway.router import _internal_error


def test_internal_error_logs_only_exception_class_and_returns_generic_message():
    diagnostic = "synthetic database password diagnostic"
    error = RuntimeError(diagnostic)

    with patch("services.gateway.router.logger.error") as log_error:
        response = _internal_error(error)

    assert response.status_code == 500
    assert response.body == b'{"error":"Gateway request failed"}'
    log_error.assert_called_once_with("%s (%s)", "Gateway request failed", "RuntimeError")
    assert diagnostic not in str(log_error.call_args)
