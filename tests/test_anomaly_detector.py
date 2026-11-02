"""Tests for services.ingestion.anomaly_detector — sensor alert engine."""

from __future__ import annotations

import re
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


def test_ensure_alert_rules_uses_only_the_bounded_database_initializer():
    from services.ingestion.anomaly_detector import ensure_alert_rules

    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (10,)

    ensure_alert_rules(connection)

    cursor.execute.assert_called_once_with(
        "SELECT kokonut_security.ensure_default_alert_rules()"
    )
    cursor.fetchone.assert_called_once_with()


def test_sql_alert_rule_defaults_match_python_and_pilot_seed_stays_eight_rows():
    from pathlib import Path

    from services.ingestion.anomaly_detector import DEFAULT_ALERT_RULES

    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/739_runtime_alert_rule_read_only.sql").read_text()
    pilot_seed = (root / "schemas/seeds/003_pilot_environmental.sql").read_text()

    values_match = re.search(
        r"FROM \(VALUES(?P<rows>.*?)\) AS defaults\(", migration, re.DOTALL
    )
    assert values_match is not None
    tuple_pattern = re.compile(
        r"\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*"
        r"(-?[0-9]+(?:\.[0-9]+)?),\s*'([^']+)',\s*(true|false),\s*"
        r"(NULL|'[^']+')\)"
    )
    sql_rows = [
        (
            name,
            sensor_type,
            metric,
            operator,
            float(threshold),
            severity,
            enabled.lower() == "true",
            None if claim_type == "NULL" else claim_type[1:-1],
        )
        for name, sensor_type, metric, operator, threshold, severity, enabled, claim_type
        in tuple_pattern.findall(values_match.group("rows"))
    ]
    python_rows = [
        (
            rule["name"],
            rule["sensor_type_name"],
            rule["metric"],
            rule["operator"],
            float(rule["threshold_value"]),
            rule["severity"],
            bool(rule.get("auto_create_claim", False)),
            rule.get("claim_type"),
        )
        for rule in DEFAULT_ALERT_RULES
    ]
    assert sql_rows == python_rows
    assert len(sql_rows) == 10
    assert "SELECT kokonut_security.ensure_default_alert_rules()" not in migration

    pilot_rules = re.search(
        r"-- Alert Rules\s*(INSERT INTO alert_rule.*?;)", pilot_seed, re.DOTALL
    )
    assert pilot_rules is not None
    pilot_names = re.findall(r"'([A-Za-z][^']*)',\s*\(SELECT id FROM sensor_type", pilot_rules.group(1))
    assert pilot_names == [
        "Low Soil Moisture",
        "Critical Soil Moisture",
        "High Soil Temperature",
        "Frost Risk",
        "High Air Temperature",
        "Low Humidity",
        "Heavy Rainfall",
        "Extreme Rainfall",
    ]


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


def test_direct_alert_writer_fails_closed_without_touching_database():
    from services.ingestion.anomaly_detector import create_alert

    db = MagicMock()
    with pytest.raises(RuntimeError, match="signed anomaly worker"):
        create_alert(
            db,
            "device-1",
            "rule-1",
            "reading-1",
            "warning",
            "Synthetic alert",
            12.5,
            15.0,
        )
    db.cursor.assert_not_called()


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


def test_direct_cooldown_reader_fails_closed_without_touching_database():
    from services.ingestion.anomaly_detector import check_cooldown

    db = MagicMock()
    with pytest.raises(RuntimeError, match="signed anomaly worker"):
        check_cooldown(db, "rule-1", "device-1", 30)
    db.cursor.assert_not_called()


def test_run_check_requires_explicit_scope_before_database_access():
    from services.ingestion.anomaly_detector import run_check

    with patch("services.ingestion.anomaly_detector.get_db") as get_db:
        with pytest.raises(ValueError, match="require --location-id or --all-locations"):
            run_check()
    get_db.assert_not_called()


def test_scoped_run_check_requires_a_valid_location_before_database_access():
    from services.ingestion.anomaly_detector import run_check

    with patch("services.ingestion.anomaly_detector.get_db") as get_db:
        with pytest.raises(ValueError, match="location_id must be a valid UUID"):
            run_check(location_id="not-a-location")

    get_db.assert_not_called()


