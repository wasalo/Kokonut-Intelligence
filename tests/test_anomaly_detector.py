"""Tests for services.ingestion.anomaly_detector — sensor alert engine."""

from __future__ import annotations

from datetime import datetime, timezone
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
    with patch("services.ingestion.sensor_anomaly_worker.process_sensor_reading") as process:
        with pytest.raises(ValueError, match="require location_id"):
            handle_sensor_reading("sensor_reading", payload, event_id="event-1")
        payload["location_id"] = "not-a-uuid"
        with pytest.raises(ValueError, match="location_id must be a UUID"):
            handle_sensor_reading("sensor_reading", payload, event_id="event-1")

    process.assert_not_called()


def test_sensor_reading_handler_passes_canonical_location_to_source_check():
    from services.ingestion.anomaly_detector import handle_sensor_reading

    location_id = "A0000000-0000-0000-0000-000000000001"
    with patch("services.ingestion.sensor_anomaly_worker.process_sensor_reading") as process:
        handle_sensor_reading(
            "sensor_reading",
            {"sensor_id": "sensor-1", "location_id": location_id},
            event_id="event-1",
        )

    process.assert_called_once_with(
        sensor_id="sensor-1",
        location_id=location_id.lower(),
        event_id="event-1",
    )


def test_event_run_check_refuses_the_shared_database_path():
    from services.ingestion.anomaly_detector import run_check

    with patch("services.ingestion.anomaly_detector.get_db") as get_db:
        with pytest.raises(ValueError, match="must use handle_sensor_reading"):
            run_check(
                event_id="a0000000-0000-0000-0000-000000000002",
                location_id="a0000000-0000-0000-0000-000000000001",
            )

    get_db.assert_not_called()


def test_worker_validates_event_location_and_sensor_before_loading_credentials():
    from services.ingestion.sensor_anomaly_worker import process_sensor_reading

    with (
        patch("services.ingestion.sensor_anomaly_worker.get_worker_credential") as credential,
        patch("services.ingestion.sensor_anomaly_worker.get_worker_db") as get_db,
    ):
        with pytest.raises(ValueError, match="badly formed hexadecimal UUID"):
            process_sensor_reading(
                sensor_id="sensor-1", location_id="bad-location", event_id="event-1"
            )
        with pytest.raises(ValueError, match="badly formed hexadecimal UUID"):
            process_sensor_reading(
                sensor_id="sensor-1",
                location_id="a0000000-0000-0000-0000-000000000001",
                event_id="event-1",
            )
    credential.assert_not_called()
    get_db.assert_not_called()


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


def test_scoped_run_check_requires_a_valid_location_before_database_access():
    from services.ingestion.anomaly_detector import run_check

    with patch("services.ingestion.anomaly_detector.get_db") as get_db:
        with pytest.raises(ValueError, match="location_id must be a valid UUID"):
            run_check(location_id="not-a-location")

    get_db.assert_not_called()


def test_scoped_run_check_filters_readings_and_does_not_bootstrap_shared_rules():
    from services.ingestion.anomaly_detector import run_check

    location_id = "a0000000-0000-0000-0000-000000000001"
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[("rule-1", "rule", "type-1", "soil_moisture", "value", "gt", 50.0,
                                     None, "warning", 30, False, None)], []]

    with (
        patch("services.ingestion.anomaly_detector.get_db", return_value=db),
        patch("services.ingestion.anomaly_detector.ensure_alert_rules") as ensure_rules,
    ):
        run_check(location_id=location_id)

    reading_query, reading_parameters = cursor.execute.call_args_list[1].args
    assert "sr.location_id = %s::uuid" in reading_query
    assert reading_parameters[-2:] == (location_id, location_id)
    ensure_rules.assert_not_called()
    db.close.assert_called_once()


def test_scoped_baseline_check_filters_baselines_before_database_access():
    from services.ingestion.anomaly_detector import run_baseline_check

    location_id = "a0000000-0000-0000-0000-000000000001"
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []

    with patch("services.ingestion.anomaly_detector.get_db", return_value=db):
        run_baseline_check(location_id)

    statement, parameters = cursor.execute.call_args.args
    assert "eb.location_id = %s::uuid" in statement
    assert parameters == (location_id, location_id)
    db.close.assert_called_once()


