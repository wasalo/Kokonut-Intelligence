"""Signed, bounded generation of advisory trend forecasts."""

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway.trend_forecast_compute import (
    create_location_time_series_forecast,
)

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"
FORECAST_ID = "33333333-3333-4333-8333-333333333333"


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "FROM metric_value AS mv" in query:
            self.description = [
                (name,) for name in ("id", "value", "period_end", "computed_at", "update_frequency")
            ]
            self.rows = self.connection.observations
        elif "FROM time_series_forecast" in query:
            self.description = [
                (name,) for name in ("id", "forecast_horizon", "time_unit", "training_points")
            ]
            self.rows = self.connection.existing_forecasts
        elif "INSERT INTO time_series_forecast" in query:
            if self.connection.fail_insert:
                raise RuntimeError("synthetic insert failure")
            self.description = [("id",), ("forecast_at",)]
            self.rows = [(FORECAST_ID, "2026-10-24T12:00:00Z")]
        else:
            self.description = []
            self.rows = []

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _Connection:
    def __init__(self, observations=None, existing_forecasts=None, *, fail_insert=False):
        self.queries = []
        self.observations = observations if observations is not None else [
            ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", 2.0, "2026-10-20", "2026-10-20T00:00:00Z", "daily"),
            ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2", 3.0, "2026-10-21", "2026-10-21T00:00:00Z", "daily"),
            ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3", 4.0, "2026-10-22", "2026-10-22T00:00:00Z", "daily"),
        ]
        self.existing_forecasts = existing_forecasts or []
        self.fail_insert = fail_insert
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _patch_context_and_model(monkeypatch, connection, order):
    def set_context(conn, **kwargs):
        order.append("context")
        assert conn is connection
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "trend_analysis",
            "action": "compute",
        }

    class Forecaster:
        def get_forecast_with_intervals(self, values, *, steps, confidence):
            order.append("compute")
            assert values == [2.0, 3.0, 4.0]
            assert steps == 12
            assert confidence == 0.95
            return {
                "forecasts": [5.0] * steps,
                "intervals": [
                    {"step": index + 1, "forecast": 5.0, "lower": 4.0, "upper": 6.0}
                    for index in range(steps)
                ],
                "confidence": confidence,
                "model_order": (1, 0, 1),
            }

    monkeypatch.setattr(
        "services.gateway.trend_forecast_compute.set_operator_tenant_context", set_context
    )
    monkeypatch.setattr("services.trends.forecasting.TimeSeriesForecaster", Forecaster)


def test_forecast_uses_verified_location_data_signed_compute_scope_and_atomic_write(monkeypatch):
    connection = _Connection()
    order = []
    original_execute = _Cursor.execute

    def execute(self, query, params=None):
        if "FROM metric_value AS mv" in query:
            order.append("source-query")
        original_execute(self, query, params)

    monkeypatch.setattr(_Cursor, "execute", execute)
    _patch_context_and_model(monkeypatch, connection, order)
    result = create_location_time_series_forecast(
        OPERATOR_ID,
        LOCATION_ID,
        "soil_carbon",
        connection_factory=lambda: connection,
    )

    assert order == ["context", "source-query", "compute"]
    source_query, source_params = next(
        pair for pair in connection.queries if "FROM metric_value AS mv" in pair[0]
    )
    assert "mv.location_id = %s::uuid" in source_query
    assert "md.metric_key = %s" in source_query
    assert "md.active IS TRUE" in source_query
    assert "mv.verified IS TRUE" in source_query
    assert "LIMIT %s" in source_query
    assert source_params == (LOCATION_ID, "soil_carbon", 365)
    assert any("SET status = 'superseded'" in query for query, _ in connection.queries)
    insert_query, insert_params = next(
        pair for pair in connection.queries if "INSERT INTO time_series_forecast" in pair[0]
    )
    assert "'arima'" in insert_query and "'active'" in insert_query
    assert "AND model_type = 'arima'" in next(
        query for query, _ in connection.queries if "SET status = 'superseded'" in query
    )
    assert "verified" not in insert_params[-1]
    assert result == {
        "location_id": LOCATION_ID,
        "metric_key": "soil_carbon",
        "forecast_id": FORECAST_ID,
        "status": "active",
        "created": True,
        "forecast_horizon": 12,
        "time_unit": "day",
        "training_points": 3,
        "forecast_at": "2026-10-24T12:00:00Z",
    }
    assert connection.commits == 1
    assert connection.rollbacks == 1
    assert connection.closed


