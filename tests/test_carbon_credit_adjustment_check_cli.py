"""The scheduled credit check is isolated from interactive credit mutations."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.analytics import carbon_credit_adjustment_check as command


def _connection() -> MagicMock:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = False
    return connection


def test_scheduled_check_uses_read_only_connection_and_one_required_location():
    connection = _connection()
    location_id = uuid4()
    results = [{"credit_code": "KKNT-TEST", "needs_adjustment": True}]

    with (
        patch.object(command, "get_connection", return_value=connection) as get_connection,
        patch.object(command, "check_adjustments", return_value=results) as check_adjustments,
        patch.object(command, "print_json") as print_json,
    ):
        command.main(["--location-id", str(location_id)])

    get_connection.assert_called_once_with(readonly=True)
    check_adjustments.assert_called_once_with(connection, location_id=str(location_id))
    print_json.assert_called_once_with(results)


def test_invalid_location_fails_before_database_access():
    with patch.object(command, "get_connection") as get_connection:
        with pytest.raises(SystemExit) as exc:
            command.main(["--location-id", "not-a-uuid"])

    assert exc.value.code == 2
    get_connection.assert_not_called()


def test_missing_location_fails_before_database_access():
    with patch.object(command, "get_connection") as get_connection:
        with pytest.raises(SystemExit) as exc:
            command.main([])

    assert exc.value.code == 2
    get_connection.assert_not_called()


def test_help_does_not_open_database():
    with patch.object(command, "get_connection") as get_connection:
        with pytest.raises(SystemExit) as exc:
            command.main(["--help"])

    assert exc.value.code == 0
    get_connection.assert_not_called()
