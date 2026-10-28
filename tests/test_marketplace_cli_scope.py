"""Location UUID preflight for the hand-written marketplace CLI."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_marketplace


@pytest.mark.parametrize(
    "argv",
    [
        ["create-listing", "--location-id", "bad", "--crop", "yuca", "--quantity", "1"],
        ["market-overview", "--location-id", "bad"],
        ["create-alert", "--location-id", "bad", "--crop", "yuca", "--threshold", "1"],
        ["list-active", "--location-id", "bad"],
    ],
)
def test_location_scoped_commands_reject_bad_uuid_before_database(monkeypatch, argv):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_marketplace.main(argv)

    assert error.value.code == 2
    get_db.assert_not_called()


def test_list_active_keeps_unscoped_mode_when_location_filter_is_omitted(
    monkeypatch, capsys
):
    db = Mock()
    get_db = Mock(return_value=db)
    list_active = Mock(return_value={"total": 0, "listings": []})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "list_active_listings", list_active)

    cli_marketplace.main(["list-active", "--json"])

    get_db.assert_called_once_with()
    list_active.assert_called_once_with(db, None, None, 50, 0)
    db.close.assert_called_once_with()
    assert capsys.readouterr().out.strip() == '{\n  "total": 0,\n  "listings": []\n}'


def test_list_active_accepts_valid_location_filter(monkeypatch):
    location_id = str(uuid4())
    db = Mock()
    get_db = Mock(return_value=db)
    list_active = Mock(return_value={"total": 0, "listings": []})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "list_active_listings", list_active)

    cli_marketplace.main(["list-active", "--location-id", location_id, "--json"])

    list_active.assert_called_once_with(db, location_id, None, 50, 0)
    db.close.assert_called_once_with()
