"""Location-scoped reads of saved geostatistical summaries."""

from __future__ import annotations

import json
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
_MAX_FOLD_DIAGNOSTICS = 10
_MIN_FOLD_TEST_SAMPLES = 5
_MAX_FOLD_DIAGNOSTICS_BYTES = 16 * 1024
_FOLD_METRIC_FIELDS = (
    "mean_error",
    "mean_squared_error",
    "rmse",
    "mae",
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


class GeostatisticalRealizationNotFound(LookupError):
    """A requested realization is not visible inside the granted location."""


class GeostatisticalKrigingNotFound(LookupError):
    """A requested kriging run is not visible inside the granted location."""


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


def _safe_spatial_fold_diagnostics(strategy: str, n_folds: int, value) -> list[dict]:
    """Project only aggregate spatial-block diagnostics from bounded JSONB."""
    if strategy != "spatial_block" or isinstance(n_folds, bool):
        return []
    if not isinstance(n_folds, int) or not 1 <= n_folds <= _MAX_FOLD_DIAGNOSTICS:
        return []
    if isinstance(value, str):
        if len(value.encode("utf-8")) > _MAX_FOLD_DIAGNOSTICS_BYTES:
            return []
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    if not isinstance(value, list) or len(value) != n_folds:
        return []

    safe = []
    for index, fold in enumerate(value, start=1):
        if not isinstance(fold, dict):
            return []
        train_samples = _strict_nonnegative_int(fold.get("train_samples"))
        test_samples = _strict_nonnegative_int(fold.get("test_samples"))
        if train_samples is None or train_samples < 1:
            return []
        if test_samples is None or test_samples < _MIN_FOLD_TEST_SAMPLES:
            return []

        metrics = {}
        for field in _FOLD_METRIC_FIELDS:
            raw = fold.get(field)
            if raw is None:
                metrics[field] = None
                continue
            if isinstance(raw, bool):
                return []
            try:
                number = float(raw)
            except (TypeError, ValueError, OverflowError):
                return []
            metrics[field] = number if math.isfinite(number) else None

        safe.append({
            "fold": index,
            "train_samples": train_samples,
            "test_samples": test_samples,
            **metrics,
        })
    return safe


def _strict_nonnegative_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isascii() and value.isdigit():
        try:
            result = int(value)
        except (ValueError, OverflowError):
            return None
    else:
        return None
    return result if result >= 0 else None


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
            "has_more": (
                len(rows) > limit and offset + limit <= _MAX_OFFSET
            ),
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
                SELECT cv.property_key, cv.cv_strategy, cv.n_folds, cv.block_size_m,
                       cv.mean_error, cv.mean_squared_error, cv.root_mean_squared_error,
                       cv.mean_absolute_error, cv.r_squared, cv.computed_at,
                       CASE
                           WHEN cv.cv_strategy = 'spatial_block'
                            AND cv.n_folds BETWEEN 1 AND %s
                            AND CASE
                                    WHEN jsonb_typeof(cv.fold_results) = 'array'
                                    THEN jsonb_array_length(cv.fold_results) = cv.n_folds
                                     AND octet_length(cv.fold_results::text) <= %s
                                    ELSE FALSE
                                END
                           THEN COALESCE((
                               SELECT jsonb_agg(
                                   jsonb_build_object(
                                       'train_samples', fold.item ->> 'train_samples',
                                       'test_samples', fold.item ->> 'test_samples',
                                       'mean_error', fold.item ->> 'mean_error',
                                       'mean_squared_error', fold.item ->> 'mean_squared_error',
                                       'rmse', fold.item ->> 'rmse',
                                       'mae', fold.item ->> 'mae',
                                       'r_squared', fold.item ->> 'r_squared'
                                   ) ORDER BY fold.ordinality
                               )
                                 FROM jsonb_array_elements(cv.fold_results)
                                      WITH ORDINALITY AS fold(item, ordinality)
                                WHERE jsonb_typeof(fold.item) = 'object'
                           ), '[]'::jsonb)
                           ELSE '[]'::jsonb
                       END AS fold_diagnostics
                  FROM geostat_cv_result AS cv
                 WHERE cv.location_id = %s::uuid
                 ORDER BY cv.computed_at DESC, cv.property_key, cv.cv_strategy, cv.id DESC
                 LIMIT %s OFFSET %s
                """,
                (
                    _MAX_FOLD_DIAGNOSTICS,
                    _MAX_FOLD_DIAGNOSTICS_BYTES,
                    location_id,
                    limit + 1,
                    offset,
                ),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            for row in rows:
                row["fold_diagnostics"] = _safe_spatial_fold_diagnostics(
                    row["cv_strategy"], row["n_folds"], row["fold_diagnostics"]
                )
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
                SELECT run.id AS prediction_id, run.property_key, run.method, run.grid_resolution_m,
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


def list_location_kriging_points(
    operator_id: str,
    location_id: str,
    prediction_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Read one bounded point page from a kriging run owned by this location."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    prediction_id = _uuid(prediction_id, "prediction")
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
                SELECT id, property_key, method, grid_resolution_m,
                       n_points, created_at
                  FROM kriging_prediction
                 WHERE id = %s::uuid AND location_id = %s::uuid
                """,
                (prediction_id, location_id),
            )
            run_columns = [column[0] for column in cursor.description]
            run_rows = cursor.fetchall()
            if not run_rows:
                raise GeostatisticalKrigingNotFound
            run = dict(zip(run_columns, run_rows[0]))

            cursor.execute(
                """
                SELECT COUNT(*)
                  FROM kriging_point AS point
                  JOIN kriging_prediction AS run
                    ON run.id = point.prediction_id
                 WHERE point.prediction_id = %s::uuid
                   AND run.location_id = %s::uuid
                """,
                (prediction_id, location_id),
            )
            count_rows = cursor.fetchall()
            total = int(count_rows[0][0]) if count_rows else 0

            cursor.execute(
                """
                SELECT ST_X(point.point_geometry) AS longitude,
                       ST_Y(point.point_geometry) AS latitude,
                       point.predicted_value,
                       point.prediction_variance,
                       point.prediction_std
                  FROM kriging_point AS point
                  JOIN kriging_prediction AS run
                    ON run.id = point.prediction_id
                 WHERE point.prediction_id = %s::uuid
                   AND run.location_id = %s::uuid
                 ORDER BY ST_Y(point.point_geometry),
                          ST_X(point.point_geometry), point.id
                 LIMIT %s OFFSET %s
                """,
                (prediction_id, location_id, limit, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for index, row in enumerate(rows, start=offset + 1):
            row["point_number"] = index
            for field in (
                "longitude", "latitude", "predicted_value",
                "prediction_variance", "prediction_std",
            ):
                value = row[field]
                if value is not None:
                    numeric = float(value)
                    row[field] = numeric if math.isfinite(numeric) else None
                    if field == "longitude" and not -180 <= numeric <= 180:
                        row[field] = None
                    elif field == "latitude" and not -90 <= numeric <= 90:
                        row[field] = None
                    elif field in ("prediction_variance", "prediction_std") and numeric < 0:
                        row[field] = None

        run.pop("id", None)
        if run["grid_resolution_m"] is not None:
            value = float(run["grid_resolution_m"])
            run["grid_resolution_m"] = value if math.isfinite(value) else None
        return {
            "location_id": location_id,
            "prediction_id": prediction_id,
            "prediction": run,
            "items": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
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
                SELECT run.id AS realization_id, run.property_key,
                       run.realization_number, run.method,
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


def list_location_realization_points(
    operator_id: str,
    location_id: str,
    realization_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Read one bounded point page from a realization owned by this location."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    realization_id = _uuid(realization_id, "realization")
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
                SELECT id, property_key, realization_number, method,
                       grid_resolution_m, n_points, created_at
                  FROM geostat_realization
                 WHERE id = %s::uuid AND location_id = %s::uuid
                """,
                (realization_id, location_id),
            )
            run_columns = [column[0] for column in cursor.description]
            run_rows = cursor.fetchall()
            if not run_rows:
                raise GeostatisticalRealizationNotFound
            run = dict(zip(run_columns, run_rows[0]))

            cursor.execute(
                """
                SELECT COUNT(*)
                  FROM geostat_realization_point AS point
                  JOIN geostat_realization AS run
                    ON run.id = point.realization_id
                 WHERE point.realization_id = %s::uuid
                   AND run.location_id = %s::uuid
                """,
                (realization_id, location_id),
            )
            count_rows = cursor.fetchall()
            total = int(count_rows[0][0]) if count_rows else 0

            cursor.execute(
                """
                SELECT ST_X(point.point_geometry) AS longitude,
                       ST_Y(point.point_geometry) AS latitude,
                       point.simulated_value
                  FROM geostat_realization_point AS point
                  JOIN geostat_realization AS run
                    ON run.id = point.realization_id
                 WHERE point.realization_id = %s::uuid
                   AND run.location_id = %s::uuid
                 ORDER BY ST_Y(point.point_geometry),
                          ST_X(point.point_geometry), point.id
                 LIMIT %s OFFSET %s
                """,
                (realization_id, location_id, limit, offset),
            )
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for index, row in enumerate(rows, start=offset + 1):
            row["point_number"] = index
            for field in ("longitude", "latitude", "simulated_value"):
                value = row[field]
                if value is not None:
                    numeric = float(value)
                    row[field] = numeric if math.isfinite(numeric) else None
                    if field == "longitude" and not -180 <= numeric <= 180:
                        row[field] = None
                    elif field == "latitude" and not -90 <= numeric <= 90:
                        row[field] = None

        run.pop("id", None)
        if run["grid_resolution_m"] is not None:
            value = float(run["grid_resolution_m"])
            run["grid_resolution_m"] = value if math.isfinite(value) else None
        return {
            "location_id": location_id,
            "realization_id": realization_id,
            "realization": run,
            "items": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
