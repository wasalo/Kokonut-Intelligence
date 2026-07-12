"""Double-Loop Learning Controller — questions underlying structure.

Extends the single-loop feedback controller to question structural
assumptions and challenge mental models, not just adjust parameters.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class DoubleLoopController:
    """Enables structural questioning and assumption challenging."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def evaluate_structural_questions(
        self, location_id: str
    ) -> List[Dict[str, Any]]:
        """Evaluate and generate structural questions for a location.

        Triggers structural review when single-loop adjustments are
        not producing lasting improvements.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        questions = []

        # Check if thresholds have been adjusted too frequently
        cur.execute("""
            SELECT COUNT(*) as cnt FROM feedback_loop
            WHERE target_entity = 'adaptive_threshold'
            AND status = 'applied'
            AND created_at > NOW() - INTERVAL '30 days'
        """)
        threshold_adjustments = cur.fetchone()["cnt"]

        if threshold_adjustments >= 5:
            questions.append(self._create_question(
                cur, location_id,
                "Frequent threshold adjustments suggest the underlying metrics or alert rules may need structural review.",
                "high",
                "threshold_adjustment_frequency",
            ))

        # Check if CRISP scores are consistently declining despite interventions
        cur.execute("""
            SELECT composite_score, assessed_at
            FROM crisp_risk_assessment
            WHERE location_id = %s
            ORDER BY assessed_at DESC LIMIT 5
        """, (location_id,))
        scores = [dict(r) for r in cur.fetchall()]

        if len(scores) >= 3:
            recent = scores[0]["composite_score"]
            older = scores[-1]["composite_score"]
            if recent and older and recent < older * 0.95:
                questions.append(self._create_question(
                    cur, location_id,
                    "CRISP scores declining despite interventions — are we measuring the right things?",
                    "high",
                    "crisp_declining_trend",
                ))

        # Check if actions are consistently ineffective
        cur.execute("""
            SELECT COUNT(*) as cnt FROM action_outcome
            WHERE outcome_type IN ('ineffective', 'counterproductive')
            AND location_id = %s
            AND created_at > NOW() - INTERVAL '90 days'
        """, (location_id,))
        ineffective = cur.fetchone()["cnt"]

        if ineffective >= 3:
            questions.append(self._create_question(
                cur, location_id,
                "Multiple ineffective actions suggest fundamental assumptions may need revisiting.",
                "critical",
                "ineffective_action_cluster",
            ))

        # Check if data sources are providing useful signal
        cur.execute("""
            SELECT COUNT(*) as cnt FROM sensor_alert
            WHERE location_id = %s
            AND created_at > NOW() - INTERVAL '30 days'
            AND acknowledged = FALSE
        """, (location_id,))
        unacked_alerts = cur.fetchone()["cnt"]

        if unacked_alerts >= 10:
            questions.append(self._create_question(
                cur, location_id,
                f"{unacked_alerts} unacknowledged alerts — is the alert system providing value or creating noise?",
                "medium",
                "alert_noise_level",
            ))

        conn.commit()
        cur.close()
        return questions

    def challenge_assumption(
        self,
        assumption_id: str,
        challenge_text: str,
        evidence_type: str = "metric_trend",
        evidence_data: Optional[Dict] = None,
        challenged_by: str = "system",
    ) -> str:
        """Challenge a structural assumption.

        Returns the challenge record ID.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        challenge_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO assumption_challenge (
                id, assumption_id, challenge_text, evidence_type,
                evidence_data, confidence, challenged_by, challenged_at
            ) VALUES (%s, %s, %s, %s, %s, 0.5, %s, %s)
        """, (
            challenge_id, assumption_id, challenge_text,
            evidence_type, psycopg2.extras.Json(evidence_data or {}),
            challenged_by, now,
        ))

        # Update assumption status
        cur.execute("""
            UPDATE structural_assumption
            SET status = 'challenged',
                challenge_evidence = %s,
                challenged_at = %s,
                challenged_by = %s,
                updated_at = %s
            WHERE id = %s AND status = 'active'
        """, (challenge_text, now, challenged_by, now, assumption_id))

        conn.commit()
        cur.close()
        return challenge_id

    def get_structural_health(
        self, location_id: str
    ) -> Dict[str, Any]:
        """Assess the structural health of the system.

        Returns metrics on how well assumptions are being questioned
        and how many structural questions are open.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE status = 'active') as active,
                   COUNT(*) FILTER (WHERE status = 'challenged') as challenged,
                   COUNT(*) FILTER (WHERE status = 'validated') as validated,
                   COUNT(*) FILTER (WHERE status = 'deprecated') as deprecated
            FROM structural_assumption
            WHERE location_id = %s
        """, (location_id,))
        assumption_stats = dict(cur.fetchone())

        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE status = 'open') as open_q,
                   COUNT(*) FILTER (WHERE status = 'investigating') as investigating,
                   COUNT(*) FILTER (WHERE status = 'answered') as answered
            FROM structural_question
            WHERE location_id = %s
        """, (location_id,))
        question_stats = dict(cur.fetchone())

        cur.execute("""
            SELECT COUNT(*) as cnt FROM paradigm_shift
            WHERE location_id = %s AND status = 'confirmed'
        """, (location_id,))
        paradigm_shifts = cur.fetchone()["cnt"]

        cur.close()

        total_assumptions = assumption_stats["total"] or 0
        challenged = assumption_stats["challenged"] or 0
        open_questions = question_stats["open_q"] or 0

        health_score = 0.0
        if total_assumptions > 0:
            health_score += (challenged / total_assumptions) * 0.5
        if open_questions > 0:
            health_score += 0.2  # Having open questions is healthy
        if paradigm_shifts > 0:
            health_score += 0.3

        return {
            "assumption_stats": assumption_stats,
            "question_stats": question_stats,
            "paradigm_shifts": paradigm_shifts,
            "health_score": round(min(health_score, 1.0), 3),
            "recommendation": self._health_recommendation(
                total_assumptions, challenged, open_questions
            ),
        }

    def list_assumptions(
        self, location_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List structural assumptions."""
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
            SELECT * FROM structural_assumption {where_clause}
            ORDER BY created_at DESC
        """, params)

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def list_challenges(
        self, assumption_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List assumption challenges."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if assumption_id:
            cur.execute("""
                SELECT * FROM assumption_challenge
                WHERE assumption_id = %s ORDER BY challenged_at DESC
            """, (assumption_id,))
        else:
            cur.execute("""
                SELECT * FROM assumption_challenge
                ORDER BY challenged_at DESC LIMIT 50
            """)

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    # --- Private helpers ---

    def _create_question(
        self,
        cur,
        location_id: str,
        question_text: str,
        priority: str,
        trigger_reason: str,
    ) -> Dict[str, Any]:
        """Create a structural question."""
        question_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO structural_question (
                id, question_text, location_id, domain,
                trigger_reason, priority, status, created_at, updated_at
            ) VALUES (%s, %s, %s, 'farm', %s, %s, 'open', %s, %s)
            RETURNING *
        """, (question_id, question_text, location_id, trigger_reason, priority, now, now))

        row = dict(cur.fetchone())
        return row

    def _health_recommendation(
        self,
        total_assumptions: int,
        challenged: int,
        open_questions: int,
    ) -> str:
        """Generate a recommendation based on structural health."""
        if total_assumptions == 0:
            return "No structural assumptions documented. Start by capturing key assumptions about the farm system."
        if challenged == 0:
            return "No assumptions have been challenged. Actively question whether current approaches are working."
        if open_questions > 5:
            return "Many open structural questions. Prioritize answering the most critical ones."
        return "Structural health is reasonable. Continue questioning assumptions and testing hypotheses."
