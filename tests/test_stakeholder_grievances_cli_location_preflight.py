"""Grievance CLI location scope is validated before database access."""

import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_stakeholder_grievances as cli

LOCATION_ID = "A0000000-0000-4000-8000-000000000001"
CANONICAL_LOCATION_ID = "a0000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize("location_id", ["not-a-uuid", "", "all"])
def test_create_case_rejects_invalid_location_before_database(monkeypatch, location_id):
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("invalid location must fail before database access"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["stakeholder-grievances", "create-case", "safety", "Synthetic case", "--location-id", location_id],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


def test_create_case_canonicalizes_location_before_dispatch(monkeypatch):
    calls = []
    conn = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(cli, "get_db", lambda: conn)
    monkeypatch.setattr(cli, "create_case", lambda _conn, *_args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(cli, "_out", lambda _result: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stakeholder-grievances", "create-case", "safety", "Synthetic case", "--location-id", LOCATION_ID],
    )

    cli.main()

    assert calls == [{
        "feedback_id": None,
        "complainant_party_id": None,
        "affected_party_id": None,
        "location_id": CANONICAL_LOCATION_ID,
        "severity": "medium",
        "confidentiality": "restricted",
        "protected_details": None,
        "retaliation_risk": False,
        "owner_party_id": None,
        "due_at": None,
        "work_item_id": None,
    }]


def test_create_case_without_location_preserves_optional_scope(monkeypatch):
    calls = []
    conn = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(cli, "get_db", lambda: conn)
    monkeypatch.setattr(cli, "create_case", lambda _conn, *_args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(cli, "_out", lambda _result: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stakeholder-grievances", "create-case", "safety", "Synthetic case"],
    )

    cli.main()

    assert calls[0]["location_id"] is None


@pytest.mark.parametrize(
    "argv",
    [
        ["create-case", "safety", "Synthetic case", "--due-at", "not-a-time"],
        ["create-case", "safety", "Synthetic case", "--due-at", "2026-02-30T12:00:00Z"],
        ["create-case", "safety", "Synthetic case", "--due-at", "2026-10-29T12:00:00"],
        ["propose-remedy", str(uuid4()), "repair", "A bounded repair", "--due-at", "not-a-time"],
        ["propose-remedy", str(uuid4()), "repair", "A bounded repair", "--due-at", "2026-02-30T12:00:00Z"],
        ["propose-remedy", str(uuid4()), "repair", "A bounded repair", "--due-at", "2026-10-29T12:00:00"],
    ],
)
def test_invalid_due_at_fails_before_database(monkeypatch, argv):
    database = Mock()
    monkeypatch.setattr(sys, "argv", ["stakeholder-grievances", *argv])
    monkeypatch.setattr(cli, "get_db", database)

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    database.assert_not_called()


@pytest.mark.parametrize(
    ("argv", "service_name", "keyword"),
    [
        (
            ["create-case", "safety", "Synthetic case", "--due-at", "2026-10-29T12:30:00-04:00"],
            "create_case",
            "due_at",
        ),
        (
            ["propose-remedy", str(uuid4()), "repair", "A bounded repair", "--due-at", "2026-10-29T12:30:00Z"],
            "propose_remedy",
            "due_at",
        ),
    ],
)
def test_valid_due_at_is_forwarded_as_aware_datetime(monkeypatch, argv, service_name, keyword):
    closed = []
    connection = SimpleNamespace(close=lambda: closed.append(True))
    service = Mock(return_value={"ok": True})
    monkeypatch.setattr(sys, "argv", ["stakeholder-grievances", *argv])
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(cli, "_out", lambda _result: None)
    monkeypatch.setattr(cli, service_name, service)

    cli.main()

    due_at = service.call_args.kwargs[keyword]
    assert isinstance(due_at, datetime)
    assert due_at.tzinfo is not None and due_at.utcoffset() is not None
    assert due_at.isoformat() == datetime.fromisoformat(argv[-1].replace("Z", "+00:00")).isoformat()
    assert closed == [True]


@pytest.mark.parametrize(
    ("argv", "service_name"),
    [
        (["create-case", "safety", "Synthetic case"], "create_case"),
        (["propose-remedy", str(uuid4()), "repair", "A bounded repair"], "propose_remedy"),
    ],
)
def test_omitted_due_at_remains_none(monkeypatch, argv, service_name):
    closed = []
    connection = SimpleNamespace(close=lambda: closed.append(True))
    service = Mock(return_value={"ok": True})
    monkeypatch.setattr(sys, "argv", ["stakeholder-grievances", *argv])
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(cli, "_out", lambda _result: None)
    monkeypatch.setattr(cli, service_name, service)

    cli.main()

    assert service.call_args.kwargs["due_at"] is None
    assert closed == [True]
