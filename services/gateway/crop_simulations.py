"""Tenant-scoped, read-only crop simulation run summaries."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_OFFSET = 10_000


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


def _number(value):
    return float(value) if value is not None else None


def _iso(value):
    return value.isoformat() if value is not None else None


def get_location_crop_simulation_runs(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded completed simulation summaries for one authorized farm."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    limit, offset = _page(limit, offset)

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="digital_twin",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM simulation_run AS sr
                  JOIN digital_twin AS dt ON dt.id = sr.twin_id
                 WHERE dt.location_id = %s::uuid
                   AND dt.twin_type = 'crop_simulation'
                   AND dt.status IN ('active', 'archived')
                   AND sr.status = 'completed'
                """,
                (location_id,),
            )
            total_runs = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT dt.id AS twin_id, dt.name AS twin_name,
                       sr.id AS run_id, sr.started_at, sr.completed_at,
                       sr.duration_ms, sr.final_yield, sr.final_yield_unit,
                       sr.total_water_mm, sr.total_nitrogen_kg,
                       sr.avg_soil_carbon_pct
                  FROM simulation_run AS sr
                  JOIN digital_twin AS dt ON dt.id = sr.twin_id
                 WHERE dt.location_id = %s::uuid
                   AND dt.twin_type = 'crop_simulation'
                   AND dt.status IN ('active', 'archived')
                   AND sr.status = 'completed'
                 ORDER BY sr.completed_at DESC NULLS LAST, sr.id
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        runs = []
        for row in rows[:limit]:
            runs.append(
                {
                    "twin_id": str(row["twin_id"]),
                    "twin_name": row["twin_name"],
                    "run_id": str(row["run_id"]),
                    "started_at": _iso(row["started_at"]),
                    "completed_at": _iso(row["completed_at"]),
                    "duration_ms": row["duration_ms"],
                    "final_yield": _number(row["final_yield"]),
                    "final_yield_unit": row["final_yield_unit"],
                    "total_water_mm": _number(row["total_water_mm"]),
                    "total_nitrogen_kg": _number(row["total_nitrogen_kg"]),
                    "avg_soil_carbon_pct": _number(row["avg_soil_carbon_pct"]),
                }
            )

        return {
            "location_id": location_id,
            "total_runs": total_runs,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
            "runs": runs,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_location_crop_simulation_run_detail(
    operator_id: str,
    location_id: str,
    run_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Return a completed run and a bounded page of its persisted daily states."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    run_id = _uuid(run_id, "run")
    limit, offset = _page(limit, offset)

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="digital_twin",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dt.id AS twin_id, dt.name AS twin_name,
                       sr.id AS run_id, sr.started_at,
                       sr.completed_at, sr.duration_ms, sr.final_yield,
                       sr.final_yield_unit, sr.total_water_mm,
                       sr.total_nitrogen_kg, sr.avg_soil_carbon_pct
                  FROM simulation_run AS sr
                  JOIN digital_twin AS dt ON dt.id = sr.twin_id
                 WHERE dt.location_id = %s::uuid
                   AND dt.twin_type = 'crop_simulation'
                   AND dt.status IN ('active', 'archived')
                   AND sr.status = 'completed'
                   AND sr.id = %s::uuid
                """,
                (location_id, run_id),
            )
            columns = [column[0] for column in cur.description]
            row = cur.fetchone()
            if row is None:
                return None
            run = dict(zip(columns, row))

            state_scope = """
                FROM simulation_state AS ss
                JOIN simulation_run AS sr ON sr.id = ss.run_id
                JOIN digital_twin AS dt ON dt.id = sr.twin_id
               WHERE dt.location_id = %s::uuid
                 AND dt.twin_type = 'crop_simulation'
                 AND dt.status IN ('active', 'archived')
                 AND sr.status = 'completed'
                 AND sr.id = %s::uuid
            """
            cur.execute(
                "SELECT COUNT(*) " + state_scope,
                (location_id, run_id),
            )
            total_states = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT ss.day_number, ss.state_date,
                       ss.soil_moisture_pct, ss.soil_nitrogen_ppm,
                       ss.soil_carbon_pct, ss.soil_temperature_c,
                       ss.gdd_accumulated, ss.crop_biomass_kg_ha,
                       ss.leaf_area_index, ss.crop_stage, ss.root_depth_cm,
                       ss.rainfall_mm, ss.irrigation_mm, ss.et_actual_mm,
                       ss.drainage_mm, ss.temp_avg_c, ss.temp_min_c,
                       ss.temp_max_c, ss.solar_radiation_mj, ss.humidity_pct,
                       ss.wind_speed_kmh, ss.carbon_sequestered_kg_ha,
                       ss.carbon_emitted_kg_ha
            """ + state_scope + """
                 ORDER BY ss.day_number, ss.state_date, ss.id
                 LIMIT %s OFFSET %s
                """,
                (location_id, run_id, limit + 1, offset),
            )
            state_columns = [column[0] for column in cur.description]
            state_rows = [dict(zip(state_columns, state)) for state in cur.fetchall()]

        states = []
        for state in state_rows[:limit]:
            states.append(
                {
                    key: (
                        _iso(value)
                        if key == "state_date"
                        else _number(value)
                        if key not in {"day_number", "crop_stage"}
                        else value
                    )
                    for key, value in state.items()
                }
            )

        return {
            "location_id": location_id,
            "run": {
                "twin_id": str(run["twin_id"]),
                "twin_name": run["twin_name"],
                "run_id": str(run["run_id"]),
                "started_at": _iso(run["started_at"]),
                "completed_at": _iso(run["completed_at"]),
                "duration_ms": run["duration_ms"],
                "final_yield": _number(run["final_yield"]),
                "final_yield_unit": run["final_yield_unit"],
                "total_water_mm": _number(run["total_water_mm"]),
                "total_nitrogen_kg": _number(run["total_nitrogen_kg"]),
                "avg_soil_carbon_pct": _number(run["avg_soil_carbon_pct"]),
            },
            "total_states": total_states,
            "limit": limit,
            "offset": offset,
            "has_more": len(state_rows) > limit,
            "states": states,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
