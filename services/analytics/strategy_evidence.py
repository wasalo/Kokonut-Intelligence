"""Typed evidence lineage for strategic planning artifacts."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


SUBJECT_TYPES = ("plan", "choice", "assumption", "position", "advantage", "objective", "investment", "benefit")
SOURCE_TYPES = ("pestel_factor", "swot_factor", "competitive_signal", "competitive_force", "scenario", "threat_signal", "stakeholder_outcome", "crisp_assessment", "metric_value", "capability", "market_segment", "external_document")


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def link_evidence(conn, strategy_plan_id: str, subject_type: str, subject_id: str, source_type: str, *, source_id: Optional[str] = None, source_ref: Optional[str] = None, relevance: str = "supporting", confidence: str = "moderate", evidence_maturity: Optional[int] = None, source_version: Optional[str] = None, interpretation: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if subject_type not in SUBJECT_TYPES:
        raise ValueError("invalid strategy evidence subject type")
    if source_type not in SOURCE_TYPES:
        raise ValueError("invalid strategy evidence source type")
    if not source_id and not source_ref:
        raise ValueError("source_id or source_ref is required")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT * FROM strategy_evidence_link
            WHERE strategy_plan_id = %s::uuid AND subject_type = %s AND subject_id = %s::uuid
              AND source_type = %s AND source_id IS NOT DISTINCT FROM %s::uuid
              AND source_ref IS NOT DISTINCT FROM %s
            FOR UPDATE""", (strategy_plan_id, subject_type, subject_id, source_type, source_id, source_ref))
        existing = cur.fetchone()
        if existing:
            cur.execute("""UPDATE strategy_evidence_link SET relevance = %s, confidence = %s,
                evidence_maturity = %s, source_version = %s, interpretation = %s
                WHERE id = %s::uuid RETURNING *""", (relevance, confidence, evidence_maturity, source_version, interpretation, existing["id"]))
            row = _clean(cur.fetchone())
            conn.commit()
            return row
        cur.execute("""INSERT INTO strategy_evidence_link
            (strategy_plan_id, subject_type, subject_id, source_type, source_id, source_ref, relevance, confidence, evidence_maturity, source_version, interpretation, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid)
            RETURNING *""", (strategy_plan_id, subject_type, subject_id, source_type, source_id, source_ref, relevance, confidence, evidence_maturity, source_version, interpretation, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def list_evidence(conn, strategy_plan_id: str, *, subject_type: Optional[str] = None, subject_id: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = ["strategy_plan_id = %s::uuid"]
    params: List[Any] = [strategy_plan_id]
    if subject_type:
        clauses.append("subject_type = %s")
        params.append(subject_type)
    if subject_id:
        clauses.append("subject_id = %s::uuid")
        params.append(subject_id)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM strategy_evidence_link WHERE {' AND '.join(clauses)} ORDER BY created_at DESC", params)
        return [_clean(row) for row in cur.fetchall()]
