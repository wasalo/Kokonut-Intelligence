"""Consent CLI UUIDs are validated before PostgreSQL is opened."""

import sys
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_consent


@pytest.mark.parametrize(
    "argv",
    [
        ["record", "bad-id", "wellbeing", "participation"],
        ["record", str(uuid4()), "wellbeing", "participation", "--scope-id", "bad-id"],
        [
            "record", str(uuid4()), "wellbeing", "participation",
            "--recipient-party-id", "bad-id",
        ],
        ["check", "bad-id", "wellbeing", "participation"],
        ["check", str(uuid4()), "wellbeing", "participation", "--scope-id", "bad-id"],
        ["list", "--party-id", "bad-id"],
        ["withdraw", "bad-id", "--reason", "withdrawn by request"],
    ],
)
def test_invalid_consent_uuid_fails_before_database_open(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["kokonut-consent", *argv])
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(cli_consent, "get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_consent.main()

    assert error.value.code == 2
    get_db.assert_not_called()


def test_valid_uppercase_consent_uuids_are_canonical_before_database_handler(monkeypatch):
    party_id = uuid4()
    scope_id = uuid4()
    recipient_id = uuid4()
    supplied = [party_id.hex.upper(), scope_id.hex.upper(), recipient_id.hex.upper()]
    connection = Mock()
    get_db = Mock(return_value=connection)
    record = Mock(return_value={"consented": True})
    output = Mock()
    monkeypatch.setattr(sys, "argv", [
        "kokonut-consent", "record", supplied[0], "wellbeing", "participation",
        "--scope-type", "location", "--scope-id", supplied[1],
        "--recipient-party-id", supplied[2],
    ])
    monkeypatch.setattr(cli_consent, "get_db", get_db)
    monkeypatch.setattr(cli_consent, "record_consent", record)
    monkeypatch.setattr(cli_consent, "_out", output)

    cli_consent.main()

    record.assert_called_once_with(
        connection, str(party_id), "wellbeing", "participation",
        event_type="grant", scope_type="location", scope_id=str(scope_id),
        recipient_party_id=str(recipient_id), recipient_type="system",
        recipient_name=None, reason=None, source_system="stakeholder_registry",
    )
    output.assert_called_once_with({"consented": True})
    connection.close.assert_called_once_with()