def test_run_check_delegates_to_signed_worker_with_canonical_scope():
    from services.ingestion.anomaly_detector import run_check

    location_id = "A0000000-0000-0000-0000-000000000001"
    sensor_id = "A0000000-0000-0000-0000-000000000011"
    worker_result = {
        "events_found": 1,
        "events_processed": 1,
        "rules": 2,
        "reserved": 1,
        "alerts": 1,
        "claims": 0,
        "notifications": 1,
        "actuation_intents": 0,
        "skipped": 1,
    }
    with (
        patch(
            "services.ingestion.sensor_anomaly_worker.replay_recent_sensor_reading_events",
            return_value=worker_result,
        ) as replay,
        patch("services.ingestion.anomaly_detector.get_db") as get_db,
    ):
        result = run_check(
            location_id=location_id,
            sensor_id=sensor_id,
        )

    call = replay.call_args.kwargs
    assert call["location_id"] == location_id.lower()
    assert call["sensor_id"] == sensor_id.lower()
    assert call["batch_size"] == 100
    assert call["since"].tzinfo == timezone.utc
    assert result["locations_processed"] == 1
    assert result["events_processed"] == 1
    get_db.assert_not_called()


def test_baseline_check_delegates_to_signed_worker_without_shared_database():
    from services.ingestion.anomaly_detector import run_baseline_check

    location_id = "a0000000-0000-0000-0000-000000000001"
    worker_result = {
        "baselines_checked": 1,
        "alerts_triggered": 1,
        "alerts_replayed": 0,
        "notifications_enqueued": 1,
    }
    with (
        patch(
            "services.ingestion.sensor_baseline_worker.run_baseline_check",
            return_value=worker_result,
        ) as baseline,
        patch("services.ingestion.anomaly_detector.get_db") as get_db,
    ):
        result = run_baseline_check(location_id)

    baseline.assert_called_once_with(location_id)
    assert result["locations_processed"] == 1
    assert result["alerts_triggered"] == 1
    get_db.assert_not_called()


def test_replay_validates_sensor_and_window_before_resolving_all_locations():
    from services.ingestion.anomaly_detector import run_check

    with patch("services.core.jobs.kokonut_network_location_ids") as locations:
        with pytest.raises(ValueError, match="sensor_id must be a valid UUID"):
            run_check(sensor_id="not-a-uuid", all_locations=True)
        with pytest.raises(ValueError, match="previous 24 hours"):
            run_check(since="2020-01-01T00:00:00Z", all_locations=True)
        with pytest.raises(ValueError, match="previous 24 hours"):
            run_check(since="2999-01-01T00:00:00Z", all_locations=True)
    locations.assert_not_called()


def test_all_location_run_check_uses_explicit_network_location_inventory():
    from services.ingestion.anomaly_detector import run_check

    location_a = "a0000000-0000-0000-0000-000000000001"
    location_b = "a0000000-0000-0000-0000-000000000002"
    empty_result = {
        "events_found": 0,
        "events_processed": 0,
        "rules": 0,
        "reserved": 0,
        "alerts": 0,
        "claims": 0,
        "notifications": 0,
        "actuation_intents": 0,
        "skipped": 0,
    }
    with (
        patch(
            "services.core.jobs.kokonut_network_location_ids",
            return_value=[location_a, location_b],
        ),
        patch(
            "services.ingestion.sensor_anomaly_worker.replay_recent_sensor_reading_events",
            return_value=empty_result,
        ) as replay,
    ):
        result = run_check(all_locations=True)

    assert [call.kwargs["location_id"] for call in replay.call_args_list] == [
        location_a,
        location_b,
    ]
    assert result["locations_processed"] == 2


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


def test_sensor_anomaly_worker_rejects_unregistered_query_before_cursor_access():
    from services.ingestion.sensor_anomaly_worker import (
        SensorAnomalyWorkerError,
        _one,
    )

    class NoCursorConnection:
        def cursor(self):
            raise AssertionError("unknown query operations must fail before cursor access")

    with pytest.raises(SensorAnomalyWorkerError, match="unsupported sensor anomaly query"):
        _one(NoCursorConnection(), "SELECT * FROM public.location", ())


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
