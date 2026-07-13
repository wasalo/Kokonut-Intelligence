"""Threat Intelligence — aggregates all threatcasting data into intelligence
briefings, landscape assessments, and evolution predictions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class ThreatIntelligence:
    """Aggregates threatcasting data into actionable intelligence."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def get_threat_landscape(self, location_id: str) -> Dict[str, Any]:
        """Assess overall threat landscape for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Threat counts by type
        cur.execute(
            """
            SELECT threat_type, COUNT(*) AS count
            FROM threat
            WHERE location_id = %s AND is_active = TRUE
            GROUP BY threat_type
            """,
            (location_id,),
        )
        by_type = {r["threat_type"]: r["count"] for r in cur.fetchall()}

        # Threat counts by severity
        cur.execute(
            """
            SELECT severity_potential, COUNT(*) AS count
            FROM threat
            WHERE location_id = %s AND is_active = TRUE
            GROUP BY severity_potential
            """,
            (location_id,),
        )
        by_severity = {r["severity_potential"]: r["count"] for r in cur.fetchall()}

        # Total active threats
        cur.execute(
            "SELECT COUNT(*) AS total FROM threat WHERE location_id = %s AND is_active = TRUE",
            (location_id,),
        )
        threat_count = cur.fetchone()["total"]

        # Flag statuses
        cur.execute(
            """
            SELECT f.status, COUNT(*) AS count
            FROM threat_flag f
            JOIN threat t ON t.id = f.threat_id
            WHERE t.location_id = %s AND f.is_active = TRUE
            GROUP BY f.status
            """,
            (location_id,),
        )
        flag_statuses = {r["status"]: r["count"] for r in cur.fetchall()}
        total_flags = sum(flag_statuses.values())

        # Active cascades
        cur.execute(
            """
            SELECT COUNT(*) AS active
            FROM threat_cascade c
            JOIN threat t ON t.id = c.trigger_threat_id
            WHERE t.location_id = %s AND c.is_enabled = TRUE
            """,
            (location_id,),
        )
        cascade_count = cur.fetchone()["active"]

        # Horizons
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM threat_horizon WHERE location_id = %s AND is_active = TRUE",
            (location_id,),
        )
        horizon_count = cur.fetchone()["cnt"]

        # Narratives
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM threat_narrative n
            JOIN threat t ON t.id = n.threat_id
            WHERE t.location_id = %s
            """,
            (location_id,),
        )
        narrative_count = cur.fetchone()["cnt"]

        # Cross-impacts
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM threat_cross_impact ci
            JOIN threat t ON t.id = ci.source_threat_id
            WHERE t.location_id = %s AND ci.is_enabled = TRUE
            """,
            (location_id,),
        )
        cross_impact_count = cur.fetchone()["cnt"]

        cur.close()

        # Compute overall risk score
        severity_weights = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        flag_weights = {"normal": 0.0, "elevated": 0.3, "warning": 0.6, "critical": 1.0}

        severity_score = sum(
            by_severity.get(s, 0) * w for s, w in severity_weights.items()
        ) / max(threat_count, 1)

        flag_score = sum(
            flag_statuses.get(s, 0) * w for s, w in flag_weights.items()
        ) / max(total_flags, 1)

        cascade_score = min(cascade_count / 5.0, 1.0)  # normalize to 0-1

        overall_risk = (severity_score * 0.4) + (flag_score * 0.35) + (cascade_score * 0.25)

        return {
            "location_id": location_id,
            "threat_count": threat_count,
            "threats_by_type": by_type,
            "threats_by_severity": by_severity,
            "active_flags": total_flags,
            "warning_flags": flag_statuses.get("warning", 0),
            "critical_flags": flag_statuses.get("critical", 0),
            "active_cascades": cascade_count,
            "horizon_count": horizon_count,
            "narrative_count": narrative_count,
            "cross_impact_count": cross_impact_count,
            "overall_risk_score": round(overall_risk, 4),
            "overall_risk_level": (
                "critical" if overall_risk >= 0.7 else
                "high" if overall_risk >= 0.5 else
                "medium" if overall_risk >= 0.3 else
                "low"
            ),
        }

    def get_threat_intelligence(
        self,
        location_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get aggregated intelligence for a location."""
        landscape = self.get_threat_landscape(location_id)

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Recent signals
        cur.execute(
            """
            SELECT s.signal_source, s.signal_type, COUNT(*) AS count,
                   AVG(s.confidence) AS avg_confidence, AVG(s.sentiment) AS avg_sentiment
            FROM threat_signal s
            LEFT JOIN threat t ON t.id = s.threat_id
            WHERE t.location_id = %s
              AND s.signal_date > NOW() - INTERVAL '%s days'
            GROUP BY s.signal_source, s.signal_type
            ORDER BY count DESC
            """,
            (location_id, days),
        )
        signal_summary = [dict(r) for r in cur.fetchall()]

        # Recent high-risk flags
        cur.execute(
            """
            SELECT f.flag_name, f.status, f.current_value, t.threat_name
            FROM threat_flag f
            JOIN threat t ON t.id = f.threat_id
            WHERE t.location_id = %s AND f.status IN ('warning', 'critical')
            ORDER BY f.status DESC
            LIMIT 10
            """,
            (location_id,),
        )
        high_risk_flags = [dict(r) for r in cur.fetchall()]

        # Top narratives by probability
        cur.execute(
            """
            SELECT n.title, n.narrative_type, n.probability_estimate,
                   n.desirability_score, t.threat_name
            FROM threat_narrative n
            JOIN threat t ON t.id = n.threat_id
            WHERE t.location_id = %s
            ORDER BY n.probability_estimate DESC NULLS LAST
            LIMIT 10
            """,
            (location_id,),
        )
        top_narratives = [dict(r) for r in cur.fetchall()]

        # Active cascades
        cur.execute(
            """
            SELECT c.cascade_name, c.cascade_probability, c.total_impact_severity,
                   t.threat_name AS trigger_name
            FROM threat_cascade c
            JOIN threat t ON t.id = c.trigger_threat_id
            WHERE t.location_id = %s AND c.is_enabled = TRUE
            ORDER BY c.cascade_probability DESC NULLS LAST
            LIMIT 5
            """,
            (location_id,),
        )
        active_cascades = [dict(r) for r in cur.fetchall()]

        cur.close()

        return {
            "location_id": location_id,
            "period_days": days,
            "landscape": landscape,
            "signal_summary": signal_summary,
            "high_risk_flags": high_risk_flags,
            "top_narratives": top_narratives,
            "active_cascades": active_cascades,
        }

    def generate_threat_briefing(self, location_id: str) -> Dict[str, Any]:
        """Generate executive-level threat briefing."""
        intelligence = self.get_threat_intelligence(location_id)
        landscape = intelligence["landscape"]

        # Build briefing sections
        key_findings = []
        recommendations = []

        # Key findings from landscape
        if landscape["critical_flags"] > 0:
            key_findings.append(f"{landscape['critical_flags']} critical warning flags active")
        if landscape["active_cascades"] > 0:
            key_findings.append(f"{landscape['active_cascades']} cascading failure scenarios detected")
        if landscape["overall_risk_level"] in ("high", "critical"):
            key_findings.append(f"Overall risk level: {landscape['overall_risk_level']}")

        # Recommendations
        if landscape["critical_flags"] > 0:
            recommendations.append("Immediate investigation of critical warning flags")
        if landscape["active_cascades"] > 0:
            recommendations.append("Review and activate cascade mitigation strategies")
        if landscape["narrative_count"] == 0:
            recommendations.append("Develop threat narratives for top risks")

        # Top threat types
        top_types = sorted(landscape["threats_by_type"].items(), key=lambda x: x[1], reverse=True)[:3]
        if top_types:
            key_findings.append(
                f"Top threat types: {', '.join(f'{t} ({c})' for t, c in top_types)}"
            )

        return {
            "location_id": location_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_summary": {
                "total_threats": landscape["threat_count"],
                "risk_level": landscape["overall_risk_level"],
                "risk_score": landscape["overall_risk_score"],
                "key_findings": key_findings,
                "recommendations": recommendations,
            },
            "detailed_intelligence": intelligence,
        }

    def predict_threat_evolution(
        self,
        threat_id: str,
        horizon_years: int = 5,
    ) -> Dict[str, Any]:
        """Predict how a threat might evolve over the horizon."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT id, threat_name, threat_type, severity_potential,
                   probability, velocity, reversibility, time_horizon_years
            FROM threat WHERE id = %s
            """,
            (threat_id,),
        )
        threat_row = cur.fetchone()
        threat = dict(threat_row) if threat_row else None
        if not threat:
            cur.close()
            return {"error": "Threat not found"}

        # Get velocity multiplier
        velocity_multipliers = {"slow": 0.05, "moderate": 0.10, "fast": 0.20, "rapid": 0.40}
        velocity_mult = velocity_multipliers.get(threat.get("velocity", "moderate"), 0.10)

        # Project probability over time
        base_prob = float(threat.get("probability") or 0.5)
        projections = []
        cumulative_prob = base_prob

        for year in range(1, horizon_years + 1):
            cumulative_prob = min(1.0, cumulative_prob * (1 + velocity_mult))
            projections.append({
                "year": year,
                "projected_probability": round(cumulative_prob, 4),
                "change": round(cumulative_prob - base_prob, 4),
            })

        # Get cross-impacts
        cur.execute(
            """
            SELECT ci.impact_type, ci.impact_magnitude, t.threat_name
            FROM threat_cross_impact ci
            JOIN threat t ON t.id = ci.target_threat_id
            WHERE ci.source_threat_id = %s AND ci.is_enabled = TRUE
            """,
            (threat_id,),
        )
        cross_impacts = [dict(r) for r in cur.fetchall()]

        cur.close()

        return {
            "threat": threat,
            "horizon_years": horizon_years,
            "projections": projections,
            "cross_impacts": cross_impacts,
            "velocity_factor": velocity_mult,
            "final_probability": projections[-1]["projected_probability"] if projections else base_prob,
        }
