"""Promotion ladder — the chess "promotion" tactic for regenerative value.

A pawn that reaches the 8th rank promotes to a queen. On the platform, raw
field data promotes through a value chain: sensor_reading -> metric_value
(verified) -> carbon_credit (published) -> retirement_certificate (issued).
Each completed rung strengthens the regenerative + financial outcome.

This module computes the per-location promotion ladder (read-only) so operators
can see where value is stuck and which locations are compounding fastest.
No writes are performed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def compute_promotion_ladder(
    conn, location_id: Optional[str] = None
) -> Dict[str, Any]:
    """Per-location funnel counts across the regenerative value chain.

    Rungs (in order):
      1. sensor_reading         -- raw field signal
      2. metric_value(verified) -- governed, human-verified metric
      3. carbon_credit(published) -- issued carbon credit
      4. retirement_certificate(issued) -- retired (claimed) credit
    """
    params: List[Any] = []
    loc_filter = ""
    if location_id:
        loc_filter = " AND location_id = %s"
        params.append(location_id)

    rows: List[Dict[str, Any]] = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT l.id AS location_id, l.name AS location_name,
                   (SELECT COUNT(*) FROM sensor_reading sr
                      WHERE sr.location_id = l.id) AS sensor_readings,
                   (SELECT COUNT(*) FROM metric_value mv
                      WHERE mv.location_id = l.id AND mv.verified = TRUE) AS verified_metrics,
                   (SELECT COUNT(*) FROM carbon_credit cc
                      WHERE cc.location_id = l.id AND cc.status = 'published') AS published_credits,
                   (SELECT COUNT(*) FROM retirement_certificate rc
                      WHERE rc.location_id = l.id AND rc.status IN ('issued','verified','published'))
                      AS issued_certificates
            FROM location l
            WHERE 1=1 {loc_filter}
            ORDER BY l.name
            """,
            params,
        )
        for r in cur.fetchall():
            rungs = [
                ("sensor_reading", r["sensor_readings"], "raw field signal"),
                ("metric_value", r["verified_metrics"], "governed, verified metric"),
                ("carbon_credit", r["published_credits"], "issued carbon credit"),
                ("retirement_certificate", r["issued_certificates"], "retired credit"),
            ]
            counts = [c for _, c, _ in rungs]
            ladder_complete = all(counts) and counts[-1] > 0
            rows.append({
                "location_id": str(r["location_id"]),
                "location_name": r["location_name"],
                "rungs": [
                    {
                        "rung": name,
                        "count": int(c),
                        "description": desc,
                        "reached": int(c) > 0,
                    }
                    for name, c, desc in rungs
                ],
                "top_rung_reached": counts[-1] > 0,
                "full_ladder": ladder_complete,
                "promoted_count": counts[-1],
            })

    return {
        "location_id": location_id,
        "ladder_depth": 4,
        "locations": rows,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Read-only promotion funnel; no writes performed.",
    }
