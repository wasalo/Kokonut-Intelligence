"""Location scope is validated before traceability CLI database setup."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.analytics import cli_traceability


@pytest.mark.parametrize(
    "argv",
    (
        ["create-batch", "--location-id", "not-a-uuid", "--crop", "cassava", "--quantity", "2"],
        ["certs", "--location-id", "not-a-uuid"],
    ),
)
def test_traceability_cli_rejects_invalid_location_before_cli_runner(argv, monkeypatch):
    run = Mock()
    monkeypatch.setattr(cli_traceability.cli, "run", run)

    with pytest.raises(SystemExit) as error:
        cli_traceability.main(argv)

    assert error.value.code == 2
    run.assert_not_called()


def test_traceability_cli_preserves_help_without_opening_database(monkeypatch, capsys):
    run = Mock()
    monkeypatch.setattr(cli_traceability.cli, "run", run)

    with pytest.raises(SystemExit) as error:
        cli_traceability.main(["--help"])

    assert error.value.code == 0
    assert "create-batch" in capsys.readouterr().out
    run.assert_not_called()


@pytest.mark.parametrize("harvest_date", ["not-a-date", "2023-02-29", "20261029"])
def test_create_batch_rejects_invalid_harvest_date_before_cli_runner(
    harvest_date, monkeypatch
):
    argv = [
        "create-batch", "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "--crop", "cassava", "--quantity", "2", "--harvest-date", harvest_date,
    ]
    run = Mock()
    monkeypatch.setattr(cli_traceability.cli, "run", run)

    with pytest.raises(SystemExit) as error:
        cli_traceability.main(argv)

    assert error.value.code == 2
    run.assert_not_called()


def test_create_batch_forwards_canonical_harvest_date_unchanged(monkeypatch):
    argv = [
        "create-batch", "--location-id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "--crop", "cassava", "--quantity", "2", "--harvest-date", "2024-02-29",
    ]
    run = Mock(return_value="dispatched")
    monkeypatch.setattr(cli_traceability.cli, "run", run)

    assert cli_traceability.main(argv) == "dispatched"
    run.assert_called_once_with(argv)
