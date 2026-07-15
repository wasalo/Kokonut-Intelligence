"""Canonical stakeholder registry and relationship service.

This layer links existing domain identities without replacing them. Uncertain
links remain candidate records until a reviewer verifies them.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import psycopg2.extras


PARTY_TYPES = (
    "person", "organization", "community", "cooperative",
    "public_institution", "ecosystem", "species", "future_generation",
)
RELATIONSHIP_LEGITIMACY = ("normative", "derivative", "proxy", "unknown")
INTEREST_TYPES = ("need", "claim", "obligation", "dependency", "benefit", "harm", "stewardship")
SCOPE_TYPES = ("network", "organization", "location", "farm", "cooperative", "value_stream", "initiative", "decision")


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row(row: Any) -> Optional[Dict[str, Any]]:
    return {key: _value(value) for key, value in dict(row).items()} if row else None


def create_party(
    conn,
    party_type: str,
    display_name: str,
    *,
    description: str = "",
    privacy_level: str = "private",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if party_type not in PARTY_TYPES:
        raise ValueError(f"party_type must be one of {PARTY_TYPES}")
    if privacy_level not in ("private", "limited", "public"):
        raise ValueError("privacy_level must be private, limited, or public")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO party (party_type, display_name, description, privacy_level, metadata)
               VALUES (%s, %s, %s, %s, %s::jsonb) RETURNING *""",
            (party_type, display_name, description, privacy_level, json.dumps(metadata or {})),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def list_parties(conn, *, party_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if party_type:
        if party_type not in PARTY_TYPES:
            raise ValueError(f"party_type must be one of {PARTY_TYPES}")
        clauses.append("party_type = %s")
        params.append(party_type)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM v_stakeholder_landscape{where} ORDER BY display_name", params)
        return [_row(row) for row in cur.fetchall()]


def get_party(conn, party_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM party WHERE id = %s::uuid", (party_id,))
        party = _row(cur.fetchone())
        if not party:
            return None
        cur.execute("SELECT * FROM party_identifier WHERE party_id = %s::uuid ORDER BY created_at", (party_id,))
        party["identifiers"] = [_row(row) for row in cur.fetchall()]
        cur.execute(
            """SELECT pr.*, fp.display_name AS from_party_name, tp.display_name AS to_party_name
               FROM party_relationship pr
               JOIN party fp ON fp.id = pr.from_party_id
               JOIN party tp ON tp.id = pr.to_party_id
               WHERE pr.from_party_id = %s::uuid OR pr.to_party_id = %s::uuid
               ORDER BY pr.created_at DESC""",
            (party_id, party_id),
        )
        party["relationships"] = [_row(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT * FROM stakeholder_interest WHERE party_id = %s::uuid ORDER BY priority DESC, created_at DESC",
            (party_id,),
        )
        party["interests"] = [_row(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT * FROM stakeholder_salience_assessment WHERE party_id = %s::uuid ORDER BY assessed_at DESC",
            (party_id,),
        )
        party["salience_assessments"] = [_row(row) for row in cur.fetchall()]
        return party


def add_identifier(
    conn,
    party_id: str,
    identifier_type: str,
    identifier_value: str,
    source_system: str,
    *,
    source_id: Optional[str] = None,
    verification_status: str = "candidate",
    confidence: Optional[float] = None,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if verification_status not in ("unreviewed", "candidate", "verified", "rejected"):
        raise ValueError("invalid verification_status")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO party_identifier
               (party_id, identifier_type, identifier_value, source_system, source_id,
                verification_status, confidence, evidence)
               VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb)
               ON CONFLICT (identifier_type, identifier_value, source_system) DO UPDATE SET
                   party_id = EXCLUDED.party_id,
                   source_id = EXCLUDED.source_id,
                   verification_status = EXCLUDED.verification_status,
                   confidence = EXCLUDED.confidence,
                   evidence = EXCLUDED.evidence,
                   updated_at = NOW()
               RETURNING *""",
            (party_id, identifier_type, identifier_value, source_system, source_id,
             verification_status, confidence, json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def link_parties(
    conn,
    from_party_id: str,
    to_party_id: str,
    relationship_type: str,
    *,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    legitimacy: str = "derivative",
    status: str = "proposed",
    confidence: Optional[float] = None,
    evidence: Optional[List[Any]] = None,
    notes: str = "",
    accountable_party_id: Optional[str] = None,
    responsibility_id: Optional[str] = None,
) -> Dict[str, Any]:
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"scope_type must be one of {SCOPE_TYPES}")
    if legitimacy not in RELATIONSHIP_LEGITIMACY:
        raise ValueError(f"legitimacy must be one of {RELATIONSHIP_LEGITIMACY}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO party_relationship
               (from_party_id, to_party_id, relationship_type, scope_type, scope_id,
                legitimacy, status, confidence, evidence, notes, accountable_party_id, responsibility_id)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s::uuid, %s, %s, %s, %s::jsonb, %s, %s::uuid, %s::uuid)
               RETURNING *""",
            (from_party_id, to_party_id, relationship_type, scope_type, scope_id,
             legitimacy, status, confidence, json.dumps(evidence or []), notes,
             accountable_party_id, responsibility_id),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def add_interest(
    conn,
    party_id: str,
    interest_type: str,
    title: str,
    *,
    description: str = "",
    legitimacy: str = "normative",
    priority: int = 3,
    scope_type: str = "network",
    scope_id: Optional[str] = None,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if interest_type not in INTEREST_TYPES:
        raise ValueError(f"interest_type must be one of {INTEREST_TYPES}")
    if legitimacy not in RELATIONSHIP_LEGITIMACY:
        raise ValueError(f"legitimacy must be one of {RELATIONSHIP_LEGITIMACY}")
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"scope_type must be one of {SCOPE_TYPES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_interest
               (party_id, interest_type, title, description, legitimacy, priority,
                scope_type, scope_id, evidence)
               VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid, %s::jsonb)
               RETURNING *""",
            (party_id, interest_type, title, description, legitimacy, priority,
             scope_type, scope_id, json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def assess_salience(
    conn,
    party_id: str,
    *,
    interest_id: Optional[str] = None,
    power: float = 0,
    legitimacy: float = 0,
    urgency: float = 0,
    vulnerability: float = 0,
    harm_exposure: float = 0,
    representation: float = 0,
    rationale: str,
    evidence: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    if not rationale.strip():
        raise ValueError("rationale is required for a salience assessment")
    scores = (power, legitimacy, urgency, vulnerability, harm_exposure, representation)
    if any(score < 0 or score > 10 for score in scores):
        raise ValueError("salience scores must be between 0 and 10")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_salience_assessment
               (party_id, interest_id, power_score, legitimacy_score, urgency_score,
                vulnerability_score, harm_exposure_score, representation_score, rationale, evidence)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
               RETURNING *""",
            (party_id, interest_id, power, legitimacy, urgency, vulnerability,
             harm_exposure, representation, rationale, json.dumps(evidence or [])),
        )
        result = _row(cur.fetchone())
        conn.commit()
        return result


def list_landscape(conn, *, party_type: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_parties(conn, party_type=party_type)
