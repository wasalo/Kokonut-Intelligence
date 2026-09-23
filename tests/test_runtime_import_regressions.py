"""Regression coverage for runtime import and configuration audit findings."""

import sys
import types
from datetime import datetime, timezone
from typing import Any, get_type_hints

import pytest

from services.attestation.schemas import get_schema_definition
from services.crisp import financial_risk
from services.ingestion import anomaly_detector, climate_data, gee_climate, ml_anomaly_detector
from services.systems.config import ARCHETYPES


class _Cursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.query = None
        self.closed = False

    def execute(self, query, _params=None):
        self.query = query

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.cursors = []
        self.closed = False

    def cursor(self, **kwargs):
        cursor = _Cursor(self.rows)
        cursor.cursor_factory = kwargs.get("cursor_factory")
        self.cursors.append(cursor)
        return cursor

    def close(self):
        self.closed = True


def test_attestation_schema_annotations_resolve():
    hints = get_type_hints(get_schema_definition)

    assert hints["return"] == dict[str, Any]


def test_tragedy_of_the_commons_keeps_private_benefit_and_shared_cost():
    structure = ARCHETYPES["tragedy_of_the_commons"]["structure"]

    assert structure == {
        "shared_resource": "limited_capacity",
        "individual_benefit": "benefit_private",
        "collective_cost": "cost_shared",
    }


def test_financial_risk_applies_vintage_adjustment(monkeypatch):
    monkeypatch.setattr(financial_risk, "_query_financial_sustainability", lambda *_: {})
    monkeypatch.setattr(financial_risk, "_query_unit_economics", lambda *_: {})
    monkeypatch.setattr(financial_risk, "_query_revenue_summary", lambda *_: {"revenue_count": 0})
    monkeypatch.setattr(financial_risk, "_query_expense_summary", lambda *_: {})
    monkeypatch.setattr(financial_risk, "_compute_revenue_risk", lambda *_: 0.2)
    monkeypatch.setattr(financial_risk, "_compute_cost_risk", lambda *_: 0.2)
    monkeypatch.setattr(financial_risk, "_compute_liquidity_risk", lambda *_: 0.2)
    monkeypatch.setattr(financial_risk, "_compute_market_price_risk", lambda *_: 0.2)

    current_year = datetime.now(timezone.utc).year
    result = financial_risk.compute_financial_risk(
        object(), "location-123", vintage_year=current_year - 3
    )

    assert result.factors["vintage_risk_adjustment"] == 0.06


def test_gee_client_initializes_without_service_account_key(monkeypatch):
    ee_module = types.ModuleType("ee")
    ee_module.initialize_calls = []
    ee_module.Initialize = lambda *args, **kwargs: ee_module.initialize_calls.append((args, kwargs))
    monkeypatch.setitem(sys.modules, "ee", ee_module)
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_KEY", raising=False)

    assert gee_climate._get_gee_client() is ee_module
    assert len(ee_module.initialize_calls) == 1


def test_anomaly_actuation_queries_rule_when_enabled(monkeypatch):
    connection = _Connection(rows=[{"actuator_enabled": False}])
    monkeypatch.setattr(anomaly_detector, "get_db", lambda: connection)
    actuator_module = types.ModuleType("services.ingestion.mqtt_actuator")
    actuator_module.send_actuation_command = lambda *_args, **_kwargs: pytest.fail(
        "disabled actuator rule must not dispatch"
    )
    monkeypatch.setitem(sys.modules, "services.ingestion.mqtt_actuator", actuator_module)

    anomaly_detector.send_actuation_commands({"alert_rule_id": "rule-123", "severity": "info"})

    assert len(connection.cursors) == 1
    assert "FROM alert_rule" in connection.cursors[0].query
    assert connection.closed


def test_climate_cli_without_fetch_option_returns_help_code():
    result = climate_data.main(["--location-id", "location-123"])

    assert result == 1


@pytest.mark.parametrize(
    ("query_function", "args"),
    [
        (ml_anomaly_detector._query_sensor_timeseries, ("location-123", "soil_moisture")),
        (ml_anomaly_detector._query_all_sensors_timeseries, ("location-123",)),
    ],
)
def test_ml_sensor_queries_use_database_cursor(monkeypatch, query_function, args):
    import pandas as pd

    monkeypatch.setattr(ml_anomaly_detector, "_pd", pd)
    connection = _Connection()

    result = query_function(connection, *args)

    assert result.empty
    assert len(connection.cursors) == 1
    assert connection.cursors[0].cursor_factory is not None


def test_ml_check_runs_sensor_queries(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    monkeypatch.setattr(ml_anomaly_detector, "_pd", pd)
    monkeypatch.setattr(
        ml_anomaly_detector,
        "load_models",
        lambda *_args, **_kwargs: {"prophet": {}, "iforest": None},
    )
    connection = _Connection()

    result = ml_anomaly_detector.run_ml_check(connection, location_id="location-123")

    assert result["status"] == "success"
    assert result["sensors_checked"] == 0
    assert len(connection.cursors) == 2


def test_ml_model_save_lists_sensors_without_import_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(ml_anomaly_detector, "fit_isolation_forest", lambda *_args, **_kwargs: None)
    connection = _Connection()

    result = ml_anomaly_detector.save_models(connection, "location-123")

    assert result["status"] == "success"
    assert result["models_saved"] == []
    assert (ml_anomaly_detector.MODEL_DIR.stat().st_mode & 0o077) == 0
    assert len(connection.cursors) == 1


def test_ml_model_save_refuses_untrusted_directory(monkeypatch, tmp_path):
    model_dir = tmp_path / "writable-models"
    model_dir.mkdir(mode=0o700)
    model_dir.chmod(0o777)
    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)

    result = ml_anomaly_detector.save_models(object(), "location-123")

    assert result["status"] == "error"
    assert "not group/world writable" in result["message"]
