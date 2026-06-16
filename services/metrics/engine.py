"""
Metric Computation Engine

Reads metric definitions, dispatches to calculators, and writes results to metric_value.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import psycopg2
import psycopg2.extras

from .calculators import CALCULATORS


def compute_metric(
    conn,
    metric_key: str,
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute a single metric and store the result."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Load metric definition
    cur.execute("SELECT * FROM metric_definition WHERE metric_key = %s AND active = TRUE", (metric_key,))
    definition = cur.fetchone()
    if not definition:
        cur.close()
        return {"error": f"Metric '{metric_key}' not found or inactive"}

    definition = dict(definition)

    # Find calculator
    calculator = CALCULATORS.get(metric_key)
    if not calculator:
        cur.close()
        return {"error": f"No calculator registered for metric '{metric_key}'"}

    # Compute
    result = calculator(conn, location_id, period_start, period_end)

    if "error" in result:
        cur.close()
        return result

    # Store result
    cur.execute("""
        INSERT INTO metric_value
            (metric_id, location_id, period_start, period_end, value, unit,
             computation_method, source_record_ids, computed_at, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
        RETURNING id
    """, (
        definition["id"],
        location_id,
        period_start,
        period_end,
        result.get("value"),
        definition.get("unit"),
        result.get("computation_method", metric_key),
        result.get("source_record_ids", []),
        json.dumps(result.get("metadata", {})),
    ))
    row = cur.fetchone()
    conn.commit()
    cur.close()

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

    return {
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "computed": results,
        "errors": errors,
        "total_computed": len(results),
        "total_errors": len(errors),
    }


# Need json for metadata serialization
import json
