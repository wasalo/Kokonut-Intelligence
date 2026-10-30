"""The cooperative creation CLI validates tenant scope before DB dispatch."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_cooperative


def test_create_coop_rejects_invalid_location_before_runner(monkeypatch):
    argv = [
        "create-coop",
        "--name",
        "Adelphi cooperative",
        "--type",
        "marketing",
        "--location-id",
        "not-a-uuid",
    ]
    runner = Mock()
    connection_factory = Mock()
    monkeypatch.setattr(cli_cooperative.cli, "run", runner)
    monkeypatch.setattr(cli_cooperative.cli, "_connection_factory", connection_factory)

    with pytest.raises(SystemExit) as error:
        cli_cooperative.main(argv)

    assert error.value.code == 2
    runner.assert_not_called()
    connection_factory.assert_not_called()


def test_create_coop_valid_location_uses_existing_runner(monkeypatch):
    argv = [
        "create-coop",
        "--name",
        "Adelphi cooperative",
        "--type",
        "marketing",
        "--location-id",
        str(uuid4()),
    ]
    runner = Mock(return_value="dispatched")
    monkeypatch.setattr(cli_cooperative.cli, "run", runner)

    assert cli_cooperative.main(argv) == "dispatched"
    runner.assert_called_once_with(argv)


def test_help_still_exits_before_cli_runner(monkeypatch, capsys):
    runner = Mock()
    monkeypatch.setattr(cli_cooperative.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_cooperative.main(["--help"])

    assert error.value.code == 0
    assert "create-coop" in capsys.readouterr().out
    runner.assert_not_called()


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("not-a-datetime", "2026-10-29T11:00:00"),
        ("2026-10-29T10:00:00", "not-a-datetime"),
        ("2026-10-29", "2026-10-30"),
        ("2026-10-29T10:00:00", "2026-10-29T09:00:00"),
        ("2026-10-29T10:00:00Z", "2026-10-29T11:00:00"),
    ],
)
def test_book_asset_rejects_bad_or_reversed_timestamps_before_runner(
    monkeypatch, start, end
):
    argv = [
        "book-asset",
        "--asset-id", "synthetic-asset",
        "--membership-id", "synthetic-member",
        "--start", start,
        "--end", end,
    ]
    runner = Mock()
    monkeypatch.setattr(cli_cooperative.cli, "run", runner)

    with pytest.raises(SystemExit) as error:
        cli_cooperative.main(argv)

    assert error.value.code == 2
    runner.assert_not_called()


def test_book_asset_forwards_valid_iso_timestamps_unchanged(monkeypatch):
    argv = [
        "book-asset",
        "--asset-id", "synthetic-asset",
        "--membership-id", "synthetic-member",
        "--start", "2026-10-29T09:00:00-04:00",
        "--end", "2026-10-29T14:00:00Z",
    ]
    runner = Mock(return_value="dispatched")
    monkeypatch.setattr(cli_cooperative.cli, "run", runner)

    assert cli_cooperative.main(argv) == "dispatched"
    runner.assert_called_once_with(argv)
