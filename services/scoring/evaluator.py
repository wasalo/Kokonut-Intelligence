"""Evaluator registry and attester reputation scoring.

Manages the Impact Web of Trust evaluator identity, reputation
computation, and cross-attestation linking.

Usage:
    python3 -m services.scoring --evaluator-register --wallet 0x... --type citizen
    python3 -m services.scoring --evaluator-profile --evaluator-id UUID
    python3 -m services.scoring --evaluator-list --type expert
    python3 -m services.scoring --link-attestations --source UUID --target UUID --type supports
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("scoring.evaluator")

# Reputation weights
ACCURACY_WEIGHT = 0.40
LONGEVITY_WEIGHT = 0.30
DOMAIN_WEIGHT = 0.20
RECENCY_WEIGHT = 0.10

# Daily decay rate for recency
DECAY_RATE = 0.01


def register_evaluator(
    conn,
    evaluator_type: str,
    wallet_address: str = None,
    did: str = None,
    ens_name: str = None,
    display_name: str = None,
    domain_expertise: list = None,
    specialization: str = None,
    organization: str = None,
    credentials: str = None,
    metadata: dict = None,
) -> str:
    """Register a new evaluator.

    Args:
        conn: PostgreSQL connection.
        evaluator_type: One of 'citizen', 'professional', 'expert', 'funder', 'self'.
        wallet_address: Ethereum wallet address.
        did: Decentralized Identifier.
        ens_name: Ethereum Name Service name.
        display_name: Human-readable name.
        domain_expertise: List of expertise domains.
        specialization: Primary specialization.
        organization: Affiliated organization.
        credentials: Qualifications/certifications.
        metadata: Additional metadata.

    Returns:
        Evaluator UUID.
    """
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO evaluator (
            wallet_address, did, ens_name, evaluator_type, display_name,
            domain_expertise, specialization, organization, credentials,
            last_active_at, metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
        ON CONFLICT (wallet_address) WHERE wallet_address IS NOT NULL DO UPDATE SET
            evaluator_type = EXCLUDED.evaluator_type,
            display_name = COALESCE(EXCLUDED.display_name, evaluator.display_name),
            domain_expertise = COALESCE(EXCLUDED.domain_expertise, evaluator.domain_expertise),
            specialization = COALESCE(EXCLUDED.specialization, evaluator.specialization),
            organization = COALESCE(EXCLUDED.organization, evaluator.organization),
            credentials = COALESCE(EXCLUDED.credentials, evaluator.credentials),
            last_active_at = NOW(),
            updated_at = NOW()
        RETURNING id
    """, (
        wallet_address, did, ens_name, evaluator_type, display_name,
        domain_expertise, specialization, organization, credentials,
        json.dumps(metadata or {}),
    ))
    evaluator_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    # Log registration event
    _log_reputation_event(conn, evaluator_id, "evaluator_registered", reason=f"Registered as {evaluator_type}")

    logger.info("Registered evaluator: %s (type=%s)", display_name or wallet_address, evaluator_type)
    return evaluator_id


def _log_reputation_event(
    conn,
    evaluator_id: str,
    event_type: str,
    attestation_id: str = None,
    score_delta: float = None,
    reason: str = None,
) -> None:
    """Log a reputation event."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attester_reputation (evaluator_id, event_type, attestation_id, score_delta, reason)
        VALUES (%s, %s, %s, %s, %s)
    """, (evaluator_id, event_type, attestation_id, score_delta, reason))
    cur.close()


def compute_trust_score(conn, evaluator_id: str) -> float:
    """Compute weighted trust score for an evaluator.

    Formula:
        trust_score = (accuracy * 0.40) + (longevity * 0.30) +
                      (domain_expertise * 0.20) + (recency * 0.10)

    Returns:
        Trust score 0-1.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM evaluator WHERE id = %s", (evaluator_id,))
    evaluator = cur.fetchone()
    cur.close()

    if not evaluator:
        return 0.0

    total = evaluator["total_attestations"] or 0
    revoked = evaluator["revoked_attestations"] or 0
    domain_expertise = evaluator["domain_expertise"] or []
    last_active = evaluator["last_active_at"]

    # Accuracy: verified / total (higher = better)
    if total > 0:
        accuracy = (total - revoked) / total
    else:
        accuracy = 0.5  # Neutral when no data

    # Longevity: 1 - (revoked / total) (higher = fewer revocations = better)
    if total > 0:
        longevity = 1 - (revoked / total)
    else:
        longevity = 0.5

    # Domain expertise: attestations in domain / total (higher = more specialized)
    if total > 0 and domain_expertise:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT COUNT(*) AS domain_count FROM attestation_record ar
            JOIN evaluator e ON e.id = %s
            WHERE ar.claim_type = ANY(%s)
            AND ar.status = 'published'
        """, (evaluator_id, domain_expertise))
        row = cur.fetchone()
        cur.close()
        domain_count = row["domain_count"] if row else 0
        domain_score = min(1.0, domain_count / total)
    else:
        domain_score = 0.5

    # Recency: exponential decay based on days since last active
    if last_active:
        now = datetime.now(timezone.utc)
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        days_since = (now - last_active).total_seconds() / 86400
        recency = math.exp(-DECAY_RATE * days_since)
    else:
        recency = 0.1  # Very old if never active

    # Weighted combination
    trust_score = (
        accuracy * ACCURACY_WEIGHT +
        longevity * LONGEVITY_WEIGHT +
        domain_score * DOMAIN_WEIGHT +
        recency * RECENCY_WEIGHT
    )

    return round(max(0.0, min(1.0, trust_score)), 4)


