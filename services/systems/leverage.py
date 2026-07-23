"""Leverage Point Analyzer — maps Meadows' 12 leverage points to farm context.

Identifies the highest-leverage intervention points for a farm location
by analyzing current state across all 12 levels.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import LEVERAGE_POINTS


class LeverageAnalyzer:
    """Analyzes leverage points for farm intervention prioritization."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def assess(
        self, location_id: str, assessed_by: str = "system"
    ) -> List[Dict[str, Any]]:
        """Assess all 12 leverage points for a location.

        Returns a ranked list of leverage points with impact scores.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        assessments = []

        for point in LEVERAGE_POINTS:
            assessment = self._assess_point(cur, location_id, point)
            assessments.append(assessment)

            # Persist assessment
            cur.execute("""
                INSERT INTO leverage_assessment (
                    id, location_id, leverage_point, point_name,
                    current_state, impact_score, intervention_suggestion,
                    data_sources, assessed_at, assessed_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), location_id, point["point"],
                point["name"], assessment["current_state"],
                assessment["impact_score"],
                assessment["intervention_suggestion"],
                psycopg2.extras.Json(assessment["data_sources"]),
                datetime.now(timezone.utc), assessed_by,
            ))

        conn.commit()
        cur.close()

        assessments.sort(key=lambda x: x["impact_score"], reverse=True)
        return assessments

    def rank_by_impact(
        self, location_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Rank leverage points by impact score for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM leverage_assessment
            WHERE location_id = %s
            ORDER BY impact_score DESC
            LIMIT %s
        """, (location_id, limit))

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def get_point_details(
        self, location_id: str, leverage_point: int
    ) -> Optional[Dict[str, Any]]:
        """Get detailed assessment for a specific leverage point."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM leverage_assessment
            WHERE location_id = %s AND leverage_point = %s
            ORDER BY assessed_at DESC LIMIT 1
        """, (location_id, leverage_point))

        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return dict(row)

    def _assess_point(
        self,
        cur,
        location_id: str,
        point: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assess a single leverage point."""
        point_num = point["point"]

        if point_num == 12:
            return self._assess_parameters(cur, location_id, point)
        elif point_num == 11:
            return self._assess_buffers(cur, location_id, point)
        elif point_num == 10:
            return self._assess_stock_flow_structure(cur, location_id, point)
        elif point_num == 9:
            return self._assess_delays(cur, location_id, point)
        elif point_num == 8:
            return self._assess_negative_feedback(cur, location_id, point)
        elif point_num == 7:
            return self._assess_positive_feedback(cur, location_id, point)
        elif point_num == 6:
            return self._assess_information_flows(cur, location_id, point)
        elif point_num == 5:
            return self._assess_rules(cur, location_id, point)
        elif point_num == 4:
            return self._assess_self_organization(cur, location_id, point)
        elif point_num == 3:
            return self._assess_goals(cur, location_id, point)
        elif point_num == 2:
            return self._assess_paradigm(cur, location_id, point)
        elif point_num == 1:
            return self._assess_transcendence(cur, location_id, point)
        else:
            return {
                "leverage_point": point_num,
                "point_name": point["name"],
                "impact_score": 0.0,
                "current_state": "Unknown",
                "intervention_suggestion": "No assessment available",
                "data_sources": [],
            }

    def _assess_parameters(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 12: Constants, Parameters, Numbers."""
        # Check how many alert rules and thresholds exist
        cur.execute("""
            SELECT COUNT(*) as cnt FROM alert_rule
            WHERE status = 'active'
        """)
        alert_count = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM adaptive_threshold
            WHERE is_enabled = TRUE AND location_id = %s
        """, (location_id,))
        threshold_count = cur.fetchone()["cnt"]

        # Parameters are the weakest leverage point — always high but low impact
        impact = 0.2  # Low impact by definition (Meadows' ranking)
        state = f"{alert_count} active alerts, {threshold_count} adaptive thresholds"

        return {
            "leverage_point": 12,
            "point_name": point["name"],
            "impact_score": impact,
            "current_state": state,
            "intervention_suggestion": "Parameters are the easiest but least effective leverage point. Consider higher-level interventions.",
            "data_sources": ["alert_rule", "adaptive_threshold"],
        }

    def _assess_buffers(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 11: Buffers and Stabilizing Stocks."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM soil_carbon_measurement
            WHERE location_id = %s
        """, (location_id,))
        soil_measurements = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM water_observation
            WHERE location_id = %s
        """, (location_id,))
        water_measurements = cur.fetchone()["cnt"]

        buffer_health = min((soil_measurements + water_measurements) / 20.0, 1.0)
        impact = 0.3 + (0.2 * buffer_health)
        state = f"Soil: {soil_measurements} measurements, Water: {water_measurements} observations"

        return {
            "leverage_point": 11,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Strengthen soil carbon and water reserves as buffers against shocks.",
            "data_sources": ["soil_carbon_measurement", "water_observation"],
        }

    def _assess_stock_flow_structure(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 10: Structure of Material Stocks and Flows."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM capital_flow_observation
            WHERE location_id = %s
        """, (location_id,))
        flow_count = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(DISTINCT from_capital || to_capital) as cnt
            FROM capital_flow_observation
            WHERE location_id = %s
        """, (location_id,))
        diversity = cur.fetchone()["cnt"]

        impact = 0.4 + (0.2 * min(diversity / 10.0, 1.0))
        state = f"{flow_count} capital flows, {diversity} distinct pathways"

        return {
            "leverage_point": 10,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Diversify capital flow pathways for greater systemic resilience.",
            "data_sources": ["capital_flow_observation"],
        }

    def _assess_delays(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 9: Lengths of Delays."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM practice_event
            WHERE location_id = %s
        """, (location_id,))
        practice_count = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM harvest_event
            WHERE location_id = %s
        """, (location_id,))
        harvest_count = cur.fetchone()["cnt"]

        delay_awareness = 0.5 if practice_count > 0 and harvest_count > 0 else 0.3
        impact = 0.4 + (0.3 * delay_awareness)
        state = f"{practice_count} practices recorded, {harvest_count} harvests tracked"

        return {
            "leverage_point": 9,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Account for time delays between interventions and effects in planning.",
            "data_sources": ["practice_event", "harvest_event"],
        }

    def _assess_negative_feedback(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 8: Strength of Negative Feedback Loops."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM sensor_alert
            WHERE acknowledged = FALSE
        """)
        unacked = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM stream_alert
            WHERE acknowledged = FALSE
        """)
        stream_unacked = cur.fetchone()["cnt"]

        feedback_strength = max(0.3, 1.0 - (unacked + stream_unacked) * 0.05)
        impact = 0.5 + (0.2 * feedback_strength)
        state = f"{unacked} sensor + {stream_unacked} stream alerts unacknowledged"

        return {
            "leverage_point": 8,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Strengthen anomaly detection sensitivity and response speed.",
            "data_sources": ["sensor_alert", "stream_alert"],
        }

    def _assess_positive_feedback(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 7: Positive Feedback Loops."""
        # Check for reinforcing patterns (e.g., declining soil carbon over time)
        cur.execute("""
            SELECT COUNT(*) as cnt FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_definition_id
            WHERE mv.location_id = %s AND md.metric_key = 'soil_carbon_delta'
            AND mv.verified = TRUE
        """, (location_id,))
        carbon_data_points = cur.fetchone()["cnt"]

        reinforcing_risk = 0.5 if carbon_data_points < 3 else 0.3
        impact = 0.5 + (0.3 * reinforcing_risk)
        state = f"{carbon_data_points} soil carbon data points"

        return {
            "leverage_point": 7,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Monitor for reinforcing degradation loops and intervene early.",
            "data_sources": ["metric_value"],
        }

    def _assess_information_flows(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 6: Information Flows."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM data_stream_post
            WHERE location_id = %s AND status = 'published'
        """, (location_id,))
        published_posts = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM attestation_record
            WHERE subject_id = %s AND subject_type = 'location'
        """, (location_id,))
        attestations = cur.fetchone()["cnt"]

        info_flow = min((published_posts + attestations) / 20.0, 1.0)
        impact = 0.6 + (0.2 * info_flow)
        state = f"{published_posts} published posts, {attestations} attestations"

        return {
            "leverage_point": 6,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Improve information transparency and data access for all stakeholders.",
            "data_sources": ["data_stream_post", "attestation_record"],
        }

    def _assess_rules(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 5: Rules of the System."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM decision_policy
            WHERE is_enabled = TRUE
        """)
        policies = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM governance_inclusion_observation
            WHERE location_id = %s
        """, (location_id,))
        governance = cur.fetchone()["cnt"]

        rule_strength = min((policies + governance) / 10.0, 1.0)
        impact = 0.6 + (0.2 * rule_strength)
        state = f"{policies} decision policies, {governance} governance observations"

        return {
            "leverage_point": 5,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Review and strengthen governance rules and incentive structures.",
            "data_sources": ["decision_policy", "governance_inclusion_observation"],
        }

    def _assess_self_organization(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 4: Self-Organization."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM sampling_config
            WHERE is_enabled = TRUE AND location_id = %s
        """, (location_id,))
        adaptive_configs = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM feedback_loop
            WHERE status = 'applied'
        """)
        feedback_loops = cur.fetchone()["cnt"]

        self_org = min((adaptive_configs + feedback_loops) / 10.0, 1.0)
        impact = 0.7 + (0.2 * self_org)
        state = f"{adaptive_configs} adaptive configs, {feedback_loops} feedback loops applied"

        return {
            "leverage_point": 4,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Enable more self-organizing capabilities through adaptive rules.",
            "data_sources": ["sampling_config", "feedback_loop"],
        }

    def _assess_goals(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 3: Goals of the System."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM metric_definition
            WHERE active = TRUE
        """)
        metrics = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM crisp_risk_assessment
            WHERE location_id = %s
        """, (location_id,))
        assessments = cur.fetchone()["cnt"]

        goal_clarity = min(assessments / 5.0, 1.0)
        impact = 0.7 + (0.2 * goal_clarity)
        state = f"{metrics} tracked metrics, {assessments} CRISP assessments"

        return {
            "leverage_point": 3,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Clarify and align system goals across all stakeholders.",
            "data_sources": ["metric_definition", "crisp_risk_assessment"],
        }

    def _assess_paradigm(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 2: Paradigm or Mindset."""
        cur.execute("""
            SELECT COUNT(*) as cnt FROM mental_model
            WHERE stakeholder_id IN (
                SELECT id FROM farm_registry_record WHERE location_id = %s
            )
        """, (location_id,))
        mental_models = cur.fetchone()["cnt"]

        paradigm_depth = min(mental_models / 5.0, 1.0)
        impact = 0.8 + (0.15 * paradigm_depth)
        state = f"{mental_models} captured mental models"

        return {
            "leverage_point": 2,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Surface and examine underlying assumptions about how the farm system works.",
            "data_sources": ["mental_model"],
        }

    def _assess_transcendence(self, cur, location_id: str, point: Dict) -> Dict:
        """Level 1: Power to Transcend Paradigms."""
        cur.execute("""
            SELECT COUNT(DISTINCT assessment_type) as cnt
            FROM situation_assessment
            WHERE location_id = %s
        """, (location_id,))
        assessment_types = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM structural_assumption
            WHERE location_id = %s AND status = 'challenged'
        """, (location_id,))
        challenged = cur.fetchone()["cnt"]

        transcendence = min(challenged / 3.0, 1.0)
        impact = 0.85 + (0.1 * transcendence)
        state = f"{assessment_types} assessment types, {challenged} assumptions challenged"

        return {
            "leverage_point": 1,
            "point_name": point["name"],
            "impact_score": round(impact, 3),
            "current_state": state,
            "intervention_suggestion": "Hold all paradigms lightly — use multiple analytical frameworks and question assumptions.",
            "data_sources": ["situation_assessment", "structural_assumption"],
        }
