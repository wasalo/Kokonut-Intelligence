"""Tenant-scoped generation of advisory time-series forecasts."""

from __future__ import annotations

import hashlib
import json
import math
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_FORECAST_HORIZON = 100
_MAX_TRAINING_POINTS = 365
_ALGORITHM_VERSION = "kokonut-arima-1"
_TIME_UNITS = {
    "real_time": "observation",
    "hourly": "hour",
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
    "quarterly": "quarter",
    "annually": "year",
}


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {label} identifier") from exc


def _metric_key(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 100
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("metric_key must be a non-empty key of at most 100 characters")
    return value


def _bounded_integer(value: int, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def _confidence(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be one of 0.90, 0.95, or 0.99")
    confidence = float(value)
    if confidence not in {0.90, 0.95, 0.99}:
        raise ValueError("confidence must be one of 0.90, 0.95, or 0.99")
    return confidence


def _row_mapping(cursor, row) -> dict:
    return dict(
        zip(
            (
                column.name if hasattr(column, "name") else column[0]
                for column in (cursor.description or ())
            ),
            row,
        )
    )


def create_location_time_series_forecast(
    operator_id: str,
    location_id: str,
    metric_key: str,
    *,
    forecast_horizon: int = 12,
    confidence: float = 0.95,
    connection_factory: Callable | None = None,
) -> dict:
    """Compute from recent verified metric values and persist an advisory forecast.

    The exact-location signed grant is installed before reading source values.
    Repeated calls with the same verified inputs and options return the active
    forecast, while changed inputs atomically supersede it.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    metric_key = _metric_key(metric_key)
    forecast_horizon = _bounded_integer(
        forecast_horizon, "forecast_horizon", 1, _MAX_FORECAST_HORIZON
    )
    confidence = _confidence(confidence)

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="trend_analysis",
            action="compute",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                (location_id, metric_key),
            )
            cursor.execute(
                """
                SELECT id::text AS id, value::double precision AS value,
                       period_end, computed_at, update_frequency
                  FROM (
                      SELECT mv.id, mv.value, mv.period_end, mv.computed_at,
                             md.update_frequency
                        FROM metric_value AS mv
                        JOIN metric_definition AS md ON md.id = mv.metric_id
                       WHERE mv.location_id = %s::uuid
                         AND md.metric_key = %s
                         AND md.active IS TRUE
                         AND mv.verified IS TRUE
                         AND mv.value IS NOT NULL
                       ORDER BY COALESCE(mv.period_end, mv.computed_at::date) DESC,
                                mv.computed_at DESC, mv.id DESC
                       LIMIT %s
                  ) AS recent
                 ORDER BY COALESCE(period_end, computed_at::date), computed_at, id
                """,
                (location_id, metric_key, _MAX_TRAINING_POINTS),
            )
            observations = [_row_mapping(cursor, row) for row in cursor.fetchall()]

        values = [float(row["value"]) for row in observations]
        if len(values) < 3:
            raise ValueError("At least three verified observations are required")
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Verified observations must contain finite numeric values")

        from services.trends.forecasting import TimeSeriesForecaster

        result = TimeSeriesForecaster().get_forecast_with_intervals(
            values, steps=forecast_horizon, confidence=confidence
        )
        if "error" in result:
            raise ValueError("Verified observations are insufficient for this forecast")
        forecasts = result.get("forecasts")
        intervals = result.get("intervals")
        if (
            not isinstance(forecasts, list)
            or len(forecasts) != forecast_horizon
            or not isinstance(intervals, list)
            or len(intervals) != forecast_horizon
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in forecasts
            )
            or any(
                not isinstance(interval, dict)
                or any(
                    not isinstance(interval.get(field), (int, float))
                    or isinstance(interval.get(field), bool)
                    or not math.isfinite(interval[field])
                    for field in ("forecast", "lower", "upper")
                )
                for interval in intervals
            )
        ):
            raise ValueError("Forecast model returned invalid numeric output")

        digest_source = {
            "algorithm": _ALGORITHM_VERSION,
            "confidence": confidence,
            "forecast_horizon": forecast_horizon,
            "metric_key": metric_key,
            "update_frequency": observations[-1].get("update_frequency"),
            "observations": [
                [row["id"], float(row["value"]).hex()] for row in observations
            ],
        }
        input_digest = hashlib.sha256(
            json.dumps(digest_source, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        model_params = {
            "algorithm_version": _ALGORITHM_VERSION,
            "order": list(result.get("model_order", (1, 0, 1))),
            "confidence": confidence,
            "input_digest": input_digest,
        }
        update_frequency = observations[-1].get("update_frequency")
        time_unit = _TIME_UNITS.get(update_frequency, "observation")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text AS id, forecast_horizon, time_unit, training_points
                  FROM time_series_forecast
                 WHERE location_id = %s::uuid
                   AND metric_key = %s
                   AND model_type = 'arima'
                   AND status = 'active'
                   AND model_params ->> 'input_digest' = %s
                 ORDER BY forecast_at DESC, id DESC
                 LIMIT 1
                """,
                (location_id, metric_key, input_digest),
            )
            existing = cursor.fetchone()
            if existing is not None:
                item = _row_mapping(cursor, existing)
                connection.commit()
                return {
                    "location_id": location_id,
                    "metric_key": metric_key,
                    "forecast_id": item["id"],
                    "status": "active",
                    "created": False,
                    "forecast_horizon": item["forecast_horizon"],
                    "time_unit": item["time_unit"],
                    "training_points": item["training_points"],
                }

            cursor.execute(
                """
                UPDATE time_series_forecast
                   SET status = 'superseded'
                 WHERE location_id = %s::uuid
                   AND metric_key = %s
                   AND model_type = 'arima'
                   AND status = 'active'
                """,
                (location_id, metric_key),
            )
            cursor.execute(
                """
                INSERT INTO time_series_forecast (
                    metric_key, location_id, model_type, model_params,
                    forecast_values, prediction_intervals, forecast_horizon,
                    time_unit, training_points, status, metadata
                ) VALUES (
                    %s, %s::uuid, 'arima', %s::jsonb, %s::jsonb, %s::jsonb,
                    %s, %s, %s, 'active', %s::jsonb
                )
                RETURNING id::text AS id, forecast_at
                """,
                (
                    metric_key,
                    location_id,
                    json.dumps(model_params, allow_nan=False),
                    json.dumps(forecasts, allow_nan=False),
                    json.dumps(
                        {"confidence": confidence, "intervals": intervals},
                        allow_nan=False,
                    ),
                    forecast_horizon,
                    time_unit,
                    len(values),
                    json.dumps({"advisory": True, "generated_by_operator": operator_id}),
                ),
            )
            item = _row_mapping(cursor, cursor.fetchone())

        connection.commit()
        return {
            "location_id": location_id,
            "metric_key": metric_key,
            "forecast_id": item["id"],
            "status": "active",
            "created": True,
            "forecast_horizon": forecast_horizon,
            "time_unit": time_unit,
            "training_points": len(values),
            "forecast_at": item["forecast_at"],
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
