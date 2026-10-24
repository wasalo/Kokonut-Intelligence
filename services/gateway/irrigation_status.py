"""Tenant-scoped, read-only irrigation-zone status projection."""

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


def _moisture_status(current, trigger, target_min, target_max) -> str:
    if current is None:
        return "no_data"
    if trigger is not None and current < trigger:
        return "below_trigger"
    if target_min is not None and current < target_min:
        return "below_target"
    if target_min is not None and target_max is not None and target_min <= current <= target_max:
        return "in_range"
    return "above_target"


def get_location_irrigation_status(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded active-zone status without device or arbitrary metadata."""
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
            resource="precision_irrigation",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM irrigation_zone
                 WHERE location_id = %s::uuid AND status = 'active'
                """,
                (location_id,),
            )
            total_active_zones = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT iz.id, iz.name, iz.zone_code, iz.soil_type,
                       iz.area_m2, iz.depth_cm, iz.status AS zone_status,
                       target.target_min_pct, target.target_max_pct,
                       target.irrigation_trigger_pct, target.refill_to_pct,
                       target.growth_stage,
                       moisture.value AS current_moisture_pct,
                       moisture.reading_at AS last_moisture_reading,
                       schedule.scheduled_start AS next_irrigation_start,
                       schedule.planned_volume_l AS next_irrigation_volume_l,
                       schedule.status AS next_irrigation_status,
                       event.started_at AS last_irrigation_at,
                       event.volume_l AS last_irrigation_volume_l
                  FROM irrigation_zone AS iz
                  LEFT JOIN LATERAL (
                      SELECT target_min_pct, target_max_pct,
                             irrigation_trigger_pct, refill_to_pct, growth_stage
                        FROM soil_moisture_target
                       WHERE zone_id = iz.id
                       ORDER BY created_at DESC, id DESC
                       LIMIT 1
                  ) AS target ON TRUE
                  LEFT JOIN LATERAL (
                      SELECT sr.value,
                             sr.reading_date + COALESCE(sr.reading_time, TIME '00:00') AS reading_at
                        FROM sensor_reading AS sr
                       WHERE sr.sensor_id = iz.sensor_device_id
                         AND sr.location_id = iz.location_id
                         AND sr.sensor_type = 'soil_moisture'
                       ORDER BY sr.reading_date DESC, sr.reading_time DESC NULLS LAST, sr.id DESC
                       LIMIT 1
                  ) AS moisture ON TRUE
                  LEFT JOIN LATERAL (
                      SELECT scheduled_start, planned_volume_l, status
                        FROM irrigation_schedule
                       WHERE zone_id = iz.id AND status = 'pending'
                       ORDER BY scheduled_start, id
                       LIMIT 1
                  ) AS schedule ON TRUE
                  LEFT JOIN LATERAL (
                      SELECT started_at, volume_l
                        FROM irrigation_event
                       WHERE zone_id = iz.id
                       ORDER BY started_at DESC, id DESC
                       LIMIT 1
                  ) AS event ON TRUE
                 WHERE iz.location_id = %s::uuid
                   AND iz.status = 'active'
                 ORDER BY iz.name, iz.id
                 LIMIT %s OFFSET %s
                """,
                (location_id, limit + 1, offset),
            )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        zones = []
        for row in rows[:limit]:
            current = _number(row["current_moisture_pct"])
            trigger = _number(row["irrigation_trigger_pct"])
            target_min = _number(row["target_min_pct"])
            target_max = _number(row["target_max_pct"])
            zones.append(
                {
                    "zone_id": str(row["id"]),
                    "name": row["name"],
                    "zone_code": row["zone_code"],
                    "soil_type": row["soil_type"],
                    "area_m2": _number(row["area_m2"]),
                    "depth_cm": _number(row["depth_cm"]),
                    "zone_status": row["zone_status"],
                    "current_moisture_pct": current,
                    "last_moisture_reading": _iso(row["last_moisture_reading"]),
                    "moisture_status": _moisture_status(
                        current, trigger, target_min, target_max
                    ),
                    "target_min_pct": target_min,
                    "target_max_pct": target_max,
                    "irrigation_trigger_pct": trigger,
                    "refill_to_pct": _number(row["refill_to_pct"]),
                    "growth_stage": row["growth_stage"],
                    "next_irrigation_start": _iso(row["next_irrigation_start"]),
                    "next_irrigation_volume_l": _number(row["next_irrigation_volume_l"]),
                    "next_irrigation_status": row["next_irrigation_status"],
                    "last_irrigation_at": _iso(row["last_irrigation_at"]),
                    "last_irrigation_volume_l": _number(row["last_irrigation_volume_l"]),
                }
            )

        return {
            "location_id": location_id,
            "total_active_zones": total_active_zones,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
            "zones": zones,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
