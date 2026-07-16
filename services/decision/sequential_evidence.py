"""Immutable evidence ledger primitives for sequential decisions."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_hypothesis(conn, subject_type: str, subject_id: str, statement: str, alternative_statement: str, prior_probability: float, *, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if not 0 < prior_probability < 1:
        raise ValueError("prior probability must be between zero and one")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO decision_hypothesis
            (subject_type, subject_id, statement, alternative_statement, prior_probability, created_by_party_id)
            VALUES (%s, %s::uuid, %s, %s, %s, %s::uuid) RETURNING *""", (subject_type, subject_id, statement, alternative_statement, prior_probability, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def record_evidence(conn, hypothesis_id: str, source_type: str, evidence_class: str, observed_at: str, *, source_id: Optional[str] = None, source_ref: Optional[str] = None, value: Optional[dict[str, Any]] = None, quality_status: str = "unverified", source_reliability: Optional[float] = None, dependence_group: Optional[str] = None, likelihood_hypothesis: Optional[float] = None, likelihood_alternative: Optional[float] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if not source_id and not source_ref:
        raise ValueError("evidence requires a source id or reference")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO decision_evidence_event
            (hypothesis_id, source_type, source_id, source_ref, observed_at, evidence_class,
             value, quality_status, source_reliability, dependence_group,
             likelihood_hypothesis, likelihood_alternative, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::uuid)
            RETURNING *""", (hypothesis_id, source_type, source_id, source_ref, observed_at,
                              evidence_class, json.dumps(value or {}), quality_status,
                              source_reliability, dependence_group, likelihood_hypothesis,
                              likelihood_alternative, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def list_evidence(conn, hypothesis_id: str) -> list[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM decision_evidence_event WHERE hypothesis_id = %s::uuid ORDER BY observed_at, created_at", (hypothesis_id,))
        return [_clean(row) for row in cur.fetchall()]
