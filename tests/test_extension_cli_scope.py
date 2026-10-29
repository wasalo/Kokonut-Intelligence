"""Location UUID preflight for the hand-written extension-services CLI."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_extension


@pytest.mark.parametrize(
    "argv",
    [
        ["enroll", "--farmer-id", "farmer-1", "--module-id", "module-1", "--location-id", "bad"],
        ["create-peer-group", "--name", "Group", "--topic", "Soil", "--location-id", "bad"],
        ["peer-groups", "--location-id", "bad"],
        ["deliver", "--farmer-id", "farmer-1", "--module-id", "module-1", "--channel", "sms", "--location-id", "bad"],
        ["effectiveness", "--location-id", "bad"],
        ["recommend", "--farmer-id", "farmer-1", "--location-id", "bad"],
    ],
)
def test_location_scoped_commands_reject_bad_uuid_before_database(monkeypatch, argv):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_extension.main(argv)

    assert error.value.code == 2
    get_db.assert_not_called()


def test_peer_groups_preserves_global_mode_when_location_filter_is_omitted(
    monkeypatch, capsys
):
    db = Mock()
    get_db = Mock(return_value=db)
    get_groups = Mock(return_value=[])
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_extension, "get_peer_groups", get_groups)

    cli_extension.main(["peer-groups", "--json"])

    get_db.assert_called_once_with()
    get_groups.assert_called_once_with(db, location_id=None)
    db.close.assert_called_once_with()
    assert capsys.readouterr().out.strip() == "[]"


def test_peer_groups_accepts_valid_location_filter(monkeypatch):
    location_id = str(uuid4())
    db = Mock()
    get_db = Mock(return_value=db)
    get_groups = Mock(return_value=[])
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_extension, "get_peer_groups", get_groups)

    cli_extension.main(["peer-groups", "--location-id", location_id, "--json"])

    get_groups.assert_called_once_with(db, location_id=location_id)
    db.close.assert_called_once_with()


def test_peer_groups_canonicalizes_uppercase_location_filter(monkeypatch):
    location_id = uuid4()
    db = Mock()
    get_db = Mock(return_value=db)
    get_groups = Mock(return_value=[])
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_extension, "get_peer_groups", get_groups)

    cli_extension.main(
        ["peer-groups", "--location-id", str(location_id).upper(), "--json"]
    )

    get_groups.assert_called_once_with(db, location_id=str(location_id))
    db.close.assert_called_once_with()
