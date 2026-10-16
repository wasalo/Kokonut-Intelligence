"""Tests for services.ingestion.anomaly_detector — sensor alert engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_anomaly_detector_evaluate_rule_gt():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(50.0, "gt", 40.0) is True
    assert evaluate_rule(30.0, "gt", 40.0) is False


def test_anomaly_detector_evaluate_rule_lt():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(5.0, "lt", 15.0) is True
    assert evaluate_rule(20.0, "lt", 15.0) is False


def test_anomaly_detector_evaluate_rule_eq():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(10.0, "eq", 10.0) is True
    assert evaluate_rule(10.1, "eq", 10.0) is False


def test_anomaly_detector_evaluate_rule_outside_range():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(3.0, "outside_range", 5.0, threshold_max=95.0) is True
    assert evaluate_rule(50.0, "outside_range", 5.0, threshold_max=95.0) is False
    assert evaluate_rule(96.0, "outside_range", 5.0, threshold_max=95.0) is True


def test_anomaly_detector_evaluate_rule_unknown_operator():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(10.0, "bogus_op", 5.0) is False


def test_anomaly_detector_default_rules_have_required_keys():
    from services.ingestion.anomaly_detector import DEFAULT_ALERT_RULES

    for rule in DEFAULT_ALERT_RULES:
        assert "name" in rule
        assert "sensor_type_name" in rule
        assert "metric" in rule
        assert "operator" in rule
        assert "threshold_value" in rule
        assert "severity" in rule


def test_anomaly_detector_evaluate_metric_value_type():
    from services.ingestion.anomaly_detector import evaluate_metric

    db = MagicMock()
    rule = {"operator": "gt", "threshold_value": 40.0}
    result = evaluate_metric("value", 50.0, rule, db, "sensor-1", "air_temperature")
    assert result is True


def test_anomaly_detector_evaluate_metric_rate_returns_false_on_no_history():
    from services.ingestion.anomaly_detector import evaluate_metric

    db = MagicMock()
    rule = {"operator": "lt", "threshold_value": -5.0}

    with patch("services.ingestion.anomaly_detector.compute_rate_of_change", return_value=None):
        result = evaluate_metric("rate_of_change", 25.0, rule, db, "sensor-1", "soil_moisture")
    assert result is False


def test_sensor_reading_handler_rejects_missing_or_malformed_location_before_database_access():
    from services.ingestion.anomaly_detector import handle_sensor_reading

    payload = {"sensor_id": "sensor-1"}
    with patch("services.ingestion.anomaly_detector.run_check") as run_check:
        with pytest.raises(ValueError, match="require location_id"):
            handle_sensor_reading("sensor_reading", payload, event_id="event-1")
        payload["location_id"] = "not-a-uuid"
        with pytest.raises(ValueError, match="location_id must be a UUID"):
            handle_sensor_reading("sensor_reading", payload, event_id="event-1")

    run_check.assert_not_called()


def test_sensor_reading_handler_passes_canonical_location_to_source_check():
    from services.ingestion.anomaly_detector import handle_sensor_reading

    location_id = "A0000000-0000-0000-0000-000000000001"
    with patch("services.ingestion.anomaly_detector.run_check") as run_check:
        handle_sensor_reading(
            "sensor_reading",
            {"sensor_id": "sensor-1", "location_id": location_id},
            event_id="event-1",
        )

    run_check.assert_called_once_with(
        sensor_id="sensor-1",
        location_id=location_id.lower(),
        event_id="event-1",
    )


@pytest.mark.parametrize("location_id", [None, "not-a-uuid"])
def test_event_run_check_rejects_invalid_location_before_opening_database(location_id):
    from services.ingestion.anomaly_detector import run_check

    with patch("services.ingestion.anomaly_detector.get_db") as get_db:
        with pytest.raises(ValueError, match="valid event and location UUIDs"):
            run_check(event_id="a0000000-0000-0000-0000-000000000002", location_id=location_id)

    get_db.assert_not_called()


def test_event_run_check_filters_source_reading_by_location_and_stops_on_mismatch():
    from services.ingestion.anomaly_detector import run_check

    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    event_id = "a0000000-0000-0000-0000-000000000002"
    location_id = "a0000000-0000-0000-0000-000000000001"

    with patch("services.ingestion.anomaly_detector.get_db", return_value=db):
        with pytest.raises(ValueError, match="no matching source reading"):
            run_check(event_id=event_id, location_id=location_id)

    statement, params = cursor.execute.call_args.args
    assert "sr.location_id = %s::uuid" in statement
    assert params == (event_id, location_id)
    db.close.assert_called_once()


def test_event_run_check_accepts_source_reading_at_requested_location():
    from services.ingestion.anomaly_detector import run_check

    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (
        "reading-1", "sensor-1", "soil_moisture", 12.5, None, None,
        "a0000000-0000-0000-0000-000000000001", None,
    )
    cursor.fetchall.return_value = []
    event_id = "a0000000-0000-0000-0000-000000000002"
    location_id = "a0000000-0000-0000-0000-000000000001"

    with (
        patch("services.ingestion.anomaly_detector.get_db", return_value=db),
        patch("services.ingestion.anomaly_detector.ensure_alert_rules"),
    ):
        run_check(sensor_id="sensor-1", event_id=event_id, location_id=location_id)

    assert cursor.execute.call_count == 2
    assert cursor.execute.call_args_list[0].args[1] == (event_id, location_id)
    db.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
