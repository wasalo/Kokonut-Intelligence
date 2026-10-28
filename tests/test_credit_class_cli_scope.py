"""Location UUID preflight for credit-class project enrollment listing."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, Mock

import pytest

from services.credit_class import cli


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
