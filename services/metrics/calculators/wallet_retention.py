"""
Wallet Retention Calculator

Formula: COUNT(DISTINCT wallet_id) WHERE active_in_current AND active_in_prior
Definition: Wallet active across defined periods
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_wallet_retention(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Default to last 60 days split into two 30-day windows
    if not period_end:
        period_end = datetime.utcnow().strftime("%Y-%m-%d")
    if not period_start:
        end_dt = datetime.strptime(period_end, "%Y-%m-%d")
        period_start = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")

    end_dt = datetime.strptime(period_end, "%Y-%m-%d")
    mid_dt = end_dt - timedelta(days=30)
    mid_date = mid_dt.strftime("%Y-%m-%d")

    # Wallets active in the current period (mid_date to period_end)
    cur.execute("""
        SELECT DISTINCT wae.wallet_id
        FROM wallet_activity_event wae
        JOIN wallet_profile wp ON wae.wallet_id = wp.id
        WHERE wp.owner_id = %s
          AND wae.block_timestamp::date >= %s
          AND wae.block_timestamp::date <= %s
    """, (location_id, mid_date, period_end))
    current_wallets = {str(r["wallet_id"]) for r in cur.fetchall()}

    # Wallets active in the prior period (period_start to mid_date)
    cur.execute("""
        SELECT DISTINCT wae.wallet_id
        FROM wallet_activity_event wae
        JOIN wallet_profile wp ON wae.wallet_id = wp.id
        WHERE wp.owner_id = %s
          AND wae.block_timestamp::date >= %s
          AND wae.block_timestamp::date < %s
    """, (location_id, period_start, mid_date))
    prior_wallets = {str(r["wallet_id"]) for r in cur.fetchall()}

    # Retention: wallets active in both periods
    retained = current_wallets & prior_wallets
    total_prior = len(prior_wallets)
    retention_rate = (len(retained) / total_prior * 100) if total_prior > 0 else 0.0

    cur.close()

    return {
        "value": round(retention_rate, 2),
        "computation_method": "COUNT(active_in_current AND active_in_prior) / COUNT(active_in_prior) * 100",
        "source_record_ids": [],
        "metadata": {
            "current_period_wallets": len(current_wallets),
            "prior_period_wallets": total_prior,
            "retained_wallets": len(retained),
            "period_start": period_start,
            "period_end": period_end,
            "cutoff_date": mid_date,
        },
    }
