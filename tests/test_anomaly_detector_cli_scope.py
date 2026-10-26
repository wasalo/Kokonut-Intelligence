"""The anomaly CLI makes location-wide work an explicit operator choice."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import anomaly_detector

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


def test_no_arguments_print_help_without_database_access(capsys):
    with (
        patch.object(anomaly_detector, "get_db") as get_db,
        patch.object(anomaly_detector, "run_check") as run_check,
    ):
        anomaly_detector.main([])

    output = capsys.readouterr().out
    assert "--location-id" in output
    assert "--all-locations" in output
    get_db.assert_not_called()
    run_check.assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--baseline-check"],
        ["--ml-check"],
        ["--sensor", "sensor-1"],
        ["--since", "2026-10-01 00:00:00"],
    ],
)
def test_scoped_operations_reject_missing_scope_before_database_access(arguments):
    with (
        patch.object(anomaly_detector, "get_db") as get_db,
        patch.object(anomaly_detector, "run_baseline_check") as baseline,
        patch.object(anomaly_detector, "run_check") as run_check,
        pytest.raises(SystemExit) as exc,
    ):
        anomaly_detector.main(arguments)

    assert exc.value.code == 2
    get_db.assert_not_called()
    baseline.assert_not_called()
    run_check.assert_not_called()


def test_invalid_location_is_rejected_before_database_access():
    with (
        patch.object(anomaly_detector, "get_db") as get_db,
        patch.object(anomaly_detector, "run_check") as run_check,
        pytest.raises(SystemExit) as exc,
    ):
        anomaly_detector.main(["--location-id", "not-a-uuid"])

    assert exc.value.code == 2
    get_db.assert_not_called()
    run_check.assert_not_called()


def test_scoped_scan_receives_canonical_location_uuid():
    uppercase_location = LOCATION_ID.upper()
    with patch.object(anomaly_detector, "run_check") as run_check:
        anomaly_detector.main(["--location-id", uppercase_location, "--sensor", "sensor-1"])

    run_check.assert_called_once_with(
        sensor_id="sensor-1",
        since=None,
        location_id=LOCATION_ID,
    )


def test_explicit_all_locations_runs_default_anomaly_scan():
    with patch.object(anomaly_detector, "run_check") as run_check:
        anomaly_detector.main(["--all-locations"])

    run_check.assert_called_once_with(sensor_id=None, since=None, location_id=None)


def test_baseline_check_requires_and_forwards_explicit_aggregate_scope():
    with patch.object(anomaly_detector, "run_baseline_check") as baseline:
        anomaly_detector.main(["--baseline-check", "--all-locations"])

    baseline.assert_called_once_with(location_id=None)


def test_ml_check_uses_mocked_database_only_after_explicit_aggregate_scope():
    connection = MagicMock()
    with (
        patch("services.ingestion.base.get_db", return_value=connection) as get_db,
        patch("services.ingestion.ml_anomaly_detector.run_ml_check", return_value={"ok": True}) as check,
        patch.object(anomaly_detector, "print_json") as print_json,
    ):
        anomaly_detector.main(["--ml-check", "--all-locations"])

    get_db.assert_called_once_with()
    check.assert_called_once_with(connection, location_id=None, sensor_id=None)
    print_json.assert_called_once_with({"ok": True})
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--ml-train"],
        ["--ml-train", "--all-locations"],
    ],
)
def test_ml_training_rejects_missing_or_aggregate_scope_before_database_access(arguments):
    with (
        patch("services.ingestion.base.get_db") as get_db,
        pytest.raises(SystemExit) as exc,
    ):
        anomaly_detector.main(arguments)

    assert exc.value.code == 2
    get_db.assert_not_called()


def test_ml_training_forwards_one_canonical_location():
    connection = MagicMock()
    with (
        patch("services.ingestion.base.get_db", return_value=connection) as get_db,
        patch("services.ingestion.ml_anomaly_detector.save_models", return_value={"saved": True}) as train,
        patch.object(anomaly_detector, "print_json") as print_json,
    ):
        anomaly_detector.main(["--ml-train", "--location-id", LOCATION_ID.upper()])

    get_db.assert_called_once_with()
    train.assert_called_once_with(connection, LOCATION_ID)
    print_json.assert_called_once_with({"saved": True})
    connection.close.assert_called_once_with()


def test_ml_check_rejects_invalid_sensor_uuid_before_database_access():
    with (
        patch("services.ingestion.base.get_db") as get_db,
        pytest.raises(SystemExit) as exc,
    ):
        anomaly_detector.main(
            ["--ml-check", "--all-locations", "--sensor", "not-a-uuid"]
        )

    assert exc.value.code == 2
    get_db.assert_not_called()


def test_rule_listing_remains_an_explicit_global_read():
    with patch.object(anomaly_detector, "list_rules") as list_rules:
        anomaly_detector.main(["--list-rules"])

    list_rules.assert_called_once_with()
