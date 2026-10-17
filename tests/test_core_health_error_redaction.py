"""Core health probes retain generic statuses without logging exception text."""

from unittest.mock import MagicMock, patch

from services.core.health import _check_clickhouse, _check_directus, _check_postgres

DIAGNOSTIC = "synthetic service password diagnostic"


def test_postgres_health_failure_logs_only_exception_class():
    with (
        patch("services.common.database.get_db", side_effect=RuntimeError(DIAGNOSTIC)),
        patch("services.core.health.logger.error") as log_error,
    ):
        result = _check_postgres()

    assert result.healthy is False
    assert result.message == "PostgreSQL unavailable"
    log_error.assert_called_once_with("PostgreSQL health check failed (%s)", "RuntimeError")
    assert DIAGNOSTIC not in str(log_error.call_args)


def test_clickhouse_health_failure_logs_only_exception_class():
    with (
        patch("services.ingestion.base.get_clickhouse", side_effect=ConnectionError(DIAGNOSTIC)),
        patch("services.core.health.logger.error") as log_error,
    ):
        result = _check_clickhouse()

    assert result.healthy is False
    assert result.message == "ClickHouse unavailable"
    log_error.assert_called_once_with("ClickHouse health check failed (%s)", "ConnectionError")
    assert DIAGNOSTIC not in str(log_error.call_args)


def test_directus_health_failure_logs_only_exception_class():
    response = MagicMock()
    response.raise_for_status.side_effect = OSError(DIAGNOSTIC)
    with (
        patch("services.common.http.http.get", return_value=response),
        patch("services.core.health.logger.error") as log_error,
    ):
        result = _check_directus()

    assert result.healthy is False
    assert result.message == "Directus unavailable"
    log_error.assert_called_once_with("Directus health check failed (%s)", "OSError")
    assert DIAGNOSTIC not in str(log_error.call_args)