class _AnomalyWorkerCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        self.connection.calls.append((compact, params))
        function = next(
            (name for name in self.connection.results if f"{name}(" in compact),
            None,
        )
        result = self.connection.results.get(function) if function else None
        if isinstance(result, list):
            self.rows = result
            self.row = None
        else:
            self.row = result
            self.rows = []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class _AnomalyWorkerConnection:
    autocommit = False

    def __init__(self, *, cooldown=False, matches=True, reserved=True, actuator=True):
        location_id = "a0000000-0000-0000-0000-000000000001"
        self.calls = []
        self.results = {
            "set_worker_tenant_context": (
                "a0000000-0000-0000-0000-000000000801",
                location_id,
                "a0000000-0000-0000-0000-000000000901",
                "system_worker",
            ),
            "read_sensor_anomaly_source": (
                "a0000000-0000-0000-0000-000000000021",
                "a0000000-0000-0000-0000-000000000011",
                "soil_moisture",
                12.5,
                None,
                None,
                location_id,
                None,
                "a0000000-0000-0000-0000-000000000011",
                "Sensor 1",
                "a0000000-0000-0000-0000-000000000071",
                "soil_moisture",
                "Test Farm",
            ),
            "list_sensor_anomaly_rules": [(
                "a0000000-0000-0000-0000-000000000091",
                "Soil Moisture Low",
                "a0000000-0000-0000-0000-000000000071",
                "soil_moisture",
                "value",
                "lt",
                15.0,
                None,
                "warning",
                0,
                True,
                "sensor_anomaly",
            )],
            "reserve_sensor_anomaly_effect": (reserved,),
            "sensor_anomaly_in_cooldown": (cooldown,),
            "evaluate_sensor_anomaly_rule": (matches,),
            "record_sensor_anomaly_effect_outcome": (True,),
            "create_sensor_anomaly_alert": (
                "a0000000-0000-0000-0000-000000000041",
                datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc),
            ),
            "create_sensor_alert_draft_claim": (
                "a0000000-0000-0000-0000-000000000051",
            ),
            "publish_sensor_alert_event": (True,),
            "enqueue_sensor_alert_notification_intent": (True,),
            "sensor_alert_actuation_enabled": (actuator,),
            "create_sensor_alert_actuation_intent": (
                "a0000000-0000-0000-0000-000000000061",
            ),
        }
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def cursor(self):
        return _AnomalyWorkerCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


def _process_worker(connection):
    from services.ingestion.sensor_anomaly_worker import process_sensor_reading

    with (
        patch("services.ingestion.sensor_anomaly_worker.get_worker_credential", return_value="x" * 40),
        patch("services.ingestion.sensor_anomaly_worker.get_worker_db", return_value=connection),
        patch(
            "services.ingestion.sensor_anomaly_worker._notification_payloads",
            return_value=[("webhook", "primary", {"text": "test"})],
        ),
    ):
        return process_sensor_reading(
            sensor_id="a0000000-0000-0000-0000-000000000011",
            location_id="a0000000-0000-0000-0000-000000000001",
            event_id="a0000000-0000-0000-0000-000000000031",
        )


def test_sensor_anomaly_worker_runs_bounded_effects_in_one_signed_transaction():
    connection = _AnomalyWorkerConnection()

    stats = _process_worker(connection)

    assert stats == {
        "rules": 1,
        "reserved": 1,
        "alerts": 1,
        "claims": 1,
        "notifications": 1,
        "actuation_intents": 1,
        "skipped": 0,
    }
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed == 1
    statements = [statement for statement, _params in connection.calls]
    assert statements.index("SET LOCAL ROLE kokonut_worker_execution") < next(
        index for index, statement in enumerate(statements)
        if "read_sensor_anomaly_source" in statement
    )
    assert any("record_sensor_anomaly_effect_outcome" not in statement for statement in statements)
    assert not any(
        "FROM public." in statement or "INSERT INTO public." in statement
        for statement in statements
    )


def test_sensor_anomaly_worker_skips_actuation_for_unconfigured_rules():
    connection = _AnomalyWorkerConnection(actuator=False)

    stats = _process_worker(connection)

    assert stats["alerts"] == 1
    assert stats["actuation_intents"] == 0
    assert not any(
        "create_sensor_alert_actuation_intent" in statement
        for statement, _params in connection.calls
    )
    assert connection.commits == 1
    assert connection.rollbacks == 0


@pytest.mark.parametrize(
    ("connection_kwargs", "expected_functions"),
    [
        ({"cooldown": True}, {"reserve_sensor_anomaly_effect", "sensor_anomaly_in_cooldown",
                               "record_sensor_anomaly_effect_outcome"}),
        ({"matches": False}, {"reserve_sensor_anomaly_effect", "sensor_anomaly_in_cooldown",
                              "evaluate_sensor_anomaly_rule"}),
        ({"reserved": False}, {"reserve_sensor_anomaly_effect"}),
    ],
)
def test_sensor_anomaly_worker_keeps_cooldown_no_match_and_replay_paths_bounded(
    connection_kwargs, expected_functions
):
    connection = _AnomalyWorkerConnection(**connection_kwargs)

    stats = _process_worker(connection)

    executed_functions = {
        function
        for statement, _params in connection.calls
        for function in expected_functions
        if f"{function}(" in statement
    }
    assert executed_functions == expected_functions
    assert stats["alerts"] == 0
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed == 1


def test_sensor_anomaly_worker_rolls_back_and_closes_on_delivery_failure():
    from services.ingestion.sensor_anomaly_worker import process_sensor_reading

    connection = _AnomalyWorkerConnection()
    with (
        patch("services.ingestion.sensor_anomaly_worker.get_worker_credential", return_value="x" * 40),
        patch("services.ingestion.sensor_anomaly_worker.get_worker_db", return_value=connection),
        patch(
            "services.ingestion.sensor_anomaly_worker._enqueue_notifications",
            side_effect=RuntimeError("synthetic notification intent failure"),
        ),
    ):
        with pytest.raises(RuntimeError, match="synthetic notification intent failure"):
            process_sensor_reading(
                sensor_id="a0000000-0000-0000-0000-000000000011",
                location_id="a0000000-0000-0000-0000-000000000001",
                event_id="a0000000-0000-0000-0000-000000000031",
            )

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
