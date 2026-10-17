"""Tests for gateway audit normalization and non-secret request identities."""

from unittest.mock import MagicMock, patch

from services.gateway.app import _request_identity
from services.gateway.audit import GatewayAudit
from services.gateway.rate_limiter import RateLimiter


def test_gateway_audit_maps_http_method_to_database_action():
    conn = MagicMock()
    audit_logger = MagicMock()
    with patch("services.gateway.audit.GatewayAudit._get_conn", return_value=conn):
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
    conn = MagicMock()
    audit_logger = MagicMock()
    with patch("services.gateway.audit.GatewayAudit._get_conn", return_value=conn):
        with patch("services.security.audit.AuditLogger", return_value=audit_logger):
            GatewayAudit().log(
                caller="caller",
                path="/health",
                method="GET",
                status="allowed",
                ip="testclient",
            )

    assert audit_logger.log_access.call_args.kwargs["ip_address"] is None


def test_gateway_audit_marks_handler_failures_as_errors():
    conn = MagicMock()
    audit_logger = MagicMock()
    with patch("services.gateway.audit.GatewayAudit._get_conn", return_value=conn):
        with patch("services.security.audit.AuditLogger", return_value=audit_logger):
            GatewayAudit().log(
                caller="caller",
                path="/api/data-stream/post",
                method="POST",
                status="error",
                status_code=500,
                reason="RuntimeError",
            )

    assert audit_logger.log_access.call_args.kwargs["metadata"]["outcome"] == "error"


def test_gateway_audit_closes_owned_connection():
    conn = MagicMock()
    with patch("services.gateway.audit.GatewayAudit._get_conn", return_value=conn):
        audit_logger = MagicMock()
        with patch("services.security.audit.AuditLogger", return_value=audit_logger):
            GatewayAudit().log(
                caller="caller",
                path="/health",
                method="GET",
                status="allowed",
            )

    conn.close.assert_called_once()


def test_gateway_audit_does_not_reuse_closed_owned_connection():
    conn = MagicMock()
    audit_logger = MagicMock()
    with patch("services.common.database.get_db", return_value=conn):
        with patch("services.security.audit.AuditLogger", return_value=audit_logger):
            audit = GatewayAudit()
            audit.log(caller="caller", path="/health", method="GET", status="allowed")
            audit.log(caller="caller", path="/health", method="GET", status="allowed")

    assert conn.close.call_count == 2


def test_gateway_audit_database_failure_log_omits_exception_details():
    diagnostic = "synthetic database credential diagnostic"
    audit = GatewayAudit(conn=MagicMock())
    spool = MagicMock()
    spool.path.exists.return_value = False
    spool.pending.return_value = []
    spool.enqueue.return_value = 1
    spool.alert_threshold = 100
    spool.max_pending = 100
    audit._get_spool = lambda: spool
    audit._write_record = MagicMock(side_effect=RuntimeError(diagnostic))
    audit._report_capture_state = MagicMock()

    with patch("services.gateway.audit.logger.error") as log_error:
        audit.log(caller="caller", path="/api/write", method="POST", status="allowed")

    log_error.assert_called_once_with("Gateway audit database write failed (%s)", "RuntimeError")
    assert diagnostic not in str(log_error.call_args)
    spool.enqueue.assert_called_once()


def test_gateway_audit_journal_failure_log_omits_exception_details():
    diagnostic = "synthetic local journal path diagnostic"
    audit = GatewayAudit(conn=MagicMock())
    spool = MagicMock()
    spool.path.exists.return_value = False
    spool.pending.return_value = []
    spool.enqueue.side_effect = OSError(diagnostic)
    audit._get_spool = lambda: spool
    audit._write_record = MagicMock(side_effect=RuntimeError("database unavailable"))
    audit._report_capture_state = MagicMock()

    with patch("services.gateway.audit.logger.error") as log_error:
        audit.log(caller="caller", path="/api/write", method="POST", status="allowed")

    assert log_error.call_count == 2
    assert log_error.call_args_list[0].args == (
        "Gateway audit database write failed (%s)", "RuntimeError",
    )
    assert log_error.call_args_list[1].args == (
        "Gateway audit local journal could not retain an event (%s)", "OSError",
    )
    assert diagnostic not in str(log_error.call_args_list)


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
