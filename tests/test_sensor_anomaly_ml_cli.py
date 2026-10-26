"""The standalone ML worker CLI rejects invalid scope before worker access."""

import json
from unittest.mock import patch

import pytest

from services.ingestion import sensor_anomaly_ml_cli

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"


def test_check_requires_one_location_before_worker_access():
    with (
        patch(
            "services.ingestion.sensor_anomaly_ml_worker.run_sensor_anomaly_ml"
        ) as run_worker,
        pytest.raises(SystemExit, match="2"),
    ):
        sensor_anomaly_ml_cli.main(["--ml-check"])

    run_worker.assert_not_called()


def test_invalid_location_is_rejected_before_worker_access():
    with (
        patch(
            "services.ingestion.sensor_anomaly_ml_worker.run_sensor_anomaly_ml"
        ) as run_worker,
        pytest.raises(SystemExit, match="2"),
    ):
        sensor_anomaly_ml_cli.main(["--ml-check", "--location-id", "invalid"])

    run_worker.assert_not_called()


def test_check_passes_canonical_location_and_sensor_to_worker(capsys):
    with patch(
        "services.ingestion.sensor_anomaly_ml_worker.run_sensor_anomaly_ml",
        return_value={"status": "success", "location_id": LOCATION_ID},
    ) as run_worker:
        sensor_anomaly_ml_cli.main(
            [
                "--ml-check",
                "--location-id",
                LOCATION_ID.upper(),
                "--sensor",
                SENSOR_ID.upper(),
            ]
        )

    run_worker.assert_called_once_with(
        LOCATION_ID, sensor_id=SENSOR_ID, train=False
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "success",
        "location_id": LOCATION_ID,
    }


def test_training_passes_single_location_and_rejects_sensor_filter():
    with patch(
        "services.ingestion.sensor_anomaly_ml_worker.run_sensor_anomaly_ml",
        return_value={"status": "success", "models_saved": []},
    ) as run_worker:
        sensor_anomaly_ml_cli.main(["--ml-train", "--location-id", LOCATION_ID])

    run_worker.assert_called_once_with(LOCATION_ID, sensor_id=None, train=True)

    with (
        patch(
            "services.ingestion.sensor_anomaly_ml_worker.run_sensor_anomaly_ml"
        ) as run_worker,
        pytest.raises(SystemExit, match="2"),
    ):
        sensor_anomaly_ml_cli.main(
            [
                "--ml-train",
                "--location-id",
                LOCATION_ID,
                "--sensor",
                SENSOR_ID,
            ]
        )

    run_worker.assert_not_called()


def test_aggregate_location_selector_is_not_supported():
    with (
        patch(
            "services.ingestion.sensor_anomaly_ml_worker.run_sensor_anomaly_ml"
        ) as run_worker,
        pytest.raises(SystemExit, match="2"),
    ):
        sensor_anomaly_ml_cli.main(["--ml-check", "--all-locations"])

    run_worker.assert_not_called()
