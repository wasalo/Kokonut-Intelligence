"""Reference-class forecasting (optimism-bias dampening).

Implements the business-plan concept of *reference class forecasting*:
a location's self-projection is blended with the realized median of
comparable (established) locations to dampen optimism bias and reduce the
risk of cost overruns / revenue shortfalls. Read-only analysis; never
writes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


def apply_reference_class(
    conn, location_id: str,
    metric: str = "crop_noi",
    alpha: float = 0.5,
    comparable_org_only: bool = True,
) -> Dict[str, Any]:
    """Blend a location's projection with the comparable-location median.

    alpha = weight on the subject's own projection (optimism). Lower alpha
    leans more on the reference class (more conservative).
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between 0 and 1")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Subject's own latest projection for the metric.
    cur.execute(
        """
        SELECT value FROM forecast_output
        WHERE location_id = %(loc)s AND metric_name = %(metric)s
        ORDER BY calculated_at DESC LIMIT 1
        """,
        {"loc": location_id, "metric": metric},
    )
    row = cur.fetchone()
    projected = float(row["value"]) if row and row["value"] is not None else None

    # Comparable locations: same organization (or all), excluding subject.
    org_filter = ""
    params: Dict[str, Any] = {"loc": location_id, "metric": metric}
    if comparable_org_only:
        cur.execute("SELECT organization_id FROM location WHERE id = %(loc)s", {"loc": location_id})
        org = cur.fetchone()
        if org and org.get("organization_id"):
            org_filter = "AND l.organization_id = %(org)s"
            params["org"] = org["organization_id"]

    cur.execute(
        f"""
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ns.noi) AS median_noi,
               COUNT(DISTINCT ns.location_id) AS n_loc
        FROM noi_snapshot ns
        JOIN location l ON l.id = ns.location_id
        WHERE ns.location_id <> %(loc)s {org_filter}
          AND ns.noi IS NOT NULL
        """,
        params,
    )
    ref = cur.fetchone()
    reference_median = float(ref["median_noi"]) if ref and ref["median_noi"] is not None else None
    comparable_count = int(ref["n_loc"] or 0) if ref else 0

    damped = None
    if projected is not None and reference_median is not None:
        damped = round(alpha * projected + (1.0 - alpha) * reference_median, 4)

    return {
        "metric": metric,
        "alpha": alpha,
        "projected": projected,
        "reference_median": reference_median,
        "comparable_locations": comparable_count,
        "damped_estimate": damped,
        "note": (
            "Blend of self-projection and comparable-location median to curb optimism bias."
            if damped is not None else
            "Insufficient data to dampen (need both a projection and comparable actuals)."
        ),
    }
