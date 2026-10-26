"""Isolation checks for the read-only sensor-anomaly ML source worker."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import sensor_anomaly_ml_worker

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"


def test_disabled_worker_fails_before_opening_a_connection():
    with (
        patch.object(
            sensor_anomaly_ml_worker,
            "require_feature",
            side_effect=RuntimeError("feature disabled"),
        ),
        patch.object(sensor_anomaly_ml_worker, "get_worker_db") as get_db,
        pytest.raises(RuntimeError, match="feature disabled"),
    ):
        sensor_anomaly_ml_worker.run_sensor_anomaly_ml(LOCATION_ID)

    get_db.assert_not_called()


def test_invalid_location_fails_before_opening_a_connection():
    with (
        patch.object(sensor_anomaly_ml_worker, "require_feature"),
        patch.object(sensor_anomaly_ml_worker, "get_worker_db") as get_db,
        pytest.raises(ValueError, match="location-id must be a UUID"),
    ):
        sensor_anomaly_ml_worker.run_sensor_anomaly_ml("not-a-uuid")

    get_db.assert_not_called()


def test_worker_sets_signed_scope_then_reader_role_and_rolls_back():
    connection = MagicMock()
    with (
        patch.object(sensor_anomaly_ml_worker, "require_feature") as require_feature,
        patch.object(
            sensor_anomaly_ml_worker, "get_worker_db", return_value=connection
        ) as get_db,
        patch.object(
            sensor_anomaly_ml_worker,
            "get_worker_credential",
            return_value="synthetic-worker-secret-that-is-long-enough",
        ) as get_credential,
        patch.object(
            sensor_anomaly_ml_worker, "set_agent_source_tenant_context"
        ) as set_context,
        patch(
            "services.ingestion.ml_anomaly_detector.run_ml_check",
            return_value={"status": "success", "location_id": LOCATION_ID},
        ) as run_check,
        patch("services.ingestion.ml_anomaly_detector.save_models") as save_models,
    ):
        result = sensor_anomaly_ml_worker.run_sensor_anomaly_ml(
            LOCATION_ID.upper(), sensor_id=SENSOR_ID.upper()
        )

    require_feature.assert_called_once_with("isolated_sensor_anomaly_ml_worker")
    get_db.assert_called_once_with("sensor_anomaly_ml_source")
    get_credential.assert_called_once_with("sensor_anomaly_ml_source")
    set_context.assert_called_once_with(
        connection,
        credential="synthetic-worker-secret-that-is-long-enough",
        location_id=LOCATION_ID,
        resource="sensor_anomaly_ml",
        action="analyze",
    )
    connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SET LOCAL ROLE kokonut_sensor_anomaly_ml_reader"
    )
    run_check.assert_called_once_with(
        connection,
        location_id=LOCATION_ID,
        sensor_id=SENSOR_ID,
        signed_source=True,
    )
    save_models.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
    assert result["status"] == "success"


def test_training_uses_only_the_source_reader_connection():
    connection = MagicMock()
    with (
        patch.object(sensor_anomaly_ml_worker, "require_feature"),
        patch.object(sensor_anomaly_ml_worker, "get_worker_db", return_value=connection),
        patch.object(
            sensor_anomaly_ml_worker,
            "get_worker_credential",
            return_value="synthetic-worker-secret-that-is-long-enough",
        ),
        patch.object(sensor_anomaly_ml_worker, "set_agent_source_tenant_context"),
        patch(
            "services.ingestion.ml_anomaly_detector.save_models",
            return_value={"status": "success", "models_saved": []},
        ) as save_models,
        patch("services.ingestion.ml_anomaly_detector.run_ml_check") as run_check,
    ):
        sensor_anomaly_ml_worker.run_sensor_anomaly_ml(LOCATION_ID, train=True)

    save_models.assert_called_once_with(connection, LOCATION_ID, signed_source=True)
    run_check.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_signed_ml_scan_uses_location_scoped_view_and_rejects_missing_location(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = []
    empty_frame = MagicMock()
    empty_frame.empty = True
    monkeypatch.setattr(
        "services.ingestion.ml_anomaly_detector._query_all_sensors_timeseries",
        MagicMock(return_value=empty_frame),
    )

    with patch("services.ingestion.ml_anomaly_detector._ensure_deps", return_value=True):
        result = __import__(
            "services.ingestion.ml_anomaly_detector", fromlist=["run_ml_check"]
        ).run_ml_check(connection, location_id=LOCATION_ID, signed_source=True)

    query, parameters = cursor.execute.call_args.args
    assert "FROM kokonut_anomaly_ml_source.sensor_reading AS sr" in query
    assert "FROM sensor_reading sr" not in query
    assert "sr.location_id = %s::uuid" in query
    assert parameters == (LOCATION_ID, None, None)
    assert result["location_id"] == LOCATION_ID

    with patch("services.ingestion.ml_anomaly_detector._ensure_deps", return_value=True):
        with pytest.raises(ValueError, match="signed ML analysis requires exactly one location"):
            __import__(
                "services.ingestion.ml_anomaly_detector", fromlist=["run_ml_check"]
            ).run_ml_check(connection, signed_source=True)
