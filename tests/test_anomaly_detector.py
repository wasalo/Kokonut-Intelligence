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
    assert "e.payload ->> 'location_id' = %s" in statement
    assert "e.payload ->> 'sensor_id' = sr.sensor_id::TEXT" in statement
    assert "e.payload ->> 'sensor_device_id' = sr.sensor_id::TEXT" in statement
    assert params == (event_id, location_id, location_id)
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
    assert cursor.execute.call_args_list[0].args[1] == (event_id, location_id, location_id)
    db.close.assert_called_once()


def test_event_run_check_does_not_bootstrap_shared_alert_rules():
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
        patch("services.ingestion.anomaly_detector.ensure_alert_rules") as ensure_rules,
    ):
        run_check(sensor_id="sensor-1", event_id=event_id, location_id=location_id)

    ensure_rules.assert_not_called()
    db.close.assert_called_once()


def test_create_alert_records_the_authoritative_location_and_rejects_stale_device_scope():
    from services.ingestion.anomaly_detector import create_alert

    location_id = "a0000000-0000-0000-0000-000000000001"
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("alert-1",)

    result = create_alert(
        db, "device-1", "rule-1", "reading-1", "warning", "Synthetic alert",
        12.5, 15.0, location_id=location_id,
    )

    assert result == "alert-1"
    statement, parameters = cursor.execute.call_args.args
    assert "COALESCE(%s::uuid, device.location_id)" in statement
    assert "device.location_id = %s::uuid" in statement
    assert "reading.sensor_id::text = device.id::text" in statement
    assert "reading.location_id = device.location_id" in statement
    assert parameters[0] == location_id
    assert parameters[-4:] == (location_id, location_id, location_id, "reading-1")

    cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match="not assigned to the source location"):
        create_alert(
            db, "device-1", "rule-1", "reading-1", "warning", "Synthetic alert",
            12.5, 15.0, location_id=location_id,
        )


def test_ingestion_log_writer_persists_optional_location_lineage():
    from services.ingestion.base import log_ingestion

    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    location_id = "a0000000-0000-0000-0000-000000000001"

    log_ingestion(
        source_system="anomaly_detector",
        source_table="sensor_reading",
        source_id="reading-1",
        target_table="sensor_alert",
        target_id="alert-1",
        operation="insert",
        payload_hash="a" * 64,
        db=db,
        location_id=location_id,
    )

    statement, parameters = cursor.execute.call_args.args
    assert "dedupe_key, location_id)" in statement
    assert parameters[-1] == location_id
    db.commit.assert_not_called()
    db.close.assert_not_called()


def test_anomaly_cooldown_query_can_be_scoped_to_location():
    from services.ingestion.anomaly_detector import check_cooldown

    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    location_id = "a0000000-0000-0000-0000-000000000001"

    assert check_cooldown(db, "rule-1", "device-1", 30, location_id=location_id) is False

    statement, parameters = cursor.execute.call_args.args
    assert "location_id = %s::uuid" in statement
    assert parameters == ("rule-1", "device-1", location_id, location_id)


def test_interactive_run_check_keeps_default_alert_rule_bootstrap():
    from services.ingestion.anomaly_detector import run_check

    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []

    with (
        patch("services.ingestion.anomaly_detector.get_db", return_value=db),
        patch("services.ingestion.anomaly_detector.ensure_alert_rules") as ensure_rules,
    ):
        run_check()

    ensure_rules.assert_called_once_with(db)
    db.close.assert_called_once()


def test_anomaly_event_publishes_without_committing_the_handler_transaction():
    from datetime import datetime, timezone

    from services.ingestion.anomaly_detector import run_check

    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        (
            "reading-1", "sensor-1", "soil_moisture", 12.5, None, None,
            "a0000000-0000-0000-0000-000000000001", None,
        ),
        ("reading-1",),
        ("sensor-1",),
        (None, datetime.now(timezone.utc)),
    ]
    cursor.fetchall.return_value = [
        (
            "rule-1", "Soil Moisture Low", "type-1", "soil_moisture", "value",
            "lt", 15.0, None, "warning", 0, False, None,
        ),
    ]
    event_bus = MagicMock()
    location_id = "a0000000-0000-0000-0000-000000000001"
    event_id = "a0000000-0000-0000-0000-000000000002"

    with (
        patch("services.ingestion.anomaly_detector.get_db", return_value=db),
        patch("services.ingestion.anomaly_detector.ensure_alert_rules"),
        patch("services.ingestion.anomaly_detector.check_cooldown", return_value=False),
        patch("services.ingestion.anomaly_detector.evaluate_metric", return_value=True),
        patch("services.ingestion.anomaly_detector.create_alert", return_value="alert-1"),
        patch("services.ingestion.anomaly_detector.log_ingestion") as log_ingestion,
        patch(
            "services.ingestion.anomaly_detector.get_sensor_device_info",
            return_value={
                "sensor_name": "Sensor 1",
                "sensor_type": "soil_moisture",
                "location_name": "Test Farm",
                "location_id": location_id,
            },
        ),
        patch("services.events.notification_outbox.enqueue_event_notification") as enqueue_notification,
        patch("services.ingestion.anomaly_detector.send_actuation_commands"),
        patch("services.events.bus.EventBus", return_value=event_bus),
    ):
        run_check(sensor_id="sensor-1", event_id=event_id, location_id=location_id)

    event_bus.publish.assert_called_once()
    assert event_bus.publish.call_args.kwargs["commit"] is False
    effect_insert = next(
        call for call in cursor.execute.call_args_list
        if "INSERT INTO sensor_anomaly_effect" in call.args[0]
    )
    assert effect_insert.args[1] == (location_id, "reading-1", "rule-1", event_id)
    log_ingestion.assert_called_once()
    assert log_ingestion.call_args.kwargs["location_id"] == location_id
    enqueue_notification.assert_called_once()
    assert enqueue_notification.call_args.kwargs["location_id"] == location_id
    db.commit.assert_called_once()
    db.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
