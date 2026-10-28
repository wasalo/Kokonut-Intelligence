"""Grievance CLI location scope is validated before database access."""

import sys
from types import SimpleNamespace

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
