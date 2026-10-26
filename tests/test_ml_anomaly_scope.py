"""Location and sensor scope regressions for ML anomaly checks."""

from unittest.mock import MagicMock

from services.ingestion import ml_anomaly_detector

LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
SENSOR_A = "a0000000-0000-0000-0000-000000000011"


class _Frame:
    def __init__(self, count: int, *, empty: bool = False):
        self.count = count
        self.empty = empty

    def __len__(self):
        return self.count


def _sensor_row(location_id: str, sensor_id: str, slug: str) -> dict[str, str]:
    return {
        "location_id": location_id,
        "sensor_type": "soil_moisture",
        "sensor_id": sensor_id,
        "device_slug": slug,
    }


def test_all_locations_ml_check_loads_and_scores_each_location_separately(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = [
        _sensor_row(LOCATION_A, SENSOR_A, "sensor-a"),
        _sensor_row(LOCATION_B, "a0000000-0000-0000-0000-000000000012", "sensor-b"),
    ]
    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    time_series_queries = MagicMock(return_value=_Frame(100))
    monkeypatch.setattr(ml_anomaly_detector, "_query_sensor_timeseries", time_series_queries)
    multivariate_queries = MagicMock(return_value=_Frame(50))
    monkeypatch.setattr(
        ml_anomaly_detector, "_query_all_sensors_timeseries", multivariate_queries
    )
    model_loads = MagicMock(return_value={"prophet": {}, "iforest": None})
    monkeypatch.setattr(ml_anomaly_detector, "load_models", model_loads)
    monkeypatch.setattr(
        ml_anomaly_detector,
        "fit_prophet",
        lambda _conn, location_id, sensor_type, **_kwargs: f"{location_id}:{sensor_type}",
    )
    monkeypatch.setattr(
        ml_anomaly_detector,
        "predict_anomalies_prophet",
        lambda _model, _frame, sensor_type: [
            {"timestamp": "2026-10-26T12:00:00", "detection_method": "ml_prophet",
             "sensor_type": sensor_type}
        ],
    )
    fit_iforest = MagicMock(return_value="location-forest")
    monkeypatch.setattr(ml_anomaly_detector, "fit_isolation_forest", fit_iforest)
    monkeypatch.setattr(
        ml_anomaly_detector,
        "score_anomalies_iforest",
        lambda *_args, **_kwargs: [
            {"timestamp": "2026-10-26T12:00:00", "detection_method": "ml_isolation_forest"}
        ],
    )

    result = ml_anomaly_detector.run_ml_check(connection)

    assert result["sensors_checked"] == 2
    assert result["anomalies_detected"] == 4
    assert {item["location_id"] for item in result["anomalies"]} == {LOCATION_A, LOCATION_B}
    assert {call.args[0] for call in model_loads.call_args_list} == {LOCATION_A, LOCATION_B}
    assert {call.args[1] for call in fit_iforest.call_args_list} == {LOCATION_A, LOCATION_B}
    assert {call.args[1] for call in multivariate_queries.call_args_list} == {
        LOCATION_A, LOCATION_B
    }
    assert {call.args[1] for call in time_series_queries.call_args_list} == {
        LOCATION_A, LOCATION_B
    }
    assert all(call.kwargs["sensor_id"] is None for call in time_series_queries.call_args_list)


def test_sensor_specific_ml_check_filters_source_and_skips_multivariate_scan(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = [_sensor_row(LOCATION_A, SENSOR_A, "sensor-a")]
    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    time_series_queries = MagicMock(return_value=_Frame(100))
    monkeypatch.setattr(ml_anomaly_detector, "_query_sensor_timeseries", time_series_queries)
    multivariate_query = MagicMock()
    monkeypatch.setattr(ml_anomaly_detector, "_query_all_sensors_timeseries", multivariate_query)
    monkeypatch.setattr(
        ml_anomaly_detector,
        "load_models",
        lambda *_args, **_kwargs: {"prophet": {}, "iforest": object()},
    )
    monkeypatch.setattr(ml_anomaly_detector, "fit_prophet", lambda *_args, **_kwargs: None)

    result = ml_anomaly_detector.run_ml_check(
        connection, location_id=LOCATION_A, sensor_id=SENSOR_A
    )

    assert result["status"] == "success"
    assert time_series_queries.call_args.args[1:3] == (LOCATION_A, "soil_moisture")
    assert time_series_queries.call_args.kwargs["sensor_id"] == SENSOR_A
    assert "sr.location_id" in cursor.execute.call_args.args[0]
    assert "sr.sensor_id" in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1] == (LOCATION_A, LOCATION_A, SENSOR_A, SENSOR_A)
    multivariate_query.assert_not_called()


def test_ml_anomaly_query_accepts_optional_sensor_filter(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(ml_anomaly_detector, "_pd", pd)
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = []

    result = ml_anomaly_detector._query_sensor_timeseries(
        connection, LOCATION_A, "soil_moisture", sensor_id=SENSOR_A
    )

    assert result.empty
    assert "sensor_id = %s::uuid" in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1] == (
        LOCATION_A, "soil_moisture", SENSOR_A, SENSOR_A, 90
    )
