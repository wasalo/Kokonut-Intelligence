"""Coordination strategy orchestration facade.

This facade keeps alliance lifecycle operations separate from accounting and
learning evidence. It deliberately does not create ownership or reputation.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from services.analytics.coordination import (
    _conn,
    _insert,
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


def declare_conflict(
    alliance_id: str,
    party_id: str,
    declaration_type: str,
    description: str,
    *,
    recusal_required: bool = False,
    recused_from: Optional[str] = None,
) -> Dict[str, Any]:
    if declaration_type not in {"conflict", "no_conflict"}:
        raise ValueError("declaration_type must be conflict or no_conflict")
    return _insert("coordination_conflict_declaration", {
        "alliance_id": alliance_id, "party_id": party_id,
        "declaration_type": declaration_type, "description": description,
        "recusal_required": recusal_required, "recused_from": recused_from,
    })


def review_conflict_declaration(declaration_id: str, reviewed_by_party_id: str, status: str = "reviewed") -> Dict[str, Any]:
    if status not in {"reviewed", "managed", "dismissed"}:
        raise ValueError("invalid conflict declaration review status")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE coordination_conflict_declaration SET status = %s, reviewed_by_party_id = %s::uuid, reviewed_at = NOW() WHERE id = %s::uuid RETURNING id, status",
            (status, reviewed_by_party_id, declaration_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("conflict declaration not found")
        return {"id": str(row[0]), "status": row[1]}


def record_benefit_harm_analysis(
    alliance_id: str,
    analysis_type: str,
    description: str,
    *,
    party_id: Optional[str] = None,
    severity: Optional[str] = None,
    mitigation: Optional[str] = None,
) -> Dict[str, Any]:
    if analysis_type not in {"benefit", "harm"}:
        raise ValueError("analysis_type must be benefit or harm")
    return _insert("coordination_benefit_harm_analysis", {
        "alliance_id": alliance_id, "party_id": party_id,
        "analysis_type": analysis_type, "description": description,
        "severity": severity, "mitigation": mitigation,
    })


def review_benefit_harm_analysis(analysis_id: str, reviewed_by_party_id: str, status: str = "reviewed") -> Dict[str, Any]:
    if status not in {"reviewed", "accepted", "rejected"}:
        raise ValueError("invalid benefit/harm analysis review status")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE coordination_benefit_harm_analysis SET status = %s, reviewed_by_party_id = %s::uuid, reviewed_at = NOW() WHERE id = %s::uuid RETURNING id, status",
            (status, reviewed_by_party_id, analysis_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("benefit/harm analysis not found")
        return {"id": str(row[0]), "status": row[1]}


def preserve_minority_view(
    alliance_id: str,
    view_text: str,
    *,
    party_id: Optional[str] = None,
    anonymous_group: Optional[str] = None,
    review_id: Optional[str] = None,
    consent_checked: bool = False,
) -> Dict[str, Any]:
    return _insert("coordination_minority_view", {
        "alliance_id": alliance_id, "view_text": view_text,
        "party_id": party_id, "anonymous_group": anonymous_group,
        "review_id": review_id, "consent_checked": consent_checked,
    })


def file_appeal(
    alliance_id: str,
    target_type: str,
    target_id: str,
    appealed_by_party_id: str,
    reason: str,
    *,
    correction_requested: bool = False,
) -> Dict[str, Any]:
    return _insert("coordination_appeal", {
        "alliance_id": alliance_id, "target_type": target_type,
        "target_id": target_id, "appealed_by_party_id": appealed_by_party_id,
        "reason": reason, "correction_requested": correction_requested,
    })


def propose_remedy(
    alliance_id: str,
    description: str,
    remedy_type: str = "other",
    *,
    harm_analysis_id: Optional[str] = None,
    benefit_id: Optional[str] = None,
) -> Dict[str, Any]:
    return _insert("coordination_remedy", {
        "alliance_id": alliance_id, "description": description,
        "remedy_type": remedy_type, "harm_analysis_id": harm_analysis_id,
        "benefit_id": benefit_id,
    })


def approve_remedy(remedy_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE coordination_remedy SET status = 'approved', approved_by_party_id = %s::uuid,
               approved_at = NOW() WHERE id = %s::uuid AND status = 'proposed'
               RETURNING id, status""",
            (approved_by_party_id, remedy_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("remedy not found or already transitioned")
        return {"id": str(row[0]), "status": row[1]}


def complete_remedy(remedy_id: str, completed_by_party_id: str, evidence: str) -> Dict[str, Any]:
    if not evidence.strip():
        raise ValueError("remedy completion evidence is required")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE coordination_remedy
               SET status = 'completed', completed_by_party_id = %s::uuid,
                   completed_at = NOW(), evidence = evidence || %s::jsonb
               WHERE id = %s::uuid AND status IN ('approved', 'in_progress')
               RETURNING id, status""",
            (completed_by_party_id, json.dumps([{"type": "completion", "evidence": evidence}]), remedy_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("remedy must be approved or in progress before completion")
        return {"id": str(row[0]), "status": row[1]}


def publish_alliance(
    alliance_id: str,
    published_by_party_id: str,
    public_summary: str,
    limitations: str,
    public_evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not public_summary.strip() or not limitations.strip():
        raise ValueError("public summary and limitations are required")
    evidence = public_evidence or []
    if not any(item.get("verified") is True or item.get("status") in {"verified", "published"} for item in evidence):
        raise ValueError("at least one verified public evidence item is required")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE coordination_alliance
               SET publication_status = 'published', published_by_party_id = %s::uuid,
                   published_at = NOW(), public_summary = %s, public_evidence = %s::jsonb,
                   public_limitations = %s
               WHERE id = %s::uuid RETURNING id, publication_status""",
            (published_by_party_id, public_summary, json.dumps(evidence), limitations, alliance_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("alliance not found or not publishable")
        return {"id": str(row[0]), "publication_status": row[1]}


def suspend_alliance(alliance_id: str, reviewed_by_party_id: str, reason: str) -> Dict[str, Any]:
    if not reason.strip():
        raise ValueError("suspension reason is required")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE coordination_alliance SET status = 'paused', evidence = evidence || %s::jsonb WHERE id = %s::uuid AND status = 'active' RETURNING id, status",
            (json.dumps([{"type": "suspension", "reviewed_by": reviewed_by_party_id, "reason": reason}]), alliance_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("only active alliances can be suspended")
        return {"id": str(row[0]), "status": row[1]}


def terminate_alliance(alliance_id: str, terminated_by_party_id: str, reason: str) -> Dict[str, Any]:
    if not reason.strip():
        raise ValueError("termination reason is required")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE coordination_alliance SET status = 'dissolved', ends_at = NOW(), evidence = evidence || %s::jsonb WHERE id = %s::uuid AND status NOT IN ('dissolved', 'completed') RETURNING id, status",
            (json.dumps([{"type": "termination", "reviewed_by": terminated_by_party_id, "reason": reason}]), alliance_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            raise ValueError("alliance is already terminated or not found")
        return {"id": str(row[0]), "status": row[1]}


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
            "SELECT COUNT(*) FROM coordination_partner_event WHERE alliance_id = %s::uuid AND event_type = 'failure' AND resolved_at IS NULL",
            (alliance_id,),
        )
        unresolved_failures = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM coordination_market_observation WHERE alliance_id = %s::uuid AND outcome IN ('disputed', 'cancelled', 'late')",
            (alliance_id,),
        )
        adverse_market_events = cur.fetchone()[0]
        review_findings = findings
        if unresolved_failures:
            review_findings += "\nUnresolved partner failure events require substitution or remediation review."
        if adverse_market_events:
            review_findings += "\nAdverse market performance requires renewal safeguards."
        cur.execute(
            """INSERT INTO coordination_review
               (alliance_id, period_start, period_end, reviewer_party_id,
                participation_summary, benefit_summary, harm_and_risk_summary,
                findings, recommendation, status)
               VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s, %s, %s, %s, 'submitted')
               RETURNING id""",
            (alliance_id, period_start, period_end, reviewer_party_id,
             participation_summary, benefit_summary, harm_and_risk_summary,
             review_findings, recommendation),
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
    "declare_conflict", "file_appeal", "link_learning_target", "list_alliances",
    "manage_participant", "preserve_minority_view", "propose_remedy", "approve_remedy", "complete_remedy",
    "publish_alliance", "record_benefit_harm_analysis", "review_benefit_harm_analysis",
    "review_conflict_declaration", "review_and_renew", "suspend_alliance", "terminate_alliance",
]
