"""Mocked contracts for location-scoped extension-learning mutations."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.gateway import extension_learning_writes as writes

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
PROGRESS_ID = str(uuid4())
MODULE_ID = str(uuid4())


def _connection_with_result(result):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.description = [(key,) for key in result]
    cursor.fetchone.return_value = tuple(result.values())
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_create_peer_network_sets_scoped_context_and_uses_bounded_sql_function(monkeypatch):
    receipt = {
        "peer_network_id": str(uuid4()),
        "location_id": LOCATION_ID,
        "network_name": "Learning group",
        "network_type": "learning_group",
        "status": "active",
        "created_at": "2026-10-30T12:00:00+00:00",
        "request_id": REQUEST_ID,
        "created": True,
    }
    connection, cursor = _connection_with_result(receipt)
    context = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: context.append((conn, kwargs)),
    )

    result = writes.create_location_extension_peer_network(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        network_name=" Learning group ",
        network_type="learning_group",
        description="   ",
        max_members=12,
        meeting_cadence=" weekly ",
        metadata={"synthetic": True},
        connection_factory=lambda: connection,
    )

    assert result == receipt
    assert context == [(
        connection,
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "extension_learning",
            "action": "create_peer_network",
        },
    )]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "create_extension_peer_network" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        REQUEST_ID,
        "Learning group",
        None,
        "learning_group",
        12,
        "weekly",
        "en",
        '{"synthetic":true}',
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_progress_update_sets_location_context_and_omits_participant_identity(monkeypatch):
    receipt = {
        "progress_id": PROGRESS_ID,
        "location_id": LOCATION_ID,
        "module_id": MODULE_ID,
        "progress_pct": 75,
        "score": 88.5,
        "time_spent_min": 30,
        "status": "completed",
        "completed_at": "2026-10-30T12:00:00+00:00",
        "updated_at": "2026-10-30T12:00:00+00:00",
        "request_id": REQUEST_ID,
    }
    connection, cursor = _connection_with_result(receipt)
    context = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: context.append((conn, kwargs)),
    )

    result = writes.update_location_extension_learning_progress(
        OPERATOR_ID,
        LOCATION_ID,
        PROGRESS_ID,
        REQUEST_ID,
        status="completed",
        score=88.5,
        progress_pct=75,
        time_spent_min_delta=15,
        metadata_patch={"reviewed": True},
        connection_factory=lambda: connection,
    )

    assert result == receipt
    assert "farmer_name" not in result
    assert context == [(
        connection,
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "extension_learning",
            "action": "update_progress",
        },
    )]
    assert "update_extension_learning_progress" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        PROGRESS_ID,
        REQUEST_ID,
        "completed",
        88.5,
        75,
        15,
        '{"reviewed":true}',
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    "operation",
    [
        lambda factory: writes.create_location_extension_peer_network(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            network_name="Group",
            network_type="learning_group",
            max_members=True,
            connection_factory=factory,
        ),
        lambda factory: writes.update_location_extension_learning_progress(
            OPERATOR_ID,
            LOCATION_ID,
            PROGRESS_ID,
            REQUEST_ID,
            status="certified",
            connection_factory=factory,
        ),
        lambda factory: writes.update_location_extension_learning_progress(
            OPERATOR_ID,
            LOCATION_ID,
            PROGRESS_ID,
            REQUEST_ID,
            time_spent_min_delta=1441,
            connection_factory=factory,
        ),
    ],
)
def test_invalid_inputs_fail_before_database_access(operation):
    def unexpected_connection():
        pytest.fail("invalid extension-learning input opened a database connection")

    with pytest.raises(writes.ExtensionLearningWriteInvalid):
        operation(unexpected_connection)


def test_missing_function_receipt_rolls_back_and_closes_connection(monkeypatch):
    connection, cursor = _connection_with_result({"placeholder": None})
    cursor.fetchone.return_value = None
    monkeypatch.setattr(writes, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(writes.ExtensionLearningWriteConflict):
        writes.create_location_extension_peer_network(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            network_name="Group",
            network_type="other",
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
