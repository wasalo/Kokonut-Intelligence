"""Focused checks for the signed NOI snapshot worker entrypoint."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.metrics import noi_snapshot_worker


def _connection(row=(3,)):
    connection = MagicMock()
    connection.autocommit = False
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


@pytest.mark.parametrize("arguments", [[], ["--location-id", "bad-uuid"]])
def test_bad_location_fails_before_feature_secret_or_database_access(arguments):
    with (
        patch.object(sys, "argv", ["noi_snapshot_worker", *arguments]),
        patch("services.metrics.noi_snapshot_worker.is_enabled") as enabled,
        patch("services.common.worker_database.get_worker_credential") as credential,
        patch("services.common.worker_database.get_worker_db") as get_db,
    ):
        with pytest.raises(SystemExit) as error:
            noi_snapshot_worker.main()

    assert error.value.code == 2
    enabled.assert_not_called()
    credential.assert_not_called()
    get_db.assert_not_called()


def test_disabled_worker_fails_before_secret_or_database_access():
    with (
        patch.object(sys, "argv", ["noi_snapshot_worker", "--location-id", str(uuid4())]),
        patch("services.metrics.noi_snapshot_worker.is_enabled", return_value=False),
        patch("services.metrics.noi_snapshot_worker.reconcile") as reconcile,
    ):
        with pytest.raises(SystemExit) as error:
            noi_snapshot_worker.main()

    assert error.value.code == 2
    reconcile.assert_not_called()


def test_worker_sets_signed_scope_before_bounded_call_and_commits_once():
    location_id = uuid4()
    connection, cursor = _connection((7,))
    call_order = []

    def set_context(*args, **kwargs):
        call_order.append("context")

    def execute(statement, parameters):
        call_order.append("bounded_function")
        cursor.executed = (statement, parameters)

    cursor.execute.side_effect = execute
    with (
        patch("services.common.worker_database.get_worker_credential", return_value="x" * 32),
        patch("services.common.worker_database.get_worker_db", return_value=connection),
        patch("services.common.tenant_context.set_worker_tenant_context", side_effect=set_context) as context,
    ):
        result = noi_snapshot_worker.reconcile(str(location_id).upper())

    assert result == 7
    assert call_order == ["context", "bounded_function"]
    context.assert_called_once_with(
        connection,
        credential="x" * 32,
        location_id=str(location_id),
        resource="noi_snapshot",
        action="reconcile",
    )
    statement, parameters = cursor.executed
    assert statement == "SELECT kokonut_security.reconcile_noi_snapshot_for_location(%s::uuid)"
    assert parameters == (str(location_id),)
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


def test_bounded_call_failure_rolls_back_and_closes_worker_connection():
    connection, cursor = _connection()
    cursor.execute.side_effect = RuntimeError("synthetic bounded-call failure")
    with (
        patch("services.common.worker_database.get_worker_credential", return_value="x" * 32),
        patch("services.common.worker_database.get_worker_db", return_value=connection),
        patch("services.common.tenant_context.set_worker_tenant_context"),
    ):
        with pytest.raises(RuntimeError, match="synthetic bounded-call failure"):
            noi_snapshot_worker.reconcile(str(uuid4()))

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_worker_cli_reports_only_location_scoped_reconciliation_count():
    location_id = uuid4()
    with (
        patch.object(sys, "argv", ["noi_snapshot_worker", "--location-id", str(location_id)]),
        patch("services.metrics.noi_snapshot_worker.is_enabled", return_value=True),
        patch("services.metrics.noi_snapshot_worker.reconcile", return_value=4),
        patch("services.metrics.noi_snapshot_worker.print_json") as print_json,
    ):
        noi_snapshot_worker.main()

    assert print_json.call_args.args[0] == {
        "status": "success",
        "reconciled": 4,
        "source": "v_crop_cycle_noi",
        "scope": "location",
        "location_id": str(location_id),
    }
