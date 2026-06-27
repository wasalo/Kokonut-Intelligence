"""Equity and community scoring from aggregate, privacy-safe signals."""

from __future__ import annotations

from typing import Any

import psycopg2.extras

from .calculators import compute_equity_community_score


def compute_equity_score_from_feedback(conn, location_id: str) -> dict[str, Any]:
    """Compute an equity score from aggregate stakeholder feedback only.

    This helper intentionally does not return raw feedback text.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            COUNT(*) AS feedback_count,
            COUNT(*) FILTER (WHERE consent_given = TRUE AND is_public = TRUE AND public_summary IS NOT NULL) AS public_safe_feedback_count,
            COUNT(*) FILTER (WHERE sentiment = 'positive') AS positive_count,
            COUNT(*) FILTER (WHERE sentiment = 'negative') AS negative_count,
            COUNT(DISTINCT stakeholder_group) AS stakeholder_group_count
        FROM stakeholder_feedback
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    row = dict(cur.fetchone() or {})
    cur.close()

    feedback_count = int(row.get("feedback_count") or 0)
    public_safe_count = int(row.get("public_safe_feedback_count") or 0)
    positive_count = int(row.get("positive_count") or 0)
    negative_count = int(row.get("negative_count") or 0)
    stakeholder_group_count = int(row.get("stakeholder_group_count") or 0)
    if feedback_count == 0:
        return {
            "score": 0.0,
            "confidence": "insufficient_evidence",
            "feedback_count": 0,
            "public_safe_feedback_count": 0,
            "safety_note": "No raw stakeholder feedback is exposed.",
        }

    sentiment_balance_pct = max(0.0, min(100.0, ((positive_count - negative_count) / feedback_count) * 50 + 50))
    coverage_pct = min(100.0, (public_safe_count / feedback_count) * 70 + min(stakeholder_group_count, 3) * 10)
    score = compute_equity_community_score(coverage_pct, sentiment_balance_pct / 2.5)
    confidence = "high" if public_safe_count >= 3 and stakeholder_group_count >= 2 else "moderate" if public_safe_count >= 1 else "low"
    return {
        "score": score,
        "confidence": confidence,
        "feedback_count": feedback_count,
        "public_safe_feedback_count": public_safe_count,
        "stakeholder_group_count": stakeholder_group_count,
        "safety_note": "Aggregate stakeholder feedback only; raw private feedback is not exposed.",
    }
