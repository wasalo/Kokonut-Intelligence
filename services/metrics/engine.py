"""
Metric Computation Engine

Reads metric definitions, dispatches to calculators, and writes results to metric_value.
"""

import json
from datetime import datetime, timezone
import re
from typing import Dict, Any, Optional, List

import psycopg2
import psycopg2.extras

from .calculators import CALCULATORS

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
    verified: bool = False,
) -> Dict[str, Any]:
    """Compute a single metric and store the result."""
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

        # Store result with version metadata
        metadata = result.get("metadata", {})
        metadata["version"] = definition.get("version", 1)
        source_record_ids = result.get("source_record_ids", []) or []
        if isinstance(source_record_ids, str):
            source_record_ids = [v.strip().strip('"') for v in source_record_ids.strip("{}").split(",") if v.strip()]
        else:
            source_record_ids = [str(v) for v in source_record_ids if v]
        source_record_ids = [v for v in source_record_ids if UUID_RE.match(v)]

        cur.execute("""
            INSERT INTO metric_value
                (metric_id, location_id, period_start, period_end, value, unit,
                 computation_method, source_record_ids, computed_at, verified, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::uuid[], NOW(), %s, %s)
            RETURNING id
        """, (
            definition["id"],
            location_id,
            period_start,
            period_end,
            result.get("value"),
            definition.get("unit"),
            result.get("computation_method", metric_key),
            source_record_ids,
            verified,
            json.dumps(metadata),
        ))
        row = cur.fetchone()
        conn.commit()

        return {
            "metric_key": metric_key,
            "display_name": definition["display_name"],
            "location_id": location_id,
            "period_start": period_start,
            "period_end": period_end,
            "value": result.get("value"),
            "unit": definition.get("unit"),
            "metric_value_id": str(row["id"]) if row else None,
        }
    finally:
        cur.close()


def compute_all(
    conn,
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    verified: bool = False,
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
            result = compute_metric(conn, key, location_id, period_start, period_end, verified=verified)
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
    except Exception:
        pass  # Never fail metric computation due to event bus errors



