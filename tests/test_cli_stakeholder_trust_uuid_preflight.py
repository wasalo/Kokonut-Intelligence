"""Offline UUID validation for the stakeholder-trust and governance CLI."""

from __future__ import annotations

import sys
from uuid import UUID

import pytest

from services.analytics import cli_stakeholder_trust as cli

_VALID = "A5B3E100-0B5D-4A66-9E90-35C9DA193FE8"
_CANONICAL = str(UUID(_VALID))


@pytest.mark.parametrize(
    "arguments",
    [
        ["record-evidence", "not-a-uuid", "trust", "positive", "survey", "summary"],
        ["record-evidence", "00000000-0000-0000-0000-000000000001", "trust", "positive", "survey", "summary", "--relationship-party-id", "bad"],
        ["record-evidence", "00000000-0000-0000-0000-000000000001", "trust", "positive", "survey", "summary", "--source-id", "bad"],
        ["record-evidence", "00000000-0000-0000-0000-000000000001", "trust", "positive", "survey", "summary", "--created-by-party-id", "bad"],
        ["verify-buyer", "bad", "identity", "document"],
        ["verify-buyer", "00000000-0000-0000-0000-000000000001", "identity", "document", "--verified-by-party-id", "bad"],
        ["profile", "bad"],
        ["timeline", "bad"],
        ["risks", "--party-id", "bad"],
        ["governance-health", "--cooperative-id", "bad"],
    ],
)
def test_malformed_uuid_fails_before_database_access(monkeypatch, arguments, capsys):
    monkeypatch.setattr(sys, "argv", ["stakeholder-trust", *arguments])
    monkeypatch.setattr(
        cli,
        "get_db",
        lambda: pytest.fail("malformed UUID reached PostgreSQL acquisition"),
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "must be a valid UUID" in capsys.readouterr().err


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("arguments", "service_name", "service_args", "service_kwargs"),
    [
        (
            ["record-evidence", _VALID, "trust", "positive", "survey", "summary",
             "--relationship-party-id", _VALID, "--source-id", _VALID,
             "--created-by-party-id", _VALID],
            "record_evidence",
            ("trust", "positive", "survey", "summary"),
            {
                "relationship_party_id": _CANONICAL,
                "source_id": _CANONICAL,
                "source_label": None,
                "confidence": None,
                "uncertainty": None,
                "evidence_hash": None,
                "evidence_cid": None,
                "audience": "internal",
                "created_by_party_id": _CANONICAL,
            },
        ),
        (
            ["verify-buyer", _VALID, "identity", "document", "--verified-by-party-id", _VALID],
            "verify_buyer",
            ("identity", "document"),
            {
                "verified_by_party_id": _CANONICAL,
                "evidence_hash": None,
                "evidence_cid": None,
                "expires_at": None,
            },
        ),
        (["profile", _VALID], "profile", (), {}),
        (["timeline", _VALID], "evidence_timeline", (), {}),
        (["risks", "--party-id", _VALID], "risk_indicators", (), {}),
        (["governance-health", "--cooperative-id", _VALID], "governance_health", (), {}),
    ],
)
def test_valid_uuid_values_are_canonicalized_before_service_call(
    monkeypatch, arguments, service_name, service_args, service_kwargs
):
    connection = _Connection()
    calls = []
    monkeypatch.setattr(sys, "argv", ["stakeholder-trust", *arguments])
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(cli, "out", lambda _value: None)

    def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return {"ok": True}

    owner = cli.governance if service_name == "governance_health" else cli.trust
    monkeypatch.setattr(owner, service_name, capture)

    cli.main()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] is connection
    assert args[1:] == (_CANONICAL, *service_args)
    assert kwargs == service_kwargs
    assert connection.closed


@pytest.mark.parametrize(
    "arguments,service_name",
    [
        (["record-evidence", _VALID, "trust", "positive", "survey", "summary"], "record_evidence"),
        (["verify-buyer", _VALID, "identity", "document"], "verify_buyer"),
        (["risks"], "risk_indicators"),
        (["governance-health"], "governance_health"),
    ],
)
def test_optional_uuid_arguments_remain_none_when_omitted(monkeypatch, arguments, service_name):
    connection = _Connection()
    calls = []
    monkeypatch.setattr(sys, "argv", ["stakeholder-trust", *arguments])
    monkeypatch.setattr(cli, "get_db", lambda: connection)
    monkeypatch.setattr(cli, "out", lambda _value: None)

    def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return {"ok": True}

    owner = cli.governance if service_name == "governance_health" else cli.trust
    monkeypatch.setattr(owner, service_name, capture)
    cli.main()

    args, kwargs = calls[0]
    assert args[0] is connection
    if service_name == "record_evidence":
        assert kwargs["relationship_party_id"] is None
        assert kwargs["source_id"] is None
        assert kwargs["created_by_party_id"] is None
    elif service_name == "verify_buyer":
        assert kwargs["verified_by_party_id"] is None
    elif service_name == "risk_indicators":
        assert args[1] is None
    else:
        assert args[1] is None
    assert connection.closed
