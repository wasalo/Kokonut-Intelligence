"""Tenant-scoped, read-only pollinator health aggregates."""

from __future__ import annotations

from datetime import date, datetime
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_HABITAT_PAGE_SIZE = 50
_MAX_HABITAT_OFFSET = 10000
_MAX_HIVE_PAGE_SIZE = 50
_MAX_HIVE_OFFSET = 10000


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


def get_location_pollinator_habitat_details(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return a bounded operational habitat inventory under a separate detail grant."""
    try:
        operator_id = str(UUID(str(operator_id)))
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_HABITAT_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {_MAX_HABITAT_PAGE_SIZE}")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= _MAX_HABITAT_OFFSET:
        raise ValueError(f"offset must be between 0 and {_MAX_HABITAT_OFFSET}")

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
            action="read_detail",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT habitat.id::text, habitat.habitat_name, habitat.habitat_type,
                       habitat.area_m2::numeric, habitat.condition, habitat.status,
                       habitat.last_maintenance, habitat.updated_at
                  FROM public.pollinator_habitat AS habitat
                 WHERE habitat.location_id = %s::uuid
                 ORDER BY habitat.habitat_name, habitat.id
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            rows = _rows(cur)
        has_more = len(rows) > limit and offset + limit <= _MAX_HABITAT_OFFSET
        items = rows[:limit]
        for item in items:
            item["area_m2"] = _number(item["area_m2"])
            item["last_maintenance"] = _date(item["last_maintenance"])
            item["updated_at"] = item["updated_at"].isoformat()
        return {
            "location_id": location_id,
            "limit": limit,
            "offset": offset,
            "habitats": items,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_location_pollinator_hive_details(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded operational hive details under a separate detail grant."""
    try:
        operator_id = str(UUID(str(operator_id)))
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_HIVE_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {_MAX_HIVE_PAGE_SIZE}")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= _MAX_HIVE_OFFSET:
        raise ValueError(f"offset must be between 0 and {_MAX_HIVE_OFFSET}")

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
            action="read_detail",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT hive.id::text, hive.hive_id, hive.hive_type, hive.status,
                       hive.colony_strength, hive.colony_strength_score,
                       hive.queen_status, hive.frame_count, hive.inspection_date,
                       hive.last_maintenance_date, hive.updated_at
                  FROM public.hive_record AS hive
                 WHERE hive.location_id = %s::uuid
                 ORDER BY hive.hive_id, hive.id
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            rows = _rows(cur)
        has_more = len(rows) > limit and offset + limit <= _MAX_HIVE_OFFSET
        items = rows[:limit]
        for item in items:
            item["inspection_date"] = _date(item["inspection_date"])
            item["last_maintenance_date"] = _date(item["last_maintenance_date"])
            item["updated_at"] = item["updated_at"].isoformat()
            if item["colony_strength_score"] is not None:
                item["colony_strength_score"] = int(item["colony_strength_score"])
            if item["frame_count"] is not None:
                item["frame_count"] = int(item["frame_count"])
        return {
            "location_id": location_id,
            "limit": limit,
            "offset": offset,
            "hives": items,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def list_location_pollinator_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return a bounded private queue of independently reviewable pollinator records."""
    try:
        operator_id = str(UUID(str(operator_id)))
        location_id = str(UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise ValueError("offset must be between 0 and 10000")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="pollinator_health",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.list_location_pollinator_review_queue("
                "%s::uuid, %s::integer, %s::integer)",
                (location_id, limit, offset),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Pollinator review queue returned no result")
            result = row[0]
            if isinstance(result, str):
                import json

                result = json.loads(result)
            if (
                isinstance(result, dict)
                and result.get("has_more") is True
                and offset + limit > 10000
            ):
                result["has_more"] = False
                result["next_offset"] = None
            if (
                not isinstance(result, dict)
                or str(result.get("location_id")) != location_id
                or result.get("limit") != limit
                or result.get("offset") != offset
                or not isinstance(result.get("items"), list)
                or not isinstance(result.get("has_more"), bool)
                or isinstance(result.get("total"), bool)
                or not isinstance(result.get("total"), int)
                or result["total"] < 0
                or len(result["items"]) > limit
                or result.get("next_offset") != (offset + limit if result["has_more"] else None)
            ):
                raise RuntimeError("Pollinator review queue returned an invalid result")
            for item in result["items"]:
                if (
                    not isinstance(item, dict)
                    or item.get("record_type") not in {
                        "observation", "pesticide_impact", "hive_inspection"
                    }
                    or item.get("status") != "recorded"
                    or not isinstance(item.get("details"), dict)
                ):
                    raise RuntimeError("Pollinator review queue returned an invalid item")
                item["record_id"] = str(UUID(str(item["record_id"])))
                try:
                    occurred_on = date.fromisoformat(item.get("occurred_on"))
                except (TypeError, ValueError) as exc:
                    raise RuntimeError("Pollinator review queue returned an invalid date") from exc
                if occurred_on.isoformat() != item["occurred_on"]:
                    raise RuntimeError("Pollinator review queue returned an invalid date")
                item["updated_at"] = _date_time(item.get("updated_at"))
                item["created_at"] = _date_time(item.get("created_at"))
                item["details"] = _pollinator_review_details(item["record_type"], item["details"])
            return result
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def _date_time(value) -> str:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError("Pollinator review queue returned an invalid timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("Pollinator review queue returned a timestamp without timezone")
    return value.isoformat()


def _pollinator_review_details(record_type: str, details: dict) -> dict:
    fields = {
        "observation": {
            "pollinator_type", "count", "method", "duration_minutes", "species_name", "notes",
        },
        "pesticide_impact": {
            "product_name", "active_ingredient", "toxicity_class", "application_rate",
            "rate_unit", "area_treated_m2", "bloom_stage_at_application",
            "pollinator_distance_m", "pollinator_safe_period_days", "mortality_observed",
            "mortality_pct", "notes",
        },
        "hive_inspection": {
            "hive_id", "colony_strength", "colony_strength_score", "queen_status",
            "queen_seen", "varroa_count", "brood_pattern", "honey_stores",
            "disease_signs", "temperament", "population_estimate", "swarm_cells", "notes",
        },
    }
    allowed = fields[record_type]
    if set(details) - allowed:
        raise RuntimeError("Pollinator review queue returned an unexpected detail field")
    normalized = {}
    for field, value in details.items():
        if value is None:
            normalized[field] = None
        elif field in {
            "count", "duration_minutes", "pollinator_safe_period_days",
            "colony_strength_score", "varroa_count", "population_estimate",
        }:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeError("Pollinator review queue returned an invalid integer")
            normalized[field] = value
        elif field in {"mortality_observed", "queen_seen", "swarm_cells"}:
            if not isinstance(value, bool):
                raise RuntimeError("Pollinator review queue returned an invalid boolean")
            normalized[field] = value
        elif field in {
            "application_rate", "area_treated_m2", "pollinator_distance_m", "mortality_pct",
        }:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeError("Pollinator review queue returned an invalid number")
            normalized[field] = value
        elif isinstance(value, str) and len(value) <= 2000:
            normalized[field] = value
        else:
            raise RuntimeError("Pollinator review queue returned an invalid text detail")
    return normalized
