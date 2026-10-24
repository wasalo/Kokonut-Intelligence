"""Focused contracts for the signed read-only credit adjustment worker."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.analytics import carbon_credit_adjustment_worker as worker


def _connection(rows=None):
    connection = MagicMock()
    connection.autocommit = False
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


@pytest.mark.parametrize("arguments", [[], ["--location-id", "invalid"]])
def test_invalid_location_fails_before_feature_or_credential_access(arguments):
    with (
        patch.object(sys, "argv", ["credit_adjustment_worker", *arguments]),
        patch("services.analytics.carbon_credit_adjustment_worker.is_enabled") as enabled,
        patch("services.analytics.carbon_credit_adjustment_worker.get_worker_credential") as credential,
        patch("services.analytics.carbon_credit_adjustment_worker.get_worker_db") as get_db,
    ):
        with pytest.raises(SystemExit) as error:
            worker.main()

    assert error.value.code == 2
    enabled.assert_not_called()
    credential.assert_not_called()
    get_db.assert_not_called()


def test_disabled_worker_fails_before_credentials_or_database():
    location_id = uuid4()
    with (
        patch.object(sys, "argv", ["credit_adjustment_worker", "--location-id", str(location_id)]),
        patch("services.analytics.carbon_credit_adjustment_worker.is_enabled", return_value=False),
        patch("services.analytics.carbon_credit_adjustment_worker.check") as check,
    ):
        with pytest.raises(SystemExit) as error:
            worker.main()

    assert error.value.code == 2
    check.assert_not_called()


def test_worker_sets_signed_scope_before_bounded_read_and_filters_small_differences():
    location_id = uuid4()
    connection, cursor = _connection([
        ("KKNT-A", 100.0, 101.0),
        ("KKNT-B", 100.0, 100.05),
        ("KKNT-C", 0.0, 0.0),
    ])
    calls = []

    def set_context(*args, **kwargs):
        calls.append("context")

    def execute(statement, parameters):
        calls.append("bounded_read")
        cursor.executed = (statement, parameters)

    cursor.execute.side_effect = execute
    with (
        patch("services.analytics.carbon_credit_adjustment_worker.get_worker_credential", return_value="x" * 32),
        patch("services.analytics.carbon_credit_adjustment_worker.get_worker_db", return_value=connection),
        patch("services.analytics.carbon_credit_adjustment_worker.set_worker_tenant_context", side_effect=set_context) as context,
    ):
        result = worker.check(str(location_id).upper())

    assert calls == ["context", "bounded_read"]
    context.assert_called_once_with(
        connection,
        credential="x" * 32,
        location_id=str(location_id),
        resource="carbon_credit_adjustment",
        action="read",
    )
    statement, parameters = cursor.executed
    assert "kokonut_security.credit_adjustment_snapshot_for_location" in statement
    assert parameters == (str(location_id),)
    assert result == [{
        "credit_code": "KKNT-A",
        "current_tonnes": 100.0,
        "recomputed_tonnes": 101.0,
        "delta_pct": 1.0,
        "needs_adjustment": True,
    }]
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


def test_bounded_read_failure_rolls_back_and_closes_worker_connection():
    connection, cursor = _connection()
    cursor.execute.side_effect = RuntimeError("synthetic bounded read failure")
    with (
        patch("services.analytics.carbon_credit_adjustment_worker.get_worker_credential", return_value="x" * 32),
        patch("services.analytics.carbon_credit_adjustment_worker.get_worker_db", return_value=connection),
        patch("services.analytics.carbon_credit_adjustment_worker.set_worker_tenant_context"),
    ):
        with pytest.raises(RuntimeError, match="synthetic bounded read failure"):
            worker.check(str(uuid4()))

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_cli_reports_only_scoped_read_result():
    location_id = uuid4()
    rows = [{"credit_code": "KKNT-A", "needs_adjustment": True}]
    with (
        patch.object(sys, "argv", ["credit_adjustment_worker", "--location-id", str(location_id)]),
        patch("services.analytics.carbon_credit_adjustment_worker.is_enabled", return_value=True),
        patch("services.analytics.carbon_credit_adjustment_worker.check", return_value=rows),
        patch("services.analytics.carbon_credit_adjustment_worker.print_json") as print_json,
    ):
        worker.main()

    assert print_json.call_args.args[0] == {
        "status": "success",
        "scope": "location",
        "location_id": str(location_id),
        "count": 1,
        "adjustments": rows,
    }
