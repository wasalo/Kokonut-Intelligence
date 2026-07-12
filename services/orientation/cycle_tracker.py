"""OODA Cycle Tracker — measures timing and correlation across Observe→Orient→Decide→Act.

Tracks full OODA cycle performance with correlation IDs, phase timing,
and outcome tracking per decision type.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras


class OODACycleTracker:
    """Tracks OODA cycle timing and performance."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def start_cycle(
        self,
        correlation_id: Optional[str] = None,
        location_id: str = "",
        cycle_type: str = "automated",
        decision_type: str = "unknown",
        trigger_event_type: Optional[str] = None,
        trigger_event_id: Optional[str] = None,
    ) -> str:
        """Start a new OODA cycle. Returns correlation_id."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO ooda_cycle_log (
                id, correlation_id, location_id, cycle_type,
                decision_type, trigger_event_type, trigger_event_id,
                observe_started_at, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'in_progress', %s, %s)
        """, (
            str(uuid.uuid4()), correlation_id, location_id, cycle_type,
            decision_type, trigger_event_type, trigger_event_id,
            now, now, now,
        ))

        conn.commit()
        cur.close()
        return correlation_id

    def complete_phase(
        self,
        correlation_id: str,
        phase: str,
        duration_ms: Optional[int] = None,
        framework_used: Optional[str] = None,
        assessment_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        action_type: Optional[str] = None,
        action_outcome_id: Optional[str] = None,
    ) -> None:
        """Mark a phase as completed and update timing.

        Args:
            correlation_id: The cycle's correlation ID.
            phase: One of 'observe', 'orient', 'decide', 'act'.
            duration_ms: Duration of this phase in milliseconds.
            framework_used: For orient phase, which framework was used.
            assessment_id: For orient phase, the assessment ID.
            policy_id: For decide phase, the policy ID.
            decision_id: For decide phase, the decision log ID.
            action_type: For act phase, the action type.
            action_outcome_id: For act phase, the outcome ID.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)
        phase_started_col = f"{phase}_started_at"
        phase_completed_col = f"{phase}_completed_at"
        phase_duration_col = f"{phase}_duration_ms"

        # Build dynamic update
        updates = [f"{phase_completed_col} = %s"]
        params = [now]

        if duration_ms is not None:
            updates.append(f"{phase_duration_col} = %s")
            params.append(duration_ms)

        # Phase-specific fields
        if phase == "orient":
            if framework_used:
                # Append to JSONB array
                cur.execute("""
                    UPDATE ooda_cycle_log
                    SET orient_frameworks_used = orient_frameworks_used || %s::jsonb
                    WHERE correlation_id = %s
                """, (psycopg2.extras.Json([framework_used]), correlation_id))
            if assessment_id:
                updates.append("orient_assessment_id = %s")
                params.append(assessment_id)

        elif phase == "decide":
            if policy_id:
                updates.append("decide_policy_id = %s")
                params.append(policy_id)
            if decision_id:
                updates.append("decide_decision_id = %s")
                params.append(decision_id)

        elif phase == "act":
            if action_type:
                updates.append("act_action_type = %s")
                params.append(action_type)
            if action_outcome_id:
                updates.append("act_outcome_id = %s")
                params.append(action_outcome_id)

        updates.append("updated_at = %s")
        params.append(now)

        # Calculate total cycle time if act is completed
        if phase == "act":
            updates.append("""
                total_cycle_time_ms = EXTRACT(EPOCH FROM (%s - observe_started_at)) * 1000
            """.strip())
            params.append(now)

        params.append(correlation_id)
        sql = f"""
            UPDATE ooda_cycle_log
            SET {', '.join(updates)}
            WHERE correlation_id = %s
        """
        cur.execute(sql, params)
        conn.commit()
        cur.close()

    def complete_cycle(
        self,
        correlation_id: str,
        status: str = "completed",
        outcome_type: Optional[str] = None,
        error_message: Optional[str] = None,
        failure_phase: Optional[str] = None,
    ) -> None:
        """Mark the entire cycle as completed or failed."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)

        cur.execute("""
            UPDATE ooda_cycle_log
            SET
                status = %s,
                outcome_type = %s,
                error_message = %s,
                failure_phase = %s,
                updated_at = %s
            WHERE correlation_id = %s
        """, (status, outcome_type, error_message, failure_phase, now, correlation_id))

        conn.commit()
        cur.close()

    def get_cycle(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Get a cycle by correlation ID."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM ooda_cycle_log
            WHERE correlation_id = %s
        """, (correlation_id,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return dict(row)

    def get_stats(
        self,
        location_id: Optional[str] = None,
        decision_type: Optional[str] = None,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get cycle performance statistics."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["status = 'completed'"]
        params = []

        if location_id:
            conditions.append("location_id = %s")
            params.append(location_id)
        if decision_type:
            conditions.append("decision_type = %s")
            params.append(decision_type)
        if since:
            conditions.append("created_at >= %s")
            params.append(since)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT
                COUNT(*) as total_cycles,
                AVG(total_cycle_time_ms) as avg_cycle_time_ms,
                MIN(total_cycle_time_ms) as min_cycle_time_ms,
                MAX(total_cycle_time_ms) as max_cycle_time_ms,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_cycle_time_ms) as median_cycle_time_ms,
                AVG(observe_duration_ms) as avg_observe_ms,
                AVG(orient_duration_ms) as avg_orient_ms,
                AVG(decide_duration_ms) as avg_decide_ms,
                AVG(act_duration_ms) as avg_act_ms,
                COUNT(*) FILTER (WHERE outcome_type = 'effective') as effective_count,
                COUNT(*) FILTER (WHERE outcome_type = 'ineffective') as ineffective_count,
                COUNT(*) FILTER (WHERE outcome_type = 'unknown') as unknown_outcome_count
            FROM ooda_cycle_log
            WHERE {where_clause}
        """, params)

        row = cur.fetchone()
        cur.close()

        if row is None:
            return {"total_cycles": 0}

        row = dict(row)
        total = row.get("total_cycles", 0) or 0
        effective = row.get("effective_count", 0) or 0

        return {
            "total_cycles": total,
            "avg_cycle_time_ms": float(row.get("avg_cycle_time_ms") or 0),
            "min_cycle_time_ms": float(row.get("min_cycle_time_ms") or 0),
            "max_cycle_time_ms": float(row.get("max_cycle_time_ms") or 0),
            "median_cycle_time_ms": float(row.get("median_cycle_time_ms") or 0),
            "avg_observe_ms": float(row.get("avg_observe_ms") or 0),
            "avg_orient_ms": float(row.get("avg_orient_ms") or 0),
            "avg_decide_ms": float(row.get("avg_decide_ms") or 0),
            "avg_act_ms": float(row.get("avg_act_ms") or 0),
            "effective_rate": effective / total if total > 0 else 0.0,
            "ineffective_count": row.get("ineffective_count", 0),
            "unknown_outcome_count": row.get("unknown_outcome_count", 0),
        }

    def list_recent(
        self,
        location_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list:
        """List recent OODA cycles."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = []
        params = []

        if location_id:
            conditions.append("location_id = %s")
            params.append(location_id)
        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT
                id, correlation_id, location_id, cycle_type,
                decision_type, status, total_cycle_time_ms,
                outcome_type, observe_started_at, act_completed_at,
                created_at
            FROM ooda_cycle_log
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """, params + [limit])

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
