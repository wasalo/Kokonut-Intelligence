"""Flag Monitor — tracks observable warning indicators for threats,
evaluates thresholds, and generates alerts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class FlagMonitor:
    """Monitors and evaluates warning flags for threats."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def create_flag(
        self,
        threat_id: str,
        flag_name: str,
        description: Optional[str] = None,
        indicator_type: str = "quantitative",
        threshold_critical: Optional[float] = None,
        threshold_warning: Optional[float] = None,
        threshold_normal: Optional[float] = None,
        comparison_operator: str = "gte",
        unit: Optional[str] = None,
        data_source: Optional[str] = None,
        check_frequency_hours: int = 24,
    ) -> Dict[str, Any]:
        """Create a new warning flag."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        flag_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO threat_flag
                (id, threat_id, flag_name, description, indicator_type,
                 threshold_critical, threshold_warning, threshold_normal,
                 comparison_operator, unit, data_source, check_frequency_hours)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                flag_id, threat_id, flag_name, description, indicator_type,
                threshold_critical, threshold_warning, threshold_normal,
                comparison_operator, unit, data_source, check_frequency_hours,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Created flag %s for threat %s: %s", flag_id, threat_id, flag_name)
        return result

    def update_flag_value(
        self,
        flag_id: str,
        value: str,
    ) -> Dict[str, Any]:
        """Update flag with new observation and evaluate status."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get current flag
        cur.execute("SELECT * FROM threat_flag WHERE id = %s", (flag_id,))
        flag = dict(cur.fetchone())
        if not flag:
            cur.close()
            return {"error": "Flag not found"}

        # Determine new status
        new_status = self._evaluate_status(flag, value)

        cur.execute(
            """
            UPDATE threat_flag
            SET current_value = %s,
                previous_value = current_value,
                status = %s,
                last_value_at = NOW(),
                last_checked_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (value, new_status, flag_id),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Updated flag %s: value=%s, status=%s", flag_id, value, new_status)
        return result

    def _evaluate_status(self, flag: Dict[str, Any], value: str) -> str:
        """Evaluate flag status based on thresholds."""
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            return "unknown"

        threshold_critical = flag.get("threshold_critical")
        threshold_warning = flag.get("threshold_warning")
        threshold_normal = flag.get("threshold_normal")
        operator = flag.get("comparison_operator", "gte")

        if threshold_critical is not None:
            if self._check_threshold(numeric_value, threshold_critical, operator):
                return "critical"

        if threshold_warning is not None:
            if self._check_threshold(numeric_value, threshold_warning, operator):
                return "warning"

        if threshold_normal is not None:
            if self._check_threshold(numeric_value, threshold_normal, operator):
                return "elevated"

        return "normal"

    def _check_threshold(self, value: float, threshold: float, operator: str) -> bool:
        """Check if value exceeds threshold based on operator."""
        ops = {
            "gt": value > threshold,
            "gte": value >= threshold,
            "lt": value < threshold,
            "lte": value <= threshold,
            "eq": abs(value - threshold) < 0.0001,
            "neq": abs(value - threshold) >= 0.0001,
        }
        return ops.get(operator, value >= threshold)

    def evaluate_flag(self, flag_id: str) -> Dict[str, Any]:
        """Re-evaluate a flag against its current value."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM threat_flag WHERE id = %s", (flag_id,))
        flag = dict(cur.fetchone())
        if not flag:
            cur.close()
            return {"error": "Flag not found"}

        if flag.get("current_value"):
            new_status = self._evaluate_status(flag, flag["current_value"])

            cur.execute(
                """
                UPDATE threat_flag
                SET status = %s, last_checked_at = NOW(), updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (new_status, flag_id),
            )
            result = dict(cur.fetchone())
            conn.commit()
            cur.close()
            return result

        cur.close()
        return dict(flag)

    def evaluate_all_flags(self, location_id: str) -> List[Dict[str, Any]]:
        """Evaluate all flags for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT f.*
            FROM threat_flag f
            JOIN threat t ON t.id = f.threat_id
            WHERE t.location_id = %s AND f.is_active = TRUE
            """,
            (location_id,),
        )
        flags = [dict(r) for r in cur.fetchall()]
        cur.close()

        results = []
        for flag in flags:
            if flag.get("current_value"):
                new_status = self._evaluate_status(flag, flag["current_value"])
                if new_status != flag["status"]:
                    self.update_flag_value(flag["id"], flag["current_value"])
                    flag["status"] = new_status
            results.append(flag)

        return results

    def get_flags(
        self,
        location_id: Optional[str] = None,
        threat_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get flags with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["f.is_active = TRUE"]
        params: list = []

        if threat_id:
            conditions.append("f.threat_id = %s")
            params.append(threat_id)
        if location_id:
            conditions.append("t.location_id = %s")
            params.append(location_id)
        if status:
            conditions.append("f.status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions)

        cur.execute(
            f"""
            SELECT f.*, t.threat_name, t.threat_type
            FROM threat_flag f
            JOIN threat t ON t.id = f.threat_id
            WHERE {where_clause}
            ORDER BY f.status DESC, f.flag_name
            """,
            params,
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def get_flag_status_summary(self, location_id: str) -> Dict[str, Any]:
        """Get summary of flag statuses for dashboard."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT
                f.status,
                COUNT(*) AS count
            FROM threat_flag f
            JOIN threat t ON t.id = f.threat_id
            WHERE t.location_id = %s AND f.is_active = TRUE
            GROUP BY f.status
            """,
            (location_id,),
        )
        status_counts = {r["status"]: r["count"] for r in cur.fetchall()}

        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM threat_flag f
            JOIN threat t ON t.id = f.threat_id
            WHERE t.location_id = %s AND f.is_active = TRUE
            """,
            (location_id,),
        )
        total = cur.fetchone()["total"]

        cur.close()

        critical = status_counts.get("critical", 0)
        warning = status_counts.get("warning", 0)
        elevated = status_counts.get("elevated", 0)
        normal = status_counts.get("normal", 0)

        risk_score = ((critical * 1.0) + (warning * 0.6) + (elevated * 0.3) + (normal * 0.0)) / total if total > 0 else 0

        return {
            "location_id": location_id,
            "total_flags": total,
            "critical": critical,
            "warning": warning,
            "elevated": elevated,
            "normal": normal,
            "unknown": status_counts.get("unknown", 0),
            "risk_score": round(risk_score, 4),
            "status": "critical" if critical > 0 else ("warning" if warning > 0 else ("elevated" if elevated > 0 else "normal")),
        }

    def delete_flag(self, flag_id: str) -> bool:
        """Soft-delete a flag."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE threat_flag SET is_active = FALSE, updated_at = NOW() WHERE id = %s", (flag_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted
