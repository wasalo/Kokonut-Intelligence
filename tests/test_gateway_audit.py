"""Tests for gateway audit normalization and non-secret request identities."""

from unittest.mock import MagicMock, patch

from services.gateway.app import _request_identity
from services.gateway.audit import GatewayAudit
from services.gateway.rate_limiter import RateLimiter


def test_gateway_audit_maps_http_method_to_database_action():
    audit_logger = MagicMock()
    with patch("services.security.audit.AuditLogger", return_value=audit_logger):
        GatewayAudit().log(
            caller="caller",
            path="/api/metrics/location",
            method="GET",
            status="allowed",
            ip="127.0.0.1",
            resource="metric",
            action="read",
        )

    assert audit_logger.log_access.call_args.kwargs["action"] == "read"
    assert audit_logger.log_access.call_args.kwargs["resource_id"] is None
    assert audit_logger.log_access.call_args.kwargs["metadata"]["http_method"] == "GET"


def test_gateway_audit_rejects_invalid_ip_without_failing_request():
    audit_logger = MagicMock()
    with patch("services.security.audit.AuditLogger", return_value=audit_logger):
        GatewayAudit().log(
            caller="caller",
            path="/health",
            method="GET",
            status="allowed",
            ip="testclient",
        )

    assert audit_logger.log_access.call_args.kwargs["ip_address"] is None


def test_request_identity_does_not_return_raw_credentials():
    request = MagicMock()
    request.headers.get.side_effect = lambda key: "secret" if key == "x-api-key" else None

    identity = _request_identity(request, "127.0.0.1")

    assert identity.startswith("credential:")
    assert "secret" not in identity


def test_rate_limiter_returns_retry_after_and_bounds_callers():
    limiter = RateLimiter(max_tokens=1, refill_rate=1, max_callers=1)
    assert limiter.check("first")
    assert not limiter.check("first")
    assert limiter.retry_after("first") >= 1
    assert limiter.check("second")
    assert "first" not in limiter._buckets
