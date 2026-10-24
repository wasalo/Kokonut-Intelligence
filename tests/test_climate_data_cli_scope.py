"""Manual climate ingestion validates a single location before DB access."""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from services.ingestion import climate_data


def test_invalid_location_fails_before_database_or_provider_access():
    with (
        patch.object(climate_data, "get_db") as get_db,
        patch.object(climate_data, "fetch_worldclim") as fetch_worldclim,
        pytest.raises(SystemExit) as exc,
    ):
        climate_data.main(["--worldclim", "--location-id", "not-a-uuid"])

    assert exc.value.code == 2
    get_db.assert_not_called()
    fetch_worldclim.assert_not_called()


def test_cli_passes_canonical_location_id_to_selected_fetcher():
    location_id = str(uuid4())
    db = MagicMock()
    with (
        patch.object(climate_data, "get_db", return_value=db),
        patch.object(climate_data, "fetch_modis", return_value={"status": "success"}) as fetch,
        patch.object(climate_data, "print_json"),
    ):
        result = climate_data.main(["--modis", "--location-id", location_id.upper()])

    assert result == 0
    fetch.assert_called_once_with(db, str(UUID(location_id)))
    db.close.assert_called_once_with()


def test_cli_rejects_conflicting_dataset_modes_before_database_access():
    with patch.object(climate_data, "get_db") as get_db, pytest.raises(SystemExit) as exc:
        climate_data.main(
            ["--all", "--worldclim", "--location-id", str(uuid4())]
        )

    assert exc.value.code == 2
    get_db.assert_not_called()


def test_no_dataset_mode_prints_help_without_database_access(capsys):
    with patch.object(climate_data, "get_db") as get_db:
        result = climate_data.main(["--location-id", "not-a-uuid"])

    assert result == 1
    assert "--worldclim" in capsys.readouterr().out
    get_db.assert_not_called()
