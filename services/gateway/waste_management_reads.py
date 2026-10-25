"""Tenant-scoped read-only aggregates for verified waste operations."""

from __future__ import annotations

import json
import math
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _decode_summary(value, location_id: str, days: int) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Waste summary returned invalid JSON") from exc
    expected = {
        "location_id", "waste_summary", "waste_streams", "composting",
        "composting_efficiency", "recycling",
    }
    if not isinstance(value, dict) or set(value) != expected or value.get("location_id") != location_id:
        raise RuntimeError("Waste summary returned an invalid result")

    def rows(name, fields, string_fields, nullable_string_fields, number_fields, nullable_number_fields):
        items = value[name]
        if not isinstance(items, list):
            raise RuntimeError("Waste summary returned an invalid result")
        for item in items:
            if not isinstance(item, dict) or set(item) != fields:
                raise RuntimeError("Waste summary returned an invalid group")
            if any(not isinstance(item.get(field), str) for field in string_fields):
                raise RuntimeError("Waste summary returned an invalid group")
            if any(
                item.get(field) is not None and not isinstance(item.get(field), str)
                for field in nullable_string_fields
            ):
                raise RuntimeError("Waste summary returned an invalid group")
            count = item.get("record_count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise RuntimeError("Waste summary returned an invalid group")
            for field in ("first_date", "last_date"):
                if item.get(field) is not None and not isinstance(item.get(field), str):
                    raise RuntimeError("Waste summary returned an invalid group")
            for field in number_fields:
                number = item.get(field)
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                    raise RuntimeError("Waste summary returned an invalid group")
                item[field] = float(number)
            for field in nullable_number_fields:
                number = item.get(field)
                if number is not None:
                    if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                        raise RuntimeError("Waste summary returned an invalid group")
                    item[field] = float(number)
        return items

    value["waste_streams"] = rows(
        "waste_streams",
        {"waste_type", "disposal_method", "quantity_unit", "record_count", "total_quantity", "first_date", "last_date"},
        {"waste_type"}, {"disposal_method", "quantity_unit"}, {"total_quantity"}, set(),
    )
    value["composting"] = rows(
        "composting",
        {
            "feedstock_type", "compost_method", "record_count", "feedstock_kg",
            "total_output_kg", "weighted_yield_pct", "mean_batch_yield_pct",
            "mean_duration_days", "mean_temperature_c", "mean_moisture_pct",
            "graded_batches", "first_date", "last_date",
        },
        {"feedstock_type", "compost_method"}, set(), {"feedstock_kg", "total_output_kg"},
        {"weighted_yield_pct", "mean_batch_yield_pct", "mean_duration_days", "mean_temperature_c", "mean_moisture_pct"},
    )
    for item in value["composting"]:
        graded = item.get("graded_batches")
        if isinstance(graded, bool) or not isinstance(graded, int) or graded < 0 or graded > item["record_count"]:
            raise RuntimeError("Waste summary returned an invalid group")
    value["recycling"] = rows(
        "recycling",
        {"material_type", "record_count", "quantity_kg", "first_date", "last_date"},
        {"material_type"}, set(), {"quantity_kg"}, set(),
    )
    waste_summary = value["waste_summary"]
    if (
        not isinstance(waste_summary, dict)
        or set(waste_summary) != {
            "period_days", "total_waste_kg", "total_records", "by_type",
            "by_disposal_method",
        }
        or waste_summary.get("period_days") != days
        or isinstance(waste_summary.get("total_records"), bool)
        or not isinstance(waste_summary.get("total_records"), int)
        or waste_summary["total_records"] < 0
        or isinstance(waste_summary.get("total_waste_kg"), bool)
        or not isinstance(waste_summary.get("total_waste_kg"), (int, float))
        or not math.isfinite(waste_summary["total_waste_kg"])
    ):
        raise RuntimeError("Waste period summary returned an invalid result")
    waste_summary["total_waste_kg"] = float(waste_summary["total_waste_kg"])
    for key, nullable in (("by_type", False), ("by_disposal_method", True)):
        groups = waste_summary.get(key)
        if not isinstance(groups, list):
            raise RuntimeError("Waste period summary returned an invalid result")
        dimension = "waste_type" if key == "by_type" else "disposal_method"
        for item in groups:
            if (
                not isinstance(item, dict)
                or set(item) != {dimension, "total_kg", "record_count"}
                or (item[dimension] is not None and not isinstance(item[dimension], str))
                or (item[dimension] is None and not nullable)
                or isinstance(item.get("record_count"), bool)
                or not isinstance(item.get("record_count"), int)
                or item["record_count"] < 1
                or isinstance(item.get("total_kg"), bool)
                or not isinstance(item.get("total_kg"), (int, float))
                or not math.isfinite(item["total_kg"])
            ):
                raise RuntimeError("Waste period summary returned an invalid group")
            item["total_kg"] = float(item["total_kg"])

    efficiency = value["composting_efficiency"]
    if (
        not isinstance(efficiency, dict)
        or set(efficiency) != {
            "location_id", "total_batches", "total_feedstock_kg", "total_output_kg",
            "overall_yield_pct", "by_method", "recent_quality",
        }
        or efficiency.get("location_id") != location_id
        or isinstance(efficiency.get("total_batches"), bool)
        or not isinstance(efficiency.get("total_batches"), int)
        or efficiency["total_batches"] < 0
    ):
        raise RuntimeError("Composting efficiency returned an invalid result")
    for field in ("total_feedstock_kg", "total_output_kg"):
        number = efficiency.get(field)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise RuntimeError("Composting efficiency returned an invalid result")
        efficiency[field] = float(number)
    overall_yield = efficiency.get("overall_yield_pct")
    if overall_yield is not None:
        if isinstance(overall_yield, bool) or not isinstance(overall_yield, (int, float)) or not math.isfinite(overall_yield):
            raise RuntimeError("Composting efficiency returned an invalid result")
        efficiency["overall_yield_pct"] = float(overall_yield)

    methods = efficiency.get("by_method")
    if not isinstance(methods, list):
        raise RuntimeError("Composting efficiency returned an invalid result")
    for item in methods:
        if (
            not isinstance(item, dict)
            or set(item) != {
                "compost_method", "batches", "avg_yield_pct", "avg_feedstock_kg",
                "avg_output_kg", "avg_duration_days",
            }
            or not isinstance(item.get("compost_method"), str)
            or isinstance(item.get("batches"), bool)
            or not isinstance(item.get("batches"), int)
            or item["batches"] < 1
        ):
            raise RuntimeError("Composting efficiency returned an invalid method")
        for field in ("avg_yield_pct", "avg_feedstock_kg", "avg_output_kg", "avg_duration_days"):
            number = item.get(field)
            if number is not None:
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                    raise RuntimeError("Composting efficiency returned an invalid method")
                item[field] = float(number)

    recent = efficiency.get("recent_quality")
    if not isinstance(recent, list) or len(recent) > 10:
        raise RuntimeError("Composting quality summary returned an invalid result")
    for item in recent:
        if not isinstance(item, dict) or set(item) != {
            "ph", "moisture_pct", "temperature_c", "output_yield_pct", "recorded_at",
        } or not isinstance(item.get("recorded_at"), str):
            raise RuntimeError("Composting quality summary returned an invalid reading")
        for field in ("ph", "moisture_pct", "temperature_c", "output_yield_pct"):
            number = item.get(field)
            if number is not None:
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                    raise RuntimeError("Composting quality summary returned an invalid reading")
                item[field] = float(number)
    return value


def get_location_waste_summary(
    operator_id: str,
    location_id: str,
    *,
    days: int = 30,
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
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
        raise ValueError("days must be an integer between 1 and 3650")

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
                "SELECT kokonut_security.summarize_location_waste_operations(%s::uuid, %s::integer)",
                (location_id, days),
            )
            row = cur.fetchone()
            aggregates = _decode_summary(row[0] if row else None, location_id, days)

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
            "waste_summary": aggregates["waste_summary"],
            "waste_streams": aggregates["waste_streams"],
            "composting": aggregates["composting"],
            "composting_efficiency": aggregates["composting_efficiency"],
            "recycling": aggregates["recycling"],
            "pollution_incidents": incidents,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