def test_matching_active_forecast_is_reused_without_superseding(monkeypatch):
    connection = _Connection(
        existing_forecasts=[(FORECAST_ID, 12, "day", 3)]
    )
    order = []
    _patch_context_and_model(monkeypatch, connection, order)
    result = create_location_time_series_forecast(
        OPERATOR_ID, LOCATION_ID, "soil_carbon", connection_factory=lambda: connection
    )

    assert result["forecast_id"] == FORECAST_ID
    assert result["created"] is False
    assert result["time_unit"] == "day"
    assert not any("SET status = 'superseded'" in query for query, _ in connection.queries)
    assert not any("INSERT INTO time_series_forecast" in query for query, _ in connection.queries)
    assert connection.commits == 1


def test_insufficient_verified_observations_roll_back_before_any_write(monkeypatch):
    connection = _Connection(observations=[("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", 2.0, None, "2026-10-20", "daily")])
    order = []
    _patch_context_and_model(monkeypatch, connection, order)

    with pytest.raises(ValueError, match="At least three verified observations"):
        create_location_time_series_forecast(
            OPERATOR_ID, LOCATION_ID, "soil_carbon", connection_factory=lambda: connection
        )

    assert not any("UPDATE time_series_forecast" in query for query, _ in connection.queries)
    assert not any("INSERT INTO time_series_forecast" in query for query, _ in connection.queries)
    assert connection.commits == 0
    assert connection.rollbacks == 2
    assert connection.closed


def test_insert_failure_rolls_back_supersede_and_insert_together(monkeypatch):
    connection = _Connection(fail_insert=True)
    order = []
    _patch_context_and_model(monkeypatch, connection, order)

    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        create_location_time_series_forecast(
            OPERATOR_ID, LOCATION_ID, "soil_carbon", connection_factory=lambda: connection
        )

    assert any("SET status = 'superseded'" in query for query, _ in connection.queries)
    assert any("INSERT INTO time_series_forecast" in query for query, _ in connection.queries)
    assert connection.commits == 0
    assert connection.rollbacks == 2
    assert connection.closed


def test_invalid_inputs_fail_before_opening_database_connection():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("invalid arguments must fail before connecting")

    with pytest.raises(ValueError, match="forecast_horizon"):
        create_location_time_series_forecast(
            OPERATOR_ID, LOCATION_ID, "soil_carbon", forecast_horizon=101,
            connection_factory=connect,
        )
    with pytest.raises(ValueError, match="confidence"):
        create_location_time_series_forecast(
            OPERATOR_ID, LOCATION_ID, "soil_carbon", confidence=0.93,
            connection_factory=connect,
        )
    assert not called


def test_denied_signed_context_does_not_read_or_write_source_data(monkeypatch):
    connection = _Connection()

    def deny(_connection, **_kwargs):
        raise TenantContextDenied("missing trend compute grant")

    monkeypatch.setattr(
        "services.gateway.trend_forecast_compute.set_operator_tenant_context", deny
    )
    with pytest.raises(TenantContextDenied):
        create_location_time_series_forecast(
            OPERATOR_ID, LOCATION_ID, "soil_carbon", connection_factory=lambda: connection
        )

    assert not any("FROM metric_value AS mv" in query for query, _ in connection.queries)
    assert not any("INSERT INTO time_series_forecast" in query for query, _ in connection.queries)
    assert connection.commits == 0
    assert connection.closed
