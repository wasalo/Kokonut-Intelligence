"""Location UUID preflight for credit-class CLI operations."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, Mock

import pytest

from services.credit_class import cli


@pytest.mark.parametrize(
    "command_args",
    [
        ["batch", "create", "--class-id", "class", "--location-id", "not-a-uuid",
         "--vintage", "2026", "--quantity", "1"],
        ["batch", "list", "--location-id", "not-a-uuid"],
        ["enrollment", "apply", "--location-id", "not-a-uuid", "--class-id", "class"],
        ["enrollment", "list-by-project", "--location-id", "not-a-uuid"],
    ],
)
def test_location_commands_reject_invalid_scope_before_connection(
    monkeypatch: pytest.MonkeyPatch, command_args: list[str]
) -> None:
    get_connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(cli, "get_connection", get_connection)
    monkeypatch.setattr(sys, "argv", ["credit-class", *command_args])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


@pytest.mark.parametrize(
    "command_args, operation",
    [
        (["batch", "create", "--class-id", "class", "--location-id", "A0000000-0000-0000-0000-000000000001",
          "--vintage", "2026", "--quantity", "1"], "create_batch"),
        (["batch", "list", "--location-id", "A0000000-0000-0000-0000-000000000001"], "list_batches"),
        (["enrollment", "apply", "--location-id", "A0000000-0000-0000-0000-000000000001",
          "--class-id", "class"], "apply_to_class"),
        (["enrollment", "list-by-project", "--location-id", "A0000000-0000-0000-0000-000000000001"],
         "list_enrollments_by_project"),
    ],
)
def test_location_commands_dispatch_canonical_scope(
    monkeypatch: pytest.MonkeyPatch, command_args: list[str], operation: str
) -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    conn = Mock()
    get_connection = MagicMock()
    get_connection.return_value.__enter__.return_value = conn
    monkeypatch.setattr(cli, "get_connection", get_connection)
    monkeypatch.setattr(sys, "argv", ["credit-class", *command_args])

    if operation == "create_batch":
        from services.credit_class import batch_manager

        target = Mock(return_value={})
        monkeypatch.setattr(batch_manager, operation, target)
    elif operation == "list_batches":
        from services.credit_class import batch_manager

        target = Mock(return_value=[])
        monkeypatch.setattr(batch_manager, operation, target)
    else:
        from services.credit_class import enrollment

        target = Mock(return_value=[])
        monkeypatch.setattr(enrollment, operation, target)

    cli.main()

    assert get_connection.call_count == 1
    assert location_id in target.call_args.args or target.call_args.kwargs.get("location_id") == location_id


def test_list_by_project_rejects_invalid_location_before_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(cli, "get_connection", get_connection)
    monkeypatch.setattr(
        sys,
        "argv",
        ["credit-class", "enrollment", "list-by-project", "--location-id", "not-a-uuid"],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    get_connection.assert_not_called()


def test_list_by_project_dispatches_valid_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    conn = Mock()
    get_connection = MagicMock()
    get_connection.return_value.__enter__.return_value = conn
    list_enrollments = Mock(return_value=[{"name": "Synthetic enrollment"}])
    monkeypatch.setattr(cli, "get_connection", get_connection)
    monkeypatch.setattr(
        "services.credit_class.enrollment.list_enrollments_by_project",
        list_enrollments,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["credit-class", "enrollment", "list-by-project", "--location-id", location_id],
    )

    cli.main()

    get_connection.assert_called_once_with()
    list_enrollments.assert_called_once_with(conn, location_id)


def test_list_by_project_help_does_not_open_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(cli, "get_connection", get_connection)
    monkeypatch.setattr(
        sys,
        "argv",
        ["credit-class", "enrollment", "list-by-project", "--help"],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 0
    get_connection.assert_not_called()
