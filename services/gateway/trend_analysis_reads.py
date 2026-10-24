"""Location-scoped reads of saved trend estimates."""

from __future__ import annotations

import math
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_OFFSET = 10_000
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
