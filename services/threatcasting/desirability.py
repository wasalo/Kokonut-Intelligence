"""Desirability Assessor — evaluates threat narratives against wellbeing frameworks
(GNH, 8 Forms of Capital, SDGs)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger
from services.threatcasting.config import (
    EIGHT_FORMS_OF_CAPITAL,
    GNH_DIMENSIONS,
    SDG_ALIGNMENT,
)

logger = get_logger(__name__)

FRAMEWORK_REGISTRY: Dict[str, List[Dict[str, Any]]] = {
    "gnh": GNH_DIMENSIONS,
    "8_forms_capital": EIGHT_FORMS_OF_CAPITAL,
    "sdg": SDG_ALIGNMENT,
    "composite": GNH_DIMENSIONS + EIGHT_FORMS_OF_CAPITAL,
}


class DesirabilityAssessor:
    """Assesses desirability of threat narratives against wellbeing frameworks."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def assess(
        self,
        narrative_id: str,
        framework: str = "gnh",
        assessments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create desirability assessments for a narrative."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get dimensions for framework
        dimensions = FRAMEWORK_REGISTRY.get(framework, GNH_DIMENSIONS)
        created = []

        if assessments:
            # Use provided assessments
            for a in assessments:
                a_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO threat_desirability_assessment
                        (id, narrative_id, assessment_framework, dimension,
                         score, weight, rationale, data_sources, assessed_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        a_id, narrative_id, framework, a["dimension"],
                        a["score"], a.get("weight", 1.0), a.get("rationale"),
                        a.get("data_sources", []), a.get("assessed_by"),
                    ),
                )
                created.append(dict(cur.fetchone()))
        else:
            # Create placeholder assessments
            for dim in dimensions:
                a_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO threat_desirability_assessment
                        (id, narrative_id, assessment_framework, dimension,
                         score, weight, rationale)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        a_id, narrative_id, framework, dim["name"],
                        0.0, dim.get("weight", 1.0),
                        f"Default assessment for {dim['name']}",
                    ),
                )
                created.append(dict(cur.fetchone()))

        conn.commit()
        cur.close()

        # Compute overall score
        overall = self._compute_overall_score(created)

        # Update narrative desirability_score
        cur2 = conn.cursor()
        cur2.execute(
            "UPDATE threat_narrative SET desirability_score = %s, updated_at = NOW() WHERE id = %s",
            (overall["overall_score"], narrative_id),
        )
        conn.commit()
        cur2.close()

        logger.info("Assessed narrative %s with %s framework: score=%.4f", narrative_id, framework, overall["overall_score"])
        return {
            "narrative_id": narrative_id,
            "framework": framework,
            "assessments": created,
            "overall": overall,
        }

    def _compute_overall_score(self, assessments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute weighted overall desirability score."""
        if not assessments:
            return {"overall_score": 0.0, "dimension_scores": {}, "framework_scores": {}}

        total_weighted = 0.0
        total_weight = 0.0
        dimension_scores = {}

        for a in assessments:
            score = float(a.get("score", 0))
            weight = float(a.get("weight", 1.0))
            total_weighted += score * weight
            total_weight += weight
            dimension_scores[a["dimension"]] = score

        overall = total_weighted / total_weight if total_weight > 0 else 0.0

        return {
            "overall_score": round(overall, 4),
            "total_weight": round(total_weight, 4),
            "dimension_scores": dimension_scores,
        }

    def get_assessments(
        self,
        narrative_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all assessments for a narrative."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT * FROM threat_desirability_assessment
            WHERE narrative_id = %s
            ORDER BY dimension
            """,
            (narrative_id,),
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def get_desirability_summary(self, narrative_id: str) -> Dict[str, Any]:
        """Get summary of desirability for a narrative."""
        assessments = self.get_assessments(narrative_id)
        if not assessments:
            return {"narrative_id": narrative_id, "overall_score": 0.0, "dimensions": []}

        # Group by framework
        by_framework: Dict[str, List[Dict]] = {}
        for a in assessments:
            fw = a["assessment_framework"]
            if fw not in by_framework:
                by_framework[fw] = []
            by_framework[fw].append(a)

        # Compute per-framework scores
        framework_scores = {}
        for fw, items in by_framework.items():
            total_w = sum(float(i.get("weight", 1.0)) for i in items)
            total_ws = sum(float(i.get("score", 0)) * float(i.get("weight", 1.0)) for i in items)
            framework_scores[fw] = round(total_ws / total_w, 4) if total_w > 0 else 0.0

        # Overall across all frameworks
        overall = self._compute_overall_score(assessments)

        return {
            "narrative_id": narrative_id,
            "overall_score": overall["overall_score"],
            "framework_scores": framework_scores,
            "dimension_scores": overall["dimension_scores"],
            "assessment_count": len(assessments),
        }

    def compare_desirability(
        self,
        narrative_ids: List[str],
    ) -> Dict[str, Any]:
        """Compare desirability across multiple narratives."""
        summaries = {}
        for nid in narrative_ids:
            summaries[nid] = self.get_desirability_summary(nid)

        scores = {nid: s["overall_score"] for nid, s in summaries.items()}
        best = max(scores, key=scores.get) if scores else None
        worst = min(scores, key=scores.get) if scores else None

        return {
            "narrative_ids": narrative_ids,
            "summaries": summaries,
            "scores": scores,
            "best_narrative": best,
            "worst_narrative": worst,
            "score_range": round(scores[best] - scores[worst], 4) if best and worst else 0,
        }

    def get_gnh_alignment(self, narrative_id: str) -> Dict[str, Any]:
        """Get GNH-specific assessment for a narrative."""
        assessments = self.get_assessments(narrative_id)
        gnh_assessments = [a for a in assessments if a["assessment_framework"] == "gnh"]

        if not gnh_assessments:
            return {
                "narrative_id": narrative_id,
                "aligned": False,
                "overall_score": 0.0,
                "dimension_scores": {},
            }

        overall = self._compute_overall_score(gnh_assessments)
        aligned = overall["overall_score"] >= 0.0  # Non-negative = aligned

        return {
            "narrative_id": narrative_id,
            "aligned": aligned,
            "overall_score": overall["overall_score"],
            "dimension_scores": overall["dimension_scores"],
        }

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete an assessment."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM threat_desirability_assessment WHERE id = %s", (assessment_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted
