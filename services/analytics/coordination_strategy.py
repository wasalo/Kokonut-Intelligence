"""Coordination strategy orchestration facade.

This facade keeps alliance lifecycle operations separate from accounting and
learning evidence. It deliberately does not create ownership or reputation.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from services.analytics.coordination import (
    _conn,
    _row,
    activate_alliance,
    activate_participant,
    add_objective,
    add_participant,
    approve_alliance,
    create_alliance,
    get_coordination_health,
    list_alliances,
)
from services.analytics.coordination_accounting import explain_coordination_health, link_learning_target


def create_coordination_alliance(*args, **kwargs) -> Dict[str, Any]:
    return create_alliance(*args, **kwargs)


def manage_participant(*args, **kwargs) -> Dict[str, Any]:
    return add_participant(*args, **kwargs)


def review_and_renew(
    alliance_id: str,
    period_start: date,
    period_end: date,
    reviewer_party_id: str,
    participation_summary: str,
    benefit_summary: str,
    harm_and_risk_summary: str,
    findings: str,
    recommendation: str,
) -> Dict[str, Any]:
    """Record a human review; renewal creates a proposed new term."""
    if recommendation not in {"continue", "amend", "pause", "close", "escalate"}:
        raise ValueError("invalid coordination review recommendation")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO coordination_review
               (alliance_id, period_start, period_end, reviewer_party_id,
                participation_summary, benefit_summary, harm_and_risk_summary,
                findings, recommendation, status)
               VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s, %s, %s, %s, 'submitted')
               RETURNING id""",
            (alliance_id, period_start, period_end, reviewer_party_id,
             participation_summary, benefit_summary, harm_and_risk_summary,
             findings, recommendation),
        )
        review_id = cur.fetchone()[0]
        if recommendation in {"continue", "amend"}:
            cur.execute(
                "UPDATE coordination_alliance SET status = 'proposed', approved_by_party_id = NULL, approved_at = NULL, approval_basis = NULL WHERE id = %s::uuid",
                (alliance_id,),
            )
        elif recommendation == "pause":
            cur.execute("UPDATE coordination_alliance SET status = 'paused' WHERE id = %s::uuid", (alliance_id,))
        elif recommendation == "close":
            cur.execute("UPDATE coordination_alliance SET status = 'dissolved', ends_at = NOW() WHERE id = %s::uuid", (alliance_id,))
        conn.commit()
    return {"review_id": str(review_id), "alliance_id": alliance_id, "recommendation": recommendation}


__all__ = [
    "activate_alliance", "activate_participant", "add_objective", "approve_alliance",
    "create_coordination_alliance", "explain_coordination_health", "get_coordination_health",
    "link_learning_target", "list_alliances", "manage_participant", "review_and_renew",
]
