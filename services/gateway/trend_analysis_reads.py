"""Location-scoped reads of saved trend estimates."""

from __future__ import annotations

import math
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_OFFSET = 10_000
_MAX_SMOOTHING_POINTS = 100
_MAX_CHANGE_POINTS = 100
_MAX_DECOMPOSITION_POINTS = 200
_NUMERIC_FIELDS = (
    "slope",
    "intercept",
    "r_squared",
    "standard_error",
    "slope_p_value",
    "slope_ci_lower",
    "slope_ci_upper",
)


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {label} identifier") from exc


def _page(limit: int, offset: int) -> tuple[int, int]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {_MAX_PAGE_SIZE}")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= _MAX_OFFSET:
        raise ValueError(f"offset must be between 0 and {_MAX_OFFSET}")
    return limit, offset


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


def list_location_trend_smoothing(
    operator_id: str,
    location_id: str,
    metric_key: str,
    *,
    limit: int = _MAX_SMOOTHING_POINTS,
    connection_factory: Callable | None = None,
) -> dict:
    """List the latest stored smoothing points for one metric and location."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    metric_key = _metric_key(metric_key)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_SMOOTHING_POINTS:
        raise ValueError(f"limit must be between 1 and {_MAX_SMOOTHING_POINTS}")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="trend_analysis",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT metric_key, smoothing_type, timestamp, original_value,
                       smoothed_value, computed_at
                  FROM trend_smoothing
                 WHERE location_id = %s::uuid
                   AND metric_key = %s
                 ORDER BY timestamp DESC, computed_at DESC, id DESC
                 LIMIT %s
                """,
                (location_id, metric_key, limit),
            )
            rows = _grouped_rows(cursor)
            for row in rows:
                for field in ("original_value", "smoothed_value"):
                    value = row[field]
                    if value is not None and not math.isfinite(value):
                        row[field] = None
        return {
            "location_id": location_id,
            "metric_key": metric_key,
            "items": rows,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_change_points(
    operator_id: str,
    location_id: str,
    metric_key: str,
    *,
    limit: int = _MAX_CHANGE_POINTS,
    connection_factory: Callable | None = None,
) -> dict:
    """List saved change-point detections for one metric and location."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    metric_key = _metric_key(metric_key)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_CHANGE_POINTS:
        raise ValueError(f"limit must be between 1 and {_MAX_CHANGE_POINTS}")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="trend_analysis",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT metric_key, detection_method, change_point_index,
                       change_point_timestamp, magnitude, direction, confidence,
                       segment_count, status, detected_at
                  FROM change_point
                 WHERE location_id = %s::uuid
                   AND metric_key = %s
                 ORDER BY detected_at DESC, id DESC
                 LIMIT %s
                """,
                (location_id, metric_key, limit),
            )
            rows = _grouped_rows(cursor)
            for row in rows:
                value = row["confidence"]
                if value is not None and not math.isfinite(value):
                    row["confidence"] = None
                value = row["magnitude"]
                if value is not None and not math.isfinite(value):
                    row["magnitude"] = None
        return {"location_id": location_id, "metric_key": metric_key, "items": rows}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_seasonal_decomposition(
    operator_id: str,
    location_id: str,
    metric_key: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Read the latest saved seasonal decomposition with a bounded preview."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    metric_key = _metric_key(metric_key)

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="trend_analysis",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT metric_key, decomposition_method, period,
                       CASE WHEN jsonb_typeof(trend_component) = 'array'
                            THEN jsonb_path_query_array(trend_component, '$[0 to 199]'::jsonpath)
                            ELSE '[]'::jsonb END AS trend_component,
                       CASE WHEN jsonb_typeof(seasonal_component) = 'array'
                            THEN jsonb_path_query_array(seasonal_component, '$[0 to 199]'::jsonpath)
                            ELSE '[]'::jsonb END AS seasonal_component,
                       CASE WHEN jsonb_typeof(residual_component) = 'array'
                            THEN jsonb_path_query_array(residual_component, '$[0 to 199]'::jsonpath)
                            ELSE '[]'::jsonb END AS residual_component,
                       seasonal_strength, trend_strength, residual_variance,
                       data_points,
                       CASE WHEN jsonb_typeof(trend_component) = 'array'
                            THEN jsonb_array_length(trend_component) ELSE 0 END
                           AS trend_component_points,
                       CASE WHEN jsonb_typeof(seasonal_component) = 'array'
                            THEN jsonb_array_length(seasonal_component) ELSE 0 END
                           AS seasonal_component_points,
                       CASE WHEN jsonb_typeof(residual_component) = 'array'
                            THEN jsonb_array_length(residual_component) ELSE 0 END
                           AS residual_component_points,
                       (CASE WHEN jsonb_typeof(trend_component) = 'array'
                             THEN jsonb_array_length(trend_component) ELSE 0 END > 200
                        OR CASE WHEN jsonb_typeof(seasonal_component) = 'array'
                                THEN jsonb_array_length(seasonal_component) ELSE 0 END > 200
                        OR CASE WHEN jsonb_typeof(residual_component) = 'array'
                                THEN jsonb_array_length(residual_component) ELSE 0 END > 200)
                           AS truncated,
                       computed_at
                  FROM seasonal_decomposition
                 WHERE location_id = %s::uuid
                   AND metric_key = %s
                 ORDER BY computed_at DESC, id DESC
                 LIMIT 1
                """,
                (location_id, metric_key),
            )
            rows = _grouped_rows(cursor)

        item = rows[0] if rows else None
        if item is not None:
            for field in (
                "trend_component",
                "seasonal_component",
                "residual_component",
            ):
                values = item[field]
                if not isinstance(values, list):
                    values = []
                item[field] = [
                    value if value is None or (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                    ) else None
                    for value in values[:_MAX_DECOMPOSITION_POINTS]
                ]
            for field in ("seasonal_strength", "trend_strength", "residual_variance"):
                value = item[field]
                if value is not None and not math.isfinite(value):
                    item[field] = None
        return {"location_id": location_id, "metric_key": metric_key, "item": item}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def _grouped_rows(cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def list_location_trend_estimates(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List latest saved trend estimates for each metric in one location.

    Reads stored estimates only. It does not run a model, inspect source
    measurements, or claim that saved metrics have been independently
    verified. Metadata and estimator-provided identity fields are not selected.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    limit, offset = _page(limit, offset)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="trend_analysis",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT metric_key, period_start, period_end, data_points,
                       slope, intercept, r_squared, standard_error,
                       slope_p_value, direction, confidence_level,
                       slope_ci_lower, slope_ci_upper, time_unit, computed_at
                  FROM (
                      SELECT DISTINCT ON (metric_key)
                             metric_key, period_start, period_end, data_points,
                             slope, intercept, r_squared, standard_error,
                             slope_p_value, direction, confidence_level,
                             slope_ci_lower, slope_ci_upper, time_unit,
                             computed_at, id
                        FROM trend_estimate
                       WHERE location_id = %s::uuid
                       ORDER BY metric_key, computed_at DESC, id DESC
                  ) AS latest
                 ORDER BY computed_at DESC, metric_key
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            rows = _grouped_rows(cursor)
            for row in rows:
                for field in _NUMERIC_FIELDS:
                    value = row[field]
                    if value is not None and not math.isfinite(value):
                        row[field] = None
        return {
            "location_id": location_id,
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
