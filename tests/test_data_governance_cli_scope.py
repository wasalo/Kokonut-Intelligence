"""Data governance location filters reject malformed scope before DB setup."""

from unittest.mock import Mock

import pytest

from services.analytics import cli_data_governance


@pytest.mark.parametrize(
    "argv",
    [
        ["record-consent", "--farmer-id", "farmer", "--data-category", "soil", "--scope", "collection", "--location-id", "bad"],
        ["log-access", "--accessor-id", "operator", "--data-category", "soil", "--resource-type", "plot", "--access-type", "read", "--location-id", "bad"],
        ["request-portability", "--farmer-id", "farmer", "--location-id", "bad"],
        ["set-retention", "--data-category", "soil", "--actor", "operator", "--reason", "review", "--location-id", "bad"],
        ["retention-policies", "--location-id", "bad"],
        ["governance-summary", "--location-id", "bad"],
    ],
)
def test_location_filters_reject_invalid_uuid_before_connection(monkeypatch, argv, capsys):
    connection_calls = []

    def connect():
        connection_calls.append(True)
        raise AssertionError("database connection must not be opened")

    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", connect)

    with pytest.raises(SystemExit) as exc_info:
        cli_data_governance.main(argv)

    assert exc_info.value.code == 2
    assert "--location-id must be a valid UUID" in capsys.readouterr().err
    assert connection_calls == []


def test_unscoped_retention_inventory_is_still_allowed(monkeypatch):
    connection = Mock()
    handler = Mock(return_value=[])
    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", lambda: connection)
    monkeypatch.setattr(cli_data_governance, "list_retention_policies", handler)

    cli_data_governance.main(["retention-policies"])

    handler.assert_called_once_with(
        connection,
        status=None,
        data_category=None,
        jurisdiction_code=None,
        purpose_code=None,
        location_id=None,
        limit=100,
    )
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    ("location_args", "expected_location_args"),
    [
        (
            ["--location-id", "A0000000-0000-4000-8000-000000000001"],
            ["--location-id", "a0000000-0000-4000-8000-000000000001"],
        ),
        (
            ["--location-id=A0000000-0000-4000-8000-000000000001"],
            ["--location-id=a0000000-0000-4000-8000-000000000001"],
        ),
    ],
)
def test_valid_location_filter_is_canonicalized_before_runner(
    monkeypatch, location_args, expected_location_args
):
    runner = Mock()
    monkeypatch.setattr(cli_data_governance, "run", runner)

    cli_data_governance.main(["retention-policies", *location_args])

    runner.assert_called_once_with(
        cli_data_governance.cli.main,
        ["retention-policies", *expected_location_args],
    )


@pytest.mark.parametrize(
    "expires_at",
    ["not-a-datetime", "2027-01-15T10:30:00"],
    ids=["malformed", "timezone-naive"],
)
def test_consent_expiry_rejects_invalid_or_naive_values_before_connection(
    monkeypatch, capsys, expires_at
):
    connection_calls = []

    def connect():
        connection_calls.append(True)
        raise AssertionError("invalid consent expiry must fail before DB access")

    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", connect)

    with pytest.raises(SystemExit) as exc_info:
        cli_data_governance.main([
            "record-consent",
            "--farmer-id", "farmer",
            "--data-category", "soil",
            "--scope", "collection",
            "--expires-at", expires_at,
        ])

    assert exc_info.value.code == 2
    assert "expiry must be an ISO-8601 datetime with a timezone" in capsys.readouterr().err
    assert connection_calls == []


@pytest.mark.parametrize(
    ("expiry_args", "expected_expiry"),
    [
        (["--expires-at", "2027-01-15T10:30:00+02:00"], "2027-01-15T10:30:00+02:00"),
        ([], None),
    ],
    ids=["aware-expiry", "no-expiry"],
)
def test_record_consent_receives_parsed_expiry(monkeypatch, expiry_args, expected_expiry):
    connection = Mock()
    handler = Mock(return_value={"consent_id": "consent-id"})
    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", lambda: connection)
    monkeypatch.setattr(cli_data_governance, "record_consent", handler)

    cli_data_governance.main([
        "record-consent",
        "--farmer-id", "farmer",
        "--data-category", "soil",
        "--scope", "collection",
        *expiry_args,
    ])

    expiry = handler.call_args.kwargs["expires_at"]
    if expected_expiry is None:
        assert expiry is None
    else:
        from datetime import datetime

        assert isinstance(expiry, datetime)
        assert expiry.isoformat() == expected_expiry
    connection.close.assert_called_once()
