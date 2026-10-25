"""Tenant-scoped read-only aggregates for verified waste operations."""

from __future__ import annotations

import json
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


def _number(value) -> float:
    return float(value or 0)


def _optional_number(value):
    return float(value) if value is not None else None


def _iso(value):
    return value.isoformat() if value is not None else None


def _date_groups(rows, count_key: str, quantity_key: str | None = None) -> list[dict]:
    result = []
    for row in rows:
        item = {key: value for key, value in row.items() if key not in {
            count_key, "total_quantity", "first_date", "last_date"
        }}
        item["record_count"] = int(row[count_key] or 0)
        if quantity_key is not None:
            item[quantity_key] = _number(row["total_quantity"])
        item["first_date"] = _iso(row["first_date"])
        item["last_date"] = _iso(row["last_date"])
        result.append(item)
    return result


def get_location_waste_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded verified waste, composting, recycling, and incident data.

    The response contains no incident narratives, affected-area descriptions,
    reporter/destination identities, costs, notes, IDs, or arbitrary metadata.
    Quantity groups retain their recorded unit; no cross-unit total is derived.
    Compost output/yield and process measures are aggregate descriptions, not
    quality certification or compliance determinations.
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
            resource="waste_management",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT waste_type, disposal_method, quantity_unit,
                       COUNT(*)::bigint AS record_count,
                       SUM(quantity_kg)::numeric AS total_quantity,
                       MIN(record_date) AS first_date,
                       MAX(record_date) AS last_date
                  FROM waste_stream
                 WHERE location_id = %s::uuid AND status = 'verified'
                 GROUP BY waste_type, disposal_method, quantity_unit
                 ORDER BY waste_type, disposal_method NULLS FIRST, quantity_unit
                """,
                (location_id,),
            )
            waste_streams = _date_groups(_rows(cur), "record_count", "total_quantity")

            cur.execute(
                """
                SELECT feedstock_type, compost_method,
                       COUNT(*)::bigint AS record_count,
                       SUM(feedstock_kg)::numeric AS total_quantity,
                       SUM(finished_volume_kg)::numeric AS total_output_kg,
                       CASE
                           WHEN SUM(feedstock_kg) > 0
                           THEN ROUND((
                               SUM(finished_volume_kg) / SUM(feedstock_kg) * 100
                           )::numeric, 1)
                           ELSE NULL
                       END AS weighted_yield_pct,
                       ROUND(AVG(
                           finished_volume_kg / NULLIF(feedstock_kg, 0) * 100
                       ) FILTER (
                           WHERE finished_volume_kg IS NOT NULL AND feedstock_kg > 0
                       )::numeric, 1)
                           AS mean_batch_yield_pct,
                       ROUND(AVG(duration_days) FILTER (
                           WHERE finished_volume_kg IS NOT NULL
                       )::numeric, 1) AS mean_duration_days,
                       ROUND(AVG(temperature_c)::numeric, 1) AS mean_temperature_c,
                       ROUND(AVG(moisture_pct)::numeric, 1) AS mean_moisture_pct,
                       COUNT(*) FILTER (WHERE quality_grade IS NOT NULL)::bigint
                           AS graded_batches,
                       MIN(compost_date) AS first_date,
                       MAX(compost_date) AS last_date
                  FROM composting_record
                 WHERE location_id = %s::uuid AND status = 'verified'
                 GROUP BY feedstock_type, compost_method
                 ORDER BY feedstock_type, compost_method
                """,
                (location_id,),
            )
            composting = _date_groups(_rows(cur), "record_count", "feedstock_kg")
            for row in composting:
                row["total_output_kg"] = _number(row.pop("total_output_kg"))
                for key in (
                    "weighted_yield_pct",
                    "mean_batch_yield_pct",
                    "mean_duration_days",
                    "mean_temperature_c",
                    "mean_moisture_pct",
                ):
                    row[key] = _optional_number(row[key])
                row["graded_batches"] = int(row["graded_batches"] or 0)

            cur.execute(
                """
                SELECT material_type,
                       COUNT(*)::bigint AS record_count,
                       SUM(quantity_kg)::numeric AS total_quantity,
                       MIN(record_date) AS first_date,
                       MAX(record_date) AS last_date
                  FROM recycling_log
                 WHERE location_id = %s::uuid AND status = 'verified'
                 GROUP BY material_type
                 ORDER BY material_type
                """,
                (location_id,),
            )
            recycling = _date_groups(_rows(cur), "record_count", "quantity_kg")

            cur.execute(
                "SELECT kokonut_security.summarize_location_pollution_incidents(%s::uuid)",
                (location_id,),
            )
            row = cur.fetchone()
            incidents = row[0] if row else None
            if isinstance(incidents, str):
                incidents = json.loads(incidents)
            incident_fields = {
                "severity", "status", "record_count", "first_date", "last_date",
            }
            if (
                not isinstance(incidents, list)
                or any(
                    not isinstance(item, dict)
                    or set(item) != incident_fields
                    or not isinstance(item.get("severity"), str)
                    or item.get("severity") not in {
                        "low", "medium", "high", "critical",
                    }
                    or not isinstance(item.get("status"), str)
                    or item.get("status") not in {
                        "open", "investigating", "remediation", "resolved", "closed",
                    }
                    or isinstance(item.get("record_count"), bool)
                    or not isinstance(item.get("record_count"), int)
                    or item["record_count"] < 1
                    or item.get("first_date") is not None
                    and not isinstance(item.get("first_date"), str)
                    or item.get("last_date") is not None
                    and not isinstance(item.get("last_date"), str)
                    for item in incidents
                )
            ):
                raise RuntimeError("Incident summary returned an invalid result")

        return {
            "location_id": location_id,
            "waste_streams": waste_streams,
            "composting": composting,
            "recycling": recycling,
            "pollution_incidents": incidents,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
