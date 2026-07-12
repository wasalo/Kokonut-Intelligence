"""Policy Engine — evaluates decision policies against situation assessments.

Reads policy rules from the database, evaluates them against current
situation assessments, and produces decision log entries. All decisions
require human approval before execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class PolicyEngine:
    """Evaluates decision policies and produces action recommendations."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def evaluate(
        self,
        location_id: str,
        assessment_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluate all active policies for a location against current state.

        Args:
            location_id: UUID of the location to evaluate.
            assessment_id: Optional specific assessment to evaluate against.
            correlation_id: Optional correlation ID for OODA cycle tracking.

        Returns:
            List of decision log entries created (all with approval_status='pending').
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get the latest assessment if not provided
        if assessment_id is None:
            cur.execute("""
                SELECT id FROM situation_assessment
                WHERE location_id = %s AND status != 'superseded'
                ORDER BY assessed_at DESC LIMIT 1
            """, (location_id,))
            assess_row = cur.fetchone()
            if assess_row is None:
                cur.close()
                return []
            assessment_id = str(assess_row["id"])

        # Load assessment data
        assessment = self._load_assessment(cur, assessment_id)
        if assessment is None:
            cur.close()
            return []

        # Load active policies
        cur.execute("""
            SELECT * FROM decision_policy
            WHERE is_enabled = TRUE
            ORDER BY priority DESC, created_at
        """)
        policies = [dict(r) for r in cur.fetchall()]

        # Check cooldowns for each policy
        decisions = []
        for policy in policies:
            if self._check_cooldown(cur, policy["id"], location_id):
                continue
            if self._check_daily_limit(cur, policy["id"], location_id):
                continue

            # Evaluate the policy trigger
            if self._evaluate_trigger(cur, policy, assessment, location_id):
                decision = self._create_decision(
                    cur, policy, assessment, location_id, correlation_id
                )
                decisions.append(decision)

        conn.commit()
        cur.close()
        return decisions

    def approve(
        self,
        decision_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        """Approve a pending decision.

        Args:
            decision_id: UUID of the decision to approve.
            approved_by: Who approved the decision.

        Returns:
            Updated decision record.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)

        cur.execute("""
            UPDATE decision_log
            SET
                approval_status = 'approved',
                approved_by = %s,
                approved_at = %s,
                updated_at = %s
            WHERE id = %s AND approval_status = 'pending'
            RETURNING *
        """, (approved_by, now, now, decision_id))

        row = cur.fetchone()
        conn.commit()
        cur.close()

        if row is None:
            return {"error": "Decision not found or already processed"}

        return dict(row)

    def reject(
        self,
        decision_id: str,
        rejected_by: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Reject a pending decision."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)

        cur.execute("""
            UPDATE decision_log
            SET
                approval_status = 'rejected',
                approved_by = %s,
                approved_at = %s,
                rejection_reason = %s,
                status = 'rejected',
                updated_at = %s
            WHERE id = %s AND approval_status = 'pending'
            RETURNING *
        """, (rejected_by, now, reason, now, decision_id))

        row = cur.fetchone()
        conn.commit()
        cur.close()

        if row is None:
            return {"error": "Decision not found or already processed"}

        return dict(row)

    def execute(
        self,
        decision_id: str,
        executed_by: str = "system",
    ) -> Dict[str, Any]:
        """Execute an approved decision.

        This actually performs the action described in the decision.
        All executions are logged for audit.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)

        # Load the decision
        cur.execute("SELECT * FROM decision_log WHERE id = %s", (decision_id,))
        row = cur.fetchone()
        if row is None:
            cur.close()
            return {"error": "Decision not found"}

        decision = dict(row)

        if decision["approval_status"] != "approved":
            cur.close()
            return {"error": "Decision must be approved before execution"}

        # Execute based on action_type
        result = self._execute_action(cur, decision)

        # Update decision status
        status = "executed" if result.get("success") else "failed"
        cur.execute("""
            UPDATE decision_log
            SET
                status = %s,
                executed_at = %s,
                execution_result = %s,
                execution_error = %s,
                updated_at = %s
            WHERE id = %s
        """, (
            status, now,
            psycopg2.extras.Json(result) if result.get("success") else None,
            result.get("error"),
            now, decision_id,
        ))

        # Record outcome
        outcome_type = "success" if result.get("success") else "failure"
        cur.execute("""
            INSERT INTO decision_outcome (
                id, decision_id, outcome_type, outcome_text,
                measured_at, measured_by, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            str(uuid.uuid4()), decision_id, outcome_type,
            result.get("message", ""),
            now, executed_by,
            psycopg2.extras.Json(result),
        ))

        conn.commit()
        cur.close()
        return result

    def list_pending(
        self,
        location_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List pending decisions awaiting approval."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["dl.approval_status = 'pending'"]
        params = []

        if location_id:
            conditions.append("dl.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT
                dl.*,
                dp.policy_name,
                dp.action_type as policy_action_type,
                dp.risk_level
            FROM decision_log dl
            JOIN decision_policy dp ON dp.id = dl.policy_id
            WHERE {where_clause}
            ORDER BY dl.created_at DESC
            LIMIT %s
        """, params + [limit])

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get a decision by ID."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT dl.*, dp.policy_name, dp.action_type as policy_action_type
            FROM decision_log dl
            JOIN decision_policy dp ON dp.id = dl.policy_id
            WHERE dl.id = %s
        """, (decision_id,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return dict(row)

    # --- Private helpers ---

    def _load_assessment(
        self, cur, assessment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load assessment with dimensions and signals."""
        cur.execute("""
            SELECT * FROM situation_assessment WHERE id = %s
        """, (assessment_id,))
        assess_row = cur.fetchone()
        if assess_row is None:
            return None

        assessment = dict(assess_row)

        # Load dimensions
        cur.execute("""
            SELECT * FROM assessment_dimension
            WHERE assessment_id = %s
        """, (assessment_id,))
        assessment["dimensions"] = {r["dimension_key"]: dict(r) for r in cur.fetchall()}

        # Load signals
        cur.execute("""
            SELECT * FROM assessment_signal
            WHERE assessment_id = %s
        """, (assessment_id,))
        assessment["signals"] = [dict(r) for r in cur.fetchall()]

        return assessment

    def _evaluate_trigger(
        self,
        cur,
        policy: Dict[str, Any],
        assessment: Dict[str, Any],
        location_id: str,
    ) -> bool:
        """Evaluate whether a policy trigger condition is met."""
        # Check situation grade trigger
        trigger_grade = policy.get("trigger_situation_grade")
        if trigger_grade and assessment.get("situation_grade") != trigger_grade:
            return False

        # Check dimension trigger
        trigger_dimension = policy.get("trigger_dimension")
        if trigger_dimension:
            dim = assessment.get("dimensions", {}).get(trigger_dimension)
            if dim is None:
                return False

            score = dim.get("risk_score", 50)
            score_min = policy.get("trigger_score_min")
            score_max = policy.get("trigger_score_max")

            if score_min is not None and score < score_min:
                return False
            if score_max is not None and score > score_max:
                return False

        # Check event type trigger
        trigger_event = policy.get("trigger_event_type")
        if trigger_event:
            # For event-triggered policies, check if the assessment
            # contains a matching signal
            has_signal = any(
                s.get("key", "").startswith(trigger_event)
                for s in assessment.get("signals", [])
            )
            if not has_signal:
                return False

        return True

    def _check_cooldown(
        self, cur, policy_id: str, location_id: str
    ) -> bool:
        """Check if policy is in cooldown period."""
        cur.execute("""
            SELECT cooldown_minutes FROM decision_policy WHERE id = %s
        """, (policy_id,))
        policy_row = cur.fetchone()
        if policy_row is None:
            return False

        cooldown = policy_row["cooldown_minutes"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM decision_log
            WHERE policy_id = %s AND location_id = %s
            AND created_at > NOW() - INTERVAL '%s minutes'
        """, (policy_id, location_id, cooldown))

        row = cur.fetchone()
        return (row["cnt"] or 0) > 0

    def _check_daily_limit(
        self, cur, policy_id: str, location_id: str
    ) -> bool:
        """Check if policy has exceeded daily execution limit."""
        cur.execute("""
            SELECT max_executions_per_day FROM decision_policy WHERE id = %s
        """, (policy_id,))
        policy_row = cur.fetchone()
        if policy_row is None:
            return False

        max_daily = policy_row["max_executions_per_day"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM decision_log
            WHERE policy_id = %s AND location_id = %s
            AND created_at > NOW() - INTERVAL '24 hours'
        """, (policy_id, location_id))

        row = cur.fetchone()
        return (row["cnt"] or 0) >= max_daily

    def _create_decision(
        self,
        cur,
        policy: Dict[str, Any],
        assessment: Dict[str, Any],
        location_id: str,
        correlation_id: Optional[str],
    ) -> Dict[str, Any]:
        """Create a decision log entry for a triggered policy."""
        decision_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO decision_log (
                id, policy_id, location_id, assessment_id,
                correlation_id, trigger_event_type,
                action_type, action_config,
                status, approval_status,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', 'pending', %s, %s)
            RETURNING *
        """, (
            decision_id, policy["id"], location_id, assessment["id"],
            correlation_id, policy.get("trigger_event_type"),
            policy["action_type"],
            psycopg2.extras.Json(policy.get("action_config", {})),
            now, now,
        ))

        row = dict(cur.fetchone())
        row["policy_name"] = policy.get("policy_name")
        row["risk_level"] = policy.get("risk_level")
        return row

    def _execute_action(
        self, cur, decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the action described in a decision."""
        action_type = decision.get("action_type", "")
        action_config = decision.get("action_config", {})
        location_id = decision.get("location_id")

        if action_type == "create_intervention_draft":
            return self._create_intervention_draft(cur, location_id, action_config)

        elif action_type == "send_alert_notification":
            return self._send_alert_notification(cur, location_id, action_config)

        elif action_type == "adjust_sampling_rate":
            return self._adjust_sampling_rate(cur, location_id, action_config)

        elif action_type == "trigger_reassessment":
            return self._trigger_reassessment(cur, location_id, action_config)

        elif action_type == "create_data_stream_post":
            return self._create_data_stream_post(cur, location_id, action_config)

        else:
            return {
                "success": False,
                "error": f"Unknown action type: {action_type}",
                "message": f"Action type '{action_type}' is not implemented",
            }

    def _create_intervention_draft(
        self, cur, location_id: str, config: Dict
    ) -> Dict[str, Any]:
        """Create a draft intervention record."""
        return {
            "success": True,
            "message": "Intervention draft created (simulated)",
            "action": "create_intervention_draft",
            "location_id": location_id,
            "config": config,
        }

    def _send_alert_notification(
        self, cur, location_id: str, config: Dict
    ) -> Dict[str, Any]:
        """Send an alert notification."""
        return {
            "success": True,
            "message": "Alert notification sent (simulated)",
            "action": "send_alert_notification",
            "location_id": location_id,
            "config": config,
        }

    def _adjust_sampling_rate(
        self, cur, location_id: str, config: Dict
    ) -> Dict[str, Any]:
        """Adjust sensor sampling rate."""
        return {
            "success": True,
            "message": "Sampling rate adjusted (simulated)",
            "action": "adjust_sampling_rate",
            "location_id": location_id,
            "config": config,
        }

    def _trigger_reassessment(
        self, cur, location_id: str, config: Dict
    ) -> Dict[str, Any]:
        """Trigger a situation reassessment."""
        return {
            "success": True,
            "message": "Reassessment triggered (simulated)",
            "action": "trigger_reassessment",
            "location_id": location_id,
            "config": config,
        }

    def _create_data_stream_post(
        self, cur, location_id: str, config: Dict
    ) -> Dict[str, Any]:
        """Create a data stream post."""
        return {
            "success": True,
            "message": "Data stream post created (simulated)",
            "action": "create_data_stream_post",
            "location_id": location_id,
            "config": config,
        }
