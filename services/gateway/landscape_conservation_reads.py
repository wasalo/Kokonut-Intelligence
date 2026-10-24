"""Tenant-scoped, read-only landscape conservation aggregates."""

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


def get_location_landscape_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return location-bound habitat, corridor, hedgerow and assessment summaries.

    Inventories retain their source statuses and are not presented as verified
    outcomes. Only verified buffer checks and verified/published biodiversity
    assessments contribute to the reviewed evidence sections. Names, geometry,
    notes, assessor identities and arbitrary metadata are never selected.
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
            resource="landscape_conservation",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT habitat_type, status, biodiversity_value,
                       COUNT(*)::bigint AS record_count,
                       SUM(area_ha)::numeric AS total_area_ha
                  FROM habitat_zone
                 WHERE location_id = %s::uuid
                 GROUP BY habitat_type, status, biodiversity_value
                 ORDER BY habitat_type, status, biodiversity_value NULLS FIRST
                """,
                (location_id,),
            )
            habitats = _rows(cur)

            cur.execute(
                """
                SELECT condition, status, COUNT(*)::bigint AS record_count,
                       SUM(length_m)::numeric AS total_length_m,
                       AVG(width_m)::numeric AS mean_width_m
                  FROM wildlife_corridor
                 WHERE location_id = %s::uuid
                 GROUP BY condition, status
                 ORDER BY condition NULLS FIRST, status
                """,
                (location_id,),
            )
            corridors = _rows(cur)

            cur.execute(
                """
                SELECT condition, status, COUNT(*)::bigint AS record_count,
                       SUM(length_m)::numeric AS total_length_m,
                       AVG(height_m)::numeric AS mean_height_m
                  FROM hedgerow_record
                 WHERE location_id = %s::uuid
                 GROUP BY condition, status
                 ORDER BY condition NULLS FIRST, status
                """,
                (location_id,),
            )
            hedgerows = _rows(cur)

            cur.execute(
                """
                SELECT compliant, erosion_observed,
                       COUNT(*)::bigint AS record_count,
                       MIN(check_date) AS first_check_date,
                       MAX(check_date) AS last_check_date
                  FROM buffer_zone_monitoring
                 WHERE location_id = %s::uuid AND status = 'verified'
                 GROUP BY compliant, erosion_observed
                 ORDER BY compliant NULLS FIRST, erosion_observed
                """,
                (location_id,),
            )
            buffer_checks = _rows(cur)

            cur.execute(
                """
                SELECT COUNT(*)::bigint AS assessment_count,
                       AVG(species_richness)::numeric AS mean_species_richness,
                       AVG(shannon_index)::numeric AS mean_shannon_index,
                       AVG(habitat_diversity_index)::numeric AS mean_habitat_diversity_index,
                       AVG(connectivity_score)::numeric AS mean_connectivity_score,
                       AVG(overall_score)::numeric AS mean_overall_score,
                       MIN(assessment_date) AS first_assessment_date,
                       MAX(assessment_date) AS last_assessment_date
                  FROM landscape_biodiversity_score
                 WHERE location_id = %s::uuid AND status IN ('verified', 'published')
                """,
                (location_id,),
            )
            assessment = _rows(cur)[0]

        return {
            "location_id": location_id,
            "habitats": [
                {**row, "record_count": int(row["record_count"]), "total_area_ha": _number(row["total_area_ha"])}
                for row in habitats
            ],
            "corridors": [
                {
                    **row,
                    "record_count": int(row["record_count"]),
                    "total_length_m": _number(row["total_length_m"]),
                    "mean_width_m": _number(row["mean_width_m"]),
                }
                for row in corridors
            ],
            "hedgerows": [
                {
                    **row,
                    "record_count": int(row["record_count"]),
                    "total_length_m": _number(row["total_length_m"]),
                    "mean_height_m": _number(row["mean_height_m"]),
                }
                for row in hedgerows
            ],
            "verified_buffer_checks": [
                {
                    **row,
                    "record_count": int(row["record_count"]),
                    "first_check_date": _date(row["first_check_date"]),
                    "last_check_date": _date(row["last_check_date"]),
                }
                for row in buffer_checks
            ],
            "verified_assessments": {
                "assessment_count": int(assessment["assessment_count"]),
                "mean_species_richness": _number(assessment["mean_species_richness"]),
                "mean_shannon_index": _number(assessment["mean_shannon_index"]),
                "mean_habitat_diversity_index": _number(assessment["mean_habitat_diversity_index"]),
                "mean_connectivity_score": _number(assessment["mean_connectivity_score"]),
                "mean_overall_score": _number(assessment["mean_overall_score"]),
                "first_assessment_date": _date(assessment["first_assessment_date"]),
                "last_assessment_date": _date(assessment["last_assessment_date"]),
            },
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