def update_reputation(
    conn,
    evaluator_id: str,
    event_type: str,
    attestation_id: str = None,
    reason: str = None,
) -> Dict[str, Any]:
    """Update evaluator reputation based on an event.

    Recomputes trust score and logs the event.
    """
    # Get current score
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT trust_score, total_attestations, revoked_attestations FROM evaluator WHERE id = %s", (evaluator_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"status": "error", "message": "Evaluator not found"}

    old_score = float(row["trust_score"])

    # Update counters based on event type
    cur = conn.cursor()
    if event_type == "attestation_made":
        cur.execute("UPDATE evaluator SET total_attestations = total_attestations + 1, last_active_at = NOW(), updated_at = NOW() WHERE id = %s", (evaluator_id,))
    elif event_type == "attestation_revoked":
        cur.execute("UPDATE evaluator SET revoked_attestations = revoked_attestations + 1, updated_at = NOW() WHERE id = %s", (evaluator_id,))
    elif event_type in ("attestation_verified", "accuracy_confirmed"):
        cur.execute("UPDATE evaluator SET last_active_at = NOW(), updated_at = NOW() WHERE id = %s", (evaluator_id,))
    elif event_type == "evaluator_suspended":
        cur.execute("UPDATE evaluator SET status = 'suspended', updated_at = NOW() WHERE id = %s", (evaluator_id,))
    elif event_type == "evaluator_reactivated":
        cur.execute("UPDATE evaluator SET status = 'active', updated_at = NOW() WHERE id = %s", (evaluator_id,))
    conn.commit()
    cur.close()

    # Recompute trust score
    new_score = compute_trust_score(conn, evaluator_id)
    score_delta = new_score - old_score

    # Update score
    cur = conn.cursor()
    cur.execute("UPDATE evaluator SET trust_score = %s WHERE id = %s", (new_score, evaluator_id))
    conn.commit()
    cur.close()

    # Log event
    _log_reputation_event(conn, evaluator_id, event_type, attestation_id, score_delta, reason)

    return {
        "evaluator_id": evaluator_id,
        "event_type": event_type,
        "old_trust_score": round(old_score, 4),
        "new_trust_score": new_score,
        "score_delta": round(score_delta, 4),
    }


def get_evaluator_profile(conn, evaluator_id: str) -> Optional[Dict[str, Any]]:
    """Get full evaluator profile with reputation history."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM evaluator WHERE id = %s", (evaluator_id,))
    evaluator = cur.fetchone()
    cur.close()

    if not evaluator:
        return None

    result = dict(evaluator)

    # Get reputation history
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM attester_reputation
        WHERE evaluator_id = %s
        ORDER BY computed_at DESC
        LIMIT 50
    """, (evaluator_id,))
    result["reputation_history"] = [dict(r) for r in cur.fetchall()]
    cur.close()

    return result


def list_evaluators(
    conn,
    evaluator_type: str = None,
    domain: str = None,
    min_trust: float = None,
) -> List[Dict[str, Any]]:
    """List evaluators with optional filters."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = "SELECT * FROM evaluator WHERE status = 'active'"
    params = []

    if evaluator_type:
        query += " AND evaluator_type = %s"
        params.append(evaluator_type)
    if domain:
        query += " AND %s = ANY(domain_expertise)"
        params.append(domain)
    if min_trust is not None:
        query += " AND trust_score >= %s"
        params.append(min_trust)

    query += " ORDER BY trust_score DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def link_attestations(
    conn,
    source_attestation_id: str,
    target_attestation_id: str,
    reference_type: str,
    evaluator_id: str = None,
    strength: float = 1.0,
) -> str:
    """Create a cross-attestation reference link.

    Returns:
        Reference UUID.
    """
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attestation_reference
            (source_attestation_id, target_attestation_id, reference_type, evaluator_id, strength)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_attestation_id, target_attestation_id, reference_type) DO UPDATE SET
            strength = EXCLUDED.strength,
            evaluator_id = EXCLUDED.evaluator_id
        RETURNING id
    """, (source_attestation_id, target_attestation_id, reference_type, evaluator_id, strength))
    ref_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Linked attestations: %s --[%s]--> %s", source_attestation_id[:8], reference_type, target_attestation_id[:8])
    return ref_id


def get_attestation_references(conn, attestation_id: str) -> Dict[str, Any]:
    """Get all references for an attestation (outgoing and incoming)."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Outgoing references
    cur.execute("""
        SELECT ar.*, ar2.attestation_uid AS target_uid
        FROM attestation_reference ar
        JOIN attestation_record ar2 ON ar2.id = ar.target_attestation_id
        WHERE ar.source_attestation_id = %s
    """, (attestation_id,))
    outgoing = [dict(r) for r in cur.fetchall()]

    # Incoming references
    cur.execute("""
        SELECT ar.*, ar2.attestation_uid AS source_uid
        FROM attestation_reference ar
        JOIN attestation_record ar2 ON ar2.id = ar.source_attestation_id
        WHERE ar.target_attestation_id = %s
    """, (attestation_id,))
    incoming = [dict(r) for r in cur.fetchall()]

    cur.close()

    return {
        "attestation_id": attestation_id,
        "outgoing": outgoing,
        "incoming": incoming,
        "outgoing_count": len(outgoing),
        "incoming_count": len(incoming),
    }
