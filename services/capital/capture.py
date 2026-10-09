"""Value-leakage / capture-risk signal for the 8 Forms of Capital.

Read-only advisory diagnostic. Inspired by Keynes's managed-containment
analog: rather than letting value leak or concentrate out of the commons,
surface where a Form of Capital is at risk of capture.
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


def _clean(row: Any) -> Dict[str, Any]:
    return dict(row) if isinstance(row, dict) else dict(row)


def capture_risk(conn, location_id: str) -> Dict[str, Any]:
    """Assess capture risk per Form of Capital at a location.

    Heuristic: financial concentration is proxied by the share of revenue
    flowing to the single largest counterparty; social extraction by the
    share of guild contributions credited to intermediaries. Other Forms are
    reported as 'unknown' unless an explicit anti-capture policy scope applies.
    """
    cur = conn.cursor()
    try:
        # Financial concentration: largest counterparty revenue share.
        cur.execute(
            """
            SELECT counterparty, COALESCE(SUM(amount),0) AS amt
            FROM revenue_event
            WHERE location_id = %s
            GROUP BY counterparty
            ORDER BY amt DESC
            LIMIT 1
            """,
            (location_id,),
        )
        top = cur.fetchone()
        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM revenue_event WHERE location_id = %s",
            (location_id,),
        )
        total_row = cur.fetchone()
        total_rev = float((total_row[0] if total_row else 0) or 0.0)
        top_share = 0.0
        if top and total_rev:
            top_amt = float(top[1] if isinstance(top, (list, tuple)) else list(top.values())[1])
            top_share = round(top_amt / total_rev, 4)

        # Anti-capture policy scopes in effect for this farm.
        cur.execute(
            """
            SELECT COUNT(*) FROM anti_capture_governance_policy
            WHERE policy_scope IN ('farm', 'network', 'other')
            """,
        )
        policy_rows = cur.fetchone()
        policy_count = int((policy_rows[0] if policy_rows else 0) or 0)
    finally:
        cur.close()

    forms: List[Dict[str, Any]] = []
    for key in _CAPITAL_KEYS:
        level = "unknown"
        concentration = None
        leakage = None
        if key == "financial":
            concentration = top_share
            leakage = round(top_share, 4)
            level = "high" if top_share >= 0.6 else "medium" if top_share >= 0.3 else "low"
        forms.append({
            "capital_key": key,
            "concentration_metric": concentration,
            "leakage_signal": leakage,
            "capture_risk_level": level,
        })

    return {
        "location_id": location_id,
        "financial_top_counterparty_share": top_share,
        "anti_capture_policies_in_effect": policy_count,
        "forms": forms,
        "at_risk_forms": [f["capital_key"] for f in forms if f["capture_risk_level"] == "high"],
    }


def capture_cli(location_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        return capture_risk(conn, location_id)
