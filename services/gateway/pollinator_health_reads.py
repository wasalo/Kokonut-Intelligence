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
                SELECT pollinator_type, COUNT(*)::bigint AS observation_count,
                       AVG(count)::numeric AS avg_count,
                       MAX(count)::bigint AS max_count,
                       MIN(observation_date) AS first_observation_date,
                       MAX(observation_date) AS last_observation_date,
                       AVG(count) FILTER (
                           WHERE observation_date < CURRENT_DATE - INTERVAL '15 days'
                       )::numeric AS first_half_avg,
                       AVG(count) FILTER (
                           WHERE observation_date >= CURRENT_DATE - INTERVAL '15 days'
                       )::numeric AS second_half_avg,
                       SUM(count)::numeric AS total_count
                  FROM pollinator_observation
                 WHERE location_id = %s::uuid
                   AND observation_date >= CURRENT_DATE - INTERVAL '30 days'
                   AND status IN ('verified', 'reviewed')
                 GROUP BY pollinator_type
                 ORDER BY avg_count DESC NULLS LAST, pollinator_type
                """,
                (location_id,),
            )
            observation_trends = _rows(cur)

            for row in observation_trends:
                first_avg = _number(row.pop("first_half_avg"))
                second_avg = _number(row.pop("second_half_avg"))
                row["avg_count"] = _number(row["avg_count"])
                row["total_count"] = _number(row["total_count"])
                row["observation_count"] = int(row["observation_count"])
                row["max_count"] = int(row["max_count"]) if row["max_count"] is not None else None
                row["first_observation_date"] = _date(row["first_observation_date"])
                row["last_observation_date"] = _date(row["last_observation_date"])
                if first_avg is not None and first_avg > 0 and second_avg is not None:
                    change = (second_avg - first_avg) / first_avg * 100
                    row["trend"] = "increasing" if change > 10 else "decreasing" if change < -10 else "stable"
                    row["change_pct"] = round(change, 1)
                else:
                    row["trend"] = "insufficient_data"
                    row["change_pct"] = 0

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
                       COUNT(*) FILTER (
                           WHERE application_date >= CURRENT_DATE - INTERVAL '90 days'
                       )::bigint AS recent_record_count,
                       COUNT(*) FILTER (
                           WHERE application_date >= CURRENT_DATE - INTERVAL '90 days'
                             AND pollinator_mortality_observed = TRUE
                       )::bigint AS recent_mortality_events,
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
            recent_pesticide_count = 0
            recent_mortality_events = 0
            recent_risk_counts = {"low": 0, "moderate": 0, "high": 0, "very_high": 0, "unknown": 0}
            for row in pesticide_impacts:
                recent_count = int(row.pop("recent_record_count"))
                mortality_count = int(row.pop("recent_mortality_events"))
                recent_pesticide_count += recent_count
                recent_mortality_events += mortality_count
                risk_key = row["toxicity_class"] if row["toxicity_class"] in recent_risk_counts else "unknown"
                recent_risk_counts[risk_key] += recent_count

            cur.execute(
                """
                SELECT colony_strength, queen_status,
                       COUNT(*)::bigint AS hive_count,
                       SUM(honey_yield_kg)::numeric AS total_honey_yield_kg,
                       AVG(varroa_count)::numeric AS mean_varroa_count,
                       COUNT(colony_strength_score)::bigint AS strength_score_count,
                       AVG(colony_strength_score)::numeric AS mean_strength_score,
                       MAX(inspection_date) AS last_inspection_date
                  FROM hive_record
                 WHERE location_id = %s::uuid AND status = 'active'
                 GROUP BY colony_strength, queen_status
                 ORDER BY colony_strength NULLS FIRST, queen_status NULLS FIRST
                """,
                (location_id,),
            )
            hives = _rows(cur)

            total_active_hives = 0
            scored_active_hives = 0
            strength_score_total = 0.0
            for row in hives:
                hive_count = int(row["hive_count"])
                score_count = int(row.pop("strength_score_count"))
                mean_score = _number(row.pop("mean_strength_score"))
                total_active_hives += hive_count
                scored_active_hives += score_count
                if mean_score is not None:
                    strength_score_total += mean_score * score_count

        high_risk_count = recent_risk_counts["high"] + recent_risk_counts["very_high"]
        overall_risk = (
            "critical" if recent_mortality_events or high_risk_count >= 3
            else "elevated" if high_risk_count
            else "low"
        )

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
            "observation_trends": observation_trends,
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
            "pesticide_risk_summary": {
                "period_days": 90,
                "total_applications": recent_pesticide_count,
                "overall_risk": overall_risk,
                "risk_distribution": recent_risk_counts,
                "mortality_events": recent_mortality_events,
            },
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
            "active_hive_summary": {
                "total_hives": total_active_hives,
                "avg_colony_strength_score": (
                    round(strength_score_total / scored_active_hives, 1)
                    if scored_active_hives
                    else None
                ),
            },
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
