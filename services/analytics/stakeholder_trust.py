"""Explainable party trust evidence and relationship risk service."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import psycopg2.extras


def _row(row: Any):
    return dict(row) if row else None


def record_evidence(conn, subject_party_id: str, dimension: str, direction: str, source_type: str, summary: str, *, relationship_party_id: Optional[str] = None, source_id: Optional[str] = None, source_label: Optional[str] = None, observed_at: Optional[str] = None, expires_at: Optional[str] = None, confidence: Optional[float] = None, uncertainty: Optional[float] = None, evidence_hash: Optional[str] = None, evidence_cid: Optional[str] = None, audience: str = "internal", created_by_party_id: Optional[str] = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO party_trust_evidence
            (subject_party_id, relationship_party_id, dimension, direction, source_type, source_id,
             source_label, summary, observed_at, expires_at, confidence, uncertainty, evidence_hash, evidence_cid, audience, created_by_party_id)
             VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s, %s, COALESCE(%s::timestamptz, NOW()), %s::timestamptz, %s, %s, %s, %s, %s, %s::uuid) RETURNING *""",
            (subject_party_id, relationship_party_id, dimension, direction, source_type, source_id, source_label, summary, observed_at, expires_at, confidence, uncertainty, evidence_hash, evidence_cid, audience, created_by_party_id))
        result = _row(cur.fetchone()); conn.commit(); return result


def verify_buyer(conn, buyer_id: str, verification_type: str, method: str, *, status: str = "verified", verified_by_party_id: Optional[str] = None, evidence_hash: Optional[str] = None, evidence_cid: Optional[str] = None, expires_at: Optional[str] = None):
    if status == "verified" and not verified_by_party_id:
        raise ValueError("verified buyer records require a human verifier")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO buyer_verification
            (buyer_id, verification_type, method, status, verified_by_party_id, verified_at, evidence_hash, evidence_cid, expires_at)
            VALUES (%s::uuid, %s, %s, %s, %s::uuid, CASE WHEN %s = 'verified' THEN NOW() ELSE NULL END, %s, %s, %s::timestamptz) RETURNING *""",
            (buyer_id, verification_type, method, status, verified_by_party_id, status, evidence_hash, evidence_cid, expires_at))
        result = _row(cur.fetchone())
        if status == "verified":
            cur.execute("UPDATE buyer_profile SET verified = TRUE, verified_at = NOW(), updated_at = NOW() WHERE id = %s::uuid", (buyer_id,))
        conn.commit(); return result


def open_dispute(conn, order_id: str, dispute_type: str, summary: str, *, opened_by_party_id: Optional[str] = None, requested_remedy: Optional[str] = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""INSERT INTO market_dispute
            (order_id, opened_by_party_id, dispute_type, summary, requested_remedy)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s) RETURNING *""",
            (order_id, opened_by_party_id, dispute_type, summary, requested_remedy))
        result = _row(cur.fetchone()); conn.commit(); return result


def profile(conn, party_id: str):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_party_trust_profile WHERE party_id = %s::uuid", (party_id,)); return _row(cur.fetchone())


def evidence_timeline(conn, party_id: str):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_party_trust_evidence_timeline WHERE subject_party_id = %s::uuid ORDER BY observed_at DESC", (party_id,)); return [dict(row) for row in cur.fetchall()]


def risk_indicators(conn, party_id: Optional[str] = None):
    query = "SELECT * FROM relationship_risk_indicator"; params = []
    if party_id:
        query += " WHERE subject_party_id = %s::uuid"; params.append(party_id)
    query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at DESC"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params); return [dict(row) for row in cur.fetchall()]
