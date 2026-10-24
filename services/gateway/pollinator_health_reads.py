"""Tenant-scoped, read-only pollinator health aggregates."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _rows(cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _number(value):
    return float(value) if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def get_location_pollinator_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded pollinator observations, habitats, pesticide and hive aggregates.

    Only verified/reviewed observations and impact records are treated as
    reviewed evidence. Habitat and active-hive inventory rows remain descriptive.
    Species, plot/hive identifiers, products, notes, JSON, and arbitrary metadata
    are not selected.
    """
    try:
        operator_id = str(UUID(str(operator_id)))
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="pollinator_health",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pollinator_type, observation_method, status,
                       COUNT(*)::bigint AS record_count,
                       SUM(count)::numeric AS total_observed,
                       AVG(duration_minutes)::numeric AS mean_duration_minutes,
                       MIN(observation_date) AS first_observation_date,
                       MAX(observation_date) AS last_observation_date
                  FROM pollinator_observation
                 WHERE location_id = %s::uuid AND status IN ('verified', 'reviewed')
                 GROUP BY pollinator_type, observation_method, status
                 ORDER BY pollinator_type, observation_method NULLS FIRST, status
                """,
                (location_id,),
            )
            observations = _rows(cur)

            cur.execute(
                """
                SELECT habitat_type, condition, status,
                       COUNT(*)::bigint AS record_count,
                       SUM(area_m2)::numeric AS total_area_m2
                  FROM pollinator_habitat
                 WHERE location_id = %s::uuid
                 GROUP BY habitat_type, condition, status
                 ORDER BY habitat_type, condition NULLS FIRST, status
                """,
                (location_id,),
            )
            habitats = _rows(cur)

            cur.execute(
                """
                SELECT toxicity_class, pollinator_mortality_observed,
                       COUNT(*)::bigint AS record_count,
                       AVG(mortality_pct)::numeric AS mean_mortality_pct,
                       MIN(application_date) AS first_application_date,
                       MAX(application_date) AS last_application_date
                  FROM pesticide_impact_log
                 WHERE location_id = %s::uuid AND status IN ('verified', 'reviewed')
                 GROUP BY toxicity_class, pollinator_mortality_observed
                 ORDER BY toxicity_class NULLS FIRST, pollinator_mortality_observed
                """,
                (location_id,),
            )
            pesticide_impacts = _rows(cur)

            cur.execute(
                """
                SELECT colony_strength, queen_status,
                       COUNT(*)::bigint AS hive_count,
                       SUM(honey_yield_kg)::numeric AS total_honey_yield_kg,
                       AVG(varroa_count)::numeric AS mean_varroa_count,
                       MAX(inspection_date) AS last_inspection_date
                  FROM hive_record
                 WHERE location_id = %s::uuid AND status = 'active'
                 GROUP BY colony_strength, queen_status
                 ORDER BY colony_strength NULLS FIRST, queen_status NULLS FIRST
                """,
                (location_id,),
            )
            hives = _rows(cur)

        return {
            "location_id": location_id,
            "verified_observations": [
                {
                    **row,
                    "record_count": int(row["record_count"]),
                    "total_observed": _number(row["total_observed"]),
                    "mean_duration_minutes": _number(row["mean_duration_minutes"]),
                    "first_observation_date": _date(row["first_observation_date"]),
                    "last_observation_date": _date(row["last_observation_date"]),
                }
                for row in observations
            ],
            "habitat_inventory": [
                {**row, "record_count": int(row["record_count"]), "total_area_m2": _number(row["total_area_m2"])}
                for row in habitats
            ],
            "verified_pesticide_impacts": [
                {
                    **row,
                    "record_count": int(row["record_count"]),
                    "mean_mortality_pct": _number(row["mean_mortality_pct"]),
                    "first_application_date": _date(row["first_application_date"]),
                    "last_application_date": _date(row["last_application_date"]),
                }
                for row in pesticide_impacts
            ],
            "active_hives": [
                {
                    **row,
                    "hive_count": int(row["hive_count"]),
                    "total_honey_yield_kg": _number(row["total_honey_yield_kg"]),
                    "mean_varroa_count": _number(row["mean_varroa_count"]),
                    "last_inspection_date": _date(row["last_inspection_date"]),
                }
                for row in hives
            ],
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
