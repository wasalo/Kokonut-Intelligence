"""Time-Delay Mapper — tracks action-to-effect delays in farm systems.

Models the time lag between interventions and their observable effects,
enabling better planning and expectation management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import DEFAULT_TIME_DELAYS


class DelayMapper:
    """Maps and manages action-to-effect delays."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def get_delay(
        self, action_type: str, effect_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get the expected delay for an action-effect pair."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM time_delay
            WHERE action_type = %s AND effect_type = %s AND is_enabled = TRUE
        """, (action_type, effect_type))

        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return dict(row)

    def adjust_for_delay(
        self,
        action_date: str,
        action_type: str,
        effect_type: str,
    ) -> Dict[str, Any]:
        """Calculate when to expect an effect after an action.

        Returns expected effect date and confidence interval.
        """
        delay = self.get_delay(action_type, effect_type)
        if delay is None:
            return {
                "action_date": action_date,
                "expected_effect_date": None,
                "confidence": "unknown",
                "message": f"No delay data for {action_type} → {effect_type}",
            }

        action_dt = datetime.fromisoformat(action_date.replace("Z", "+00:00"))
        expected_hours = delay["expected_delay_hours"]
        min_hours = delay.get("min_delay_hours", expected_hours)
        max_hours = delay.get("max_delay_hours", expected_hours)

        expected_date = action_dt + timedelta(hours=expected_hours)
        earliest_date = action_dt + timedelta(hours=min_hours)
        latest_date = action_dt + timedelta(hours=max_hours)

        return {
            "action_date": action_date,
            "action_type": action_type,
            "effect_type": effect_type,
            "expected_effect_date": expected_date.isoformat(),
            "earliest_effect_date": earliest_date.isoformat(),
            "latest_effect_date": latest_date.isoformat(),
            "expected_hours": expected_hours,
            "range_hours": (min_hours, max_hours),
            "confidence": "high" if expected_hours < 1000 else "moderate",
        }

    def measure_actual_delay(
        self,
        action_id: str,
        effect_id: str,
        action_date: str,
        effect_date: str,
    ) -> Dict[str, Any]:
        """Compare actual delay against expected delay."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Look up expected delay
        cur.execute("""
            SELECT expected_delay_hours, min_delay_hours, max_delay_hours
            FROM time_delay LIMIT 1
        """)
        row = cur.fetchone()

        action_dt = datetime.fromisoformat(action_date.replace("Z", "+00:00"))
        effect_dt = datetime.fromisoformat(effect_date.replace("Z", "+00:00"))
        actual_hours = (effect_dt - action_dt).total_seconds() / 3600

        result = {
            "action_id": action_id,
            "effect_id": effect_id,
            "actual_hours": round(actual_hours, 1),
        }

        if row:
            row = dict(row)
            expected = row["expected_delay_hours"]
            result["expected_hours"] = expected
            result["deviation_pct"] = round(
                (actual_hours - expected) / expected * 100, 1
            ) if expected > 0 else None
            result["within_range"] = (
                row["min_delay_hours"] <= actual_hours <= row["max_delay_hours"]
            )

        cur.close()
        return result

    def list_delays(
        self, domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all delay mappings."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if domain:
            cur.execute("""
                SELECT * FROM time_delay WHERE domain = %s AND is_enabled = TRUE
                ORDER BY action_type
            """, (domain,))
        else:
            cur.execute("""
                SELECT * FROM time_delay WHERE is_enabled = TRUE
                ORDER BY domain, action_type
            """)

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def list_domains(self) -> List[str]:
        """List all domains with delay data."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT DISTINCT domain FROM time_delay WHERE is_enabled = TRUE
            ORDER BY domain
        """)

        rows = cur.fetchall()
        cur.close()
        return [r["domain"] for r in rows]
