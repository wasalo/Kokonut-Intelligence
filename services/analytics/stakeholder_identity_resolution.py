"""Human-reviewed source identity resolution for canonical stakeholder parties."""

from __future__ import annotations

from typing import Any, Dict, Optional

import psycopg2.extras


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return dict(row) if row else None


def propose_link(conn, source_system: str, source_type: str, source_id: str,
                 party_id: str, proposed_party_type: str, *,
                 match_method: str = "manual", confidence: Optional[float] = None,
                 evidence: Optional[list] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO party_resolution_case
               (source_system, source_type, source_id, candidate_party_id, proposed_party_type,
                match_method, confidence, evidence)
               VALUES (%s, %s, %s, %s::uuid, %s, %s, %s, %s::jsonb)
               ON CONFLICT (source_system, source_type, source_id) DO UPDATE SET
                 candidate_party_id = EXCLUDED.candidate_party_id,
                 proposed_party_type = EXCLUDED.proposed_party_type,
                 match_method = EXCLUDED.match_method,
                 confidence = EXCLUDED.confidence,
                 evidence = EXCLUDED.evidence,
                 status = 'proposed', reviewed_by_party_id = NULL, reviewed_at = NULL,
                 review_notes = NULL
               RETURNING *""",
            (source_system, source_type, source_id, party_id, proposed_party_type,
             match_method, confidence, psycopg2.extras.Json(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def review_link(conn, resolution_case_id: str, reviewer_party_id: str, *,
                approved: bool, notes: str) -> Optional[Dict[str, Any]]:
    if not notes.strip():
        raise ValueError("identity review notes are required")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM party_resolution_case WHERE id = %s::uuid", (resolution_case_id,))
        case = cur.fetchone()
        if not case:
            raise ValueError("identity resolution case not found")
        status = "approved" if approved else "rejected"
        cur.execute(
            """UPDATE party_resolution_case
               SET status = %s, reviewed_by_party_id = %s::uuid, reviewed_at = NOW(), review_notes = %s
               WHERE id = %s::uuid AND status IN ('proposed', 'in_review') RETURNING *""",
            (status, reviewer_party_id, notes, resolution_case_id),
        )
        result = _row(cur.fetchone())
        if result and approved:
            cur.execute(
                """INSERT INTO party_identifier
                   (party_id, identifier_type, identifier_value, source_system, source_id,
                    verification_status, confidence, reviewed_by, reviewed_at, evidence)
                   VALUES (%s::uuid, %s, %s, %s, %s, 'verified', %s, %s::uuid, NOW(), %s::jsonb)
                   ON CONFLICT (identifier_type, identifier_value, source_system) DO UPDATE SET
                     party_id = EXCLUDED.party_id, source_id = EXCLUDED.source_id,
                     verification_status = 'verified', confidence = EXCLUDED.confidence,
                     reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at,
                     evidence = EXCLUDED.evidence""",
                (case["candidate_party_id"], case["source_type"], case["source_id"],
                 case["source_system"], case["source_id"], case["confidence"], reviewer_party_id,
                 psycopg2.extras.Json(case["evidence"] or [])),
            )
        conn.commit()
        return result


def resolution_queue(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_party_resolution_queue ORDER BY created_at")
        return [dict(row) for row in cur.fetchall()]


def verified_party_for_source(conn, source_system: str, source_type: str, source_id: str):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM v_canonical_party_source_links
               WHERE source_system = %s AND identifier_type = %s AND source_id = %s""",
            (source_system, source_type, source_id),
        )
        return _row(cur.fetchone())
