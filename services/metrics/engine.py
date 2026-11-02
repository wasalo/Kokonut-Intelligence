"""
Metric Computation Engine

Reads metric definitions, dispatches to calculators, and writes results to metric_value.
"""

import json
import re
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

from services.common.errors import safe_exception_class
from services.common.logging import get_logger

from .calculators import CALCULATORS

logger = get_logger(__name__)

# Lazy event bus
_event_bus = None


def _get_event_bus(conn=None):
    global _event_bus
    if _event_bus is None:
        from services.events.bus import EventBus
        _event_bus = EventBus(conn=conn)
    return _event_bus

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def compute_metric(
    conn,
    metric_key: str,
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute and store a draft using the legacy CLI database adapter.

    The operator Gateway uses :func:`compute_metric_draft` followed by its
    bounded SQL-function writer instead. Keeping this adapter preserves the
    existing CLI behavior until its migration and rollout gate are complete.
    """
    draft = compute_metric_draft(conn, metric_key, location_id, period_start, period_end)
    if "error" in draft:
        return draft

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """INSERT INTO metric_value
                   (metric_id, location_id, period_start, period_end, value, unit,
                    computation_method, source_record_ids, computed_at, verified, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s::uuid[], NOW(), FALSE, %s)
               RETURNING id""",
            (
                draft["metric_id"],
                draft["location_id"],
                draft["period_start"],
                draft["period_end"],
                draft["value"],
                draft["unit"],
                draft["computation_method"],
                draft["source_record_ids"],
                json.dumps(draft["metadata"]),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "metric_key": draft["metric_key"],
            "display_name": draft["display_name"],
            "location_id": draft["location_id"],
            "period_start": draft["period_start"],
            "period_end": draft["period_end"],
            "value": draft["value"],
            "unit": draft["unit"],
            "metric_value_id": str(row["id"]) if row else None,
        }
    finally:
        cur.close()


def compute_metric_draft(
    conn,
    metric_key: str,
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one calculator and return a draft payload without persisting it.

    The caller owns transaction boundaries and the eventual write adapter. The
    function reads the active metric definition and source data on ``conn``;
    it neither commits nor writes ``metric_value``. This lets the Gateway keep
    signed location context on the same transaction used by its bounded
    ``create_location_metric_value_draft`` SQL function.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Load metric definition
        cur.execute("SELECT * FROM metric_definition WHERE metric_key = %s AND active = TRUE", (metric_key,))
        definition = cur.fetchone()
        if not definition:
            return {"error": f"Metric '{metric_key}' not found or inactive"}

        definition = dict(definition)

        # Find calculator
        calculator = CALCULATORS.get(metric_key)
        if not calculator:
            return {"error": f"No calculator registered for metric '{metric_key}'"}

        # Compute
        result = calculator(conn, location_id, period_start, period_end)

        if "error" in result:
            return result

        # Return a normalized payload for a caller-owned writer.
        metadata = result.get("metadata", {})
        if not isinstance(metadata, dict):
            return {"error": "Metric calculator returned invalid metadata"}
        metadata = dict(metadata)
        metadata["version"] = definition.get("version", 1)
        source_record_ids = result.get("source_record_ids", []) or []
        if isinstance(source_record_ids, str):
            source_record_ids = [v.strip().strip('"') for v in source_record_ids.strip("{}").split(",") if v.strip()]
        else:
            source_record_ids = [str(v) for v in source_record_ids if v]
        source_record_ids = [v for v in source_record_ids if UUID_RE.match(v)]

        return {
            "metric_key": metric_key,
            "display_name": definition["display_name"],
            "metric_id": str(definition["id"]),
            "location_id": location_id,
            "period_start": period_start,
            "period_end": period_end,
            "value": result.get("value"),
            "unit": definition.get("unit"),
            "computation_method": result.get("computation_method", metric_key),
            "source_record_ids": source_record_ids,
            "metadata": metadata,
        }
    finally:
        cur.close()


def compute_all(
    conn,
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute all active metrics that have registered calculators."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT metric_key FROM metric_definition WHERE active = TRUE ORDER BY metric_key")
    keys = [r["metric_key"] for r in cur.fetchall()]
    cur.close()

    results = {}
    errors = []
    for key in keys:
        if key in CALCULATORS:
            result = compute_metric(conn, key, location_id, period_start, period_end)
            if "error" in result:
                errors.append({"metric_key": key, "error": result["error"]})
            else:
                results[key] = result

    final = {
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "computed": results,
        "errors": errors,
        "total_computed": len(results),
        "total_errors": len(errors),
    }

    _publish_metric_event(conn, location_id, period_start, period_end, final)

    return final


def _publish_metric_event(conn, location_id: str, period_start, period_end, result: dict) -> None:
    """Publish a metric_computed event on the event bus."""
    try:
        bus = _get_event_bus(conn=conn)
        bus.publish(
            "metric_computed",
            {
                "location_id": location_id,
                "period_start": period_start,
                "period_end": period_end,
                "total_computed": result.get("total_computed", 0),
                "total_errors": result.get("total_errors", 0),
                "metric_keys": list(result.get("computed", {}).keys()),
            },
            source_table="metric_value",
            priority="normal",
        )
    except Exception as exc:
        logger.error(
            "Failed to publish metric_computed event (%s)", safe_exception_class(exc)
        )


def verify_metric_value(
    conn,
    metric_value_id: str,
    verified_by: str,
    verification_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify one computed metric value with explicit reviewer attribution."""
    if not verified_by:
        raise ValueError("verified_by is required")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            UPDATE metric_value
            SET verified = TRUE,
                verified_by = %s,
                verified_at = NOW(),
                verification_notes = %s
            WHERE id = %s AND verified = FALSE
            RETURNING id, metric_id, location_id, verified, verified_by, verified_at
            """,
            (verified_by, verification_notes, metric_value_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Metric value not found or already verified")
        conn.commit()
        return dict(row)
    finally:
        cur.close()


