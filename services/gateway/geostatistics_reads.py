"""Location-scoped reads of saved geostatistical summaries."""

from __future__ import annotations

import math
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_OFFSET = 10_000
_NUMERIC_FIELDS = (
    "statistic_value",
    "expected_value",
    "p_value",
    "z_score",
    "distance_threshold",
)
_CV_NUMERIC_FIELDS = (
    "block_size_m",
    "mean_error",
    "mean_squared_error",
    "root_mean_squared_error",
    "mean_absolute_error",
    "r_squared",
)
_VARIOGRAM_NUMERIC_FIELDS = (
    "sill",
    "range",
    "nugget",
    "partial_sill",
    "lag_distance",
    "lag_tolerance",
    "bandwidth",
    "r_squared",
)
_SENSOR_DESIGN_NUMERIC_FIELDS = (
    "optimal_spacing_m",
    "coverage_radius_m",
    "coverage_gap_pct",
    "confidence_level",
)
_KRIGING_NUMERIC_FIELDS = (
    "grid_resolution_m",
    "mean_predicted",
    "mean_variance",
    "mean_std",
    "min_predicted",
    "max_predicted",
)
_REALIZATION_NUMERIC_FIELDS = (
    "grid_resolution_m",
    "mean_simulated_value",
    "stddev_simulated_value",
    "min_simulated_value",
    "max_simulated_value",
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


def list_location_spatial_autocorrelation(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List latest stored autocorrelation statistics for an exact location."""
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
            resource="geostatistics",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT property_key, metric, statistic_value, expected_value,
                       p_value, z_score, n_samples, spatial_weights_type,
                       distance_threshold, k_neighbors, computed_at
                  FROM (
                      SELECT DISTINCT ON (property_key, metric)
                             property_key, metric, statistic_value, expected_value,
                             p_value, z_score, n_samples, spatial_weights_type,
                             distance_threshold, k_neighbors, computed_at, id
                        FROM spatial_autocorrelation
                       WHERE location_id = %s::uuid
                       ORDER BY property_key, metric, computed_at DESC, id DESC
                  ) AS latest
                 ORDER BY computed_at DESC, property_key, metric
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
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


def list_location_cross_validation(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded, fixed-projection spatial cross-validation summaries."""
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
            resource="geostatistics",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT property_key, cv_strategy, n_folds, block_size_m,
                       mean_error, mean_squared_error, root_mean_squared_error,
                       mean_absolute_error, r_squared, computed_at
                  FROM geostat_cv_result
                 WHERE location_id = %s::uuid
                 ORDER BY computed_at DESC, property_key, cv_strategy, id DESC
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            for row in rows:
                for field in _CV_NUMERIC_FIELDS:
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


def list_location_variogram_models(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded, fixed-projection fitted variogram summaries."""
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
            resource="geostatistics",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT property_key, model_type, sill, range, nugget, partial_sill,
                       lag_distance, lag_tolerance, bandwidth, n_pairs, r_squared,
                       fitted_at
                  FROM variogram_model
                 WHERE location_id = %s::uuid
                 ORDER BY fitted_at DESC, property_key, model_type, id DESC
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            for row in rows:
                for field in _VARIOGRAM_NUMERIC_FIELDS:
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


def list_location_sensor_network_designs(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded location-scoped sensor-network design summaries."""
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
            resource="geostatistics",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT property_key, optimal_spacing_m, coverage_radius_m,
                       recommended_n_sensors, current_n_sensors,
                       coverage_gap_pct, confidence_level, computed_at
                  FROM sensor_network_design
                 WHERE location_id = %s::uuid
                 ORDER BY computed_at DESC, property_key, id DESC
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            for row in rows:
                for field in _SENSOR_DESIGN_NUMERIC_FIELDS:
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


def list_location_kriging_summaries(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded location-scoped aggregate summaries of saved kriging runs."""
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
            resource="geostatistics",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH selected_runs AS (
                    SELECT id, property_key, grid_resolution_m, n_points,
                           method, created_at
                      FROM kriging_prediction
                     WHERE location_id = %s::uuid
                     ORDER BY created_at DESC, id DESC
                     LIMIT %s OFFSET %s
                )
                SELECT run.property_key, run.method, run.grid_resolution_m,
                       run.n_points, COUNT(point.id) AS result_point_count,
                       AVG(point.predicted_value) AS mean_predicted,
                       AVG(point.prediction_variance) AS mean_variance,
                       AVG(point.prediction_std) AS mean_std,
                       MIN(point.predicted_value) AS min_predicted,
                       MAX(point.predicted_value) AS max_predicted,
                       run.created_at
                  FROM selected_runs AS run
                  LEFT JOIN kriging_point AS point
                    ON point.prediction_id = run.id
                 GROUP BY run.id, run.property_key, run.method,
                          run.grid_resolution_m, run.n_points, run.created_at
                 ORDER BY run.created_at DESC, run.id DESC
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            for row in rows:
                for field in _KRIGING_NUMERIC_FIELDS:
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


def list_location_realization_summaries(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded location-scoped aggregate summaries of saved realizations."""
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
            resource="geostatistics",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH selected_runs AS (
                    SELECT id, property_key, realization_number,
                           grid_resolution_m, n_points, method, created_at
                      FROM geostat_realization
                     WHERE location_id = %s::uuid
                     ORDER BY created_at DESC, id DESC
                     LIMIT %s OFFSET %s
                )
                SELECT run.property_key, run.realization_number, run.method,
                       run.grid_resolution_m, run.n_points,
                       COUNT(point.id) AS result_point_count,
                       AVG(point.simulated_value) AS mean_simulated_value,
                       STDDEV_POP(point.simulated_value) AS stddev_simulated_value,
                       MIN(point.simulated_value) AS min_simulated_value,
                       MAX(point.simulated_value) AS max_simulated_value,
                       run.created_at
                  FROM selected_runs AS run
                  LEFT JOIN geostat_realization_point AS point
                    ON point.realization_id = run.id
                 GROUP BY run.id, run.property_key, run.realization_number,
                          run.method, run.grid_resolution_m, run.n_points,
                          run.created_at
                 ORDER BY run.created_at DESC, run.id DESC
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            for row in rows:
                for field in _REALIZATION_NUMERIC_FIELDS:
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
