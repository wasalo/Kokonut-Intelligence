"""Output-capacity & national-income analog for the 8 Forms of Capital.

Read-only diagnostics that compare each Form's current stock to its
regenerative output capacity, surfacing under-mobilized Forms.
"""

from __future__ import annotations

from typing import Any, Dict, List

from services.common.database import get_connection
from services.common.logging import get_logger

logger = get_logger(__name__)

_CAPITAL_KEYS = [
    "natural", "financial", "social", "human", "material",
    "intellectual", "cultural", "health",
]

_MOBILIZATION_LOW = 0.5  # below this, a Form is considered under-mobilized


def _clean(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def assess_capacity(conn, location_id: str) -> Dict[str, Any]:
    """Compute a capacity snapshot for every Form of Capital at a location.

    Uses the latest capital_capacity_assessment row when present; otherwise
    derives a provisional mobilization_pct from available stock signals where
    possible. Pure read; never writes.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT foc.capital_key, foc.name,
                   ca.stock_estimate, ca.output_capacity_estimate, ca.mobilization_pct
            FROM form_of_capital foc
            LEFT JOIN LATERAL (
                SELECT *
                FROM capital_capacity_assessment a
                WHERE a.location_id = %s AND a.capital_key = foc.capital_key
                ORDER BY a.period_end DESC NULLS LAST, a.created_at DESC
                LIMIT 1
            ) ca ON TRUE
            WHERE foc.is_active = TRUE
            ORDER BY foc.sort_order
            """,
            (location_id,),
        )
        rows = [_clean(r) for r in cur.fetchall()]
    finally:
        cur.close()

    forms: List[Dict[str, Any]] = []
    for r in rows:
        stock = r.get("stock_estimate")
        capacity = r.get("output_capacity_estimate")
        mob = r.get("mobilization_pct")
        if mob is None and stock is not None and capacity:
            mob = round(float(stock) / float(capacity), 4) if capacity else None
        forms.append({
            "capital_key": r["capital_key"],
            "name": r.get("name"),
            "stock_estimate": stock,
            "output_capacity_estimate": capacity,
            "mobilization_pct": mob,
            "under_mobilized": (mob is not None and mob < _MOBILIZATION_LOW),
        })
    return {
        "location_id": location_id,
        "mobilization_threshold": _MOBILIZATION_LOW,
        "forms": forms,
        "under_mobilized_forms": [f["capital_key"] for f in forms if f["under_mobilized"]],
    }


def under_mobilized_forms(conn, location_id: str) -> List[str]:
    """Return capital keys whose mobilization is below threshold."""
    return assess_capacity(conn, location_id)["under_mobilized_forms"]


def capacity_cli(location_id: str) -> Dict[str, Any]:
    """CLI entrypoint: run capacity assessment against the live DB."""
    with get_connection() as conn:
        return assess_capacity(conn, location_id)
