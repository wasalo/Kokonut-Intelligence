"""Hybrid DAO Voting — quadratic voting, reputation, delegation."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.hybrid_voting")


def cast_quadratic_vote(
    conn,
    proposal_id: str,
    voter_id: str,
    vote_weight: float,
    vote_choice: str,
    voting_method: str = "quadratic",
    token_amount: float = None,
) -> str:
    """Cast a quadratic vote with sqrt weighting."""
    sqrt_weight = math.sqrt(vote_weight)

    # Get voter reputation weight
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT COALESCE(SUM(reputation_amount), 0) AS total_rep
        FROM reputation_token WHERE voter_id = %s
    """, (voter_id,))
    rep = float(cur.fetchone()["total_rep"] or 0)
    reputation_weight = min(1.0, rep / 1000)  # Normalize to 0-1

    # Effective weight = sqrt_weight * reputation_weight
    effective_weight = sqrt_weight * reputation_weight

    cur2 = conn.cursor()
    cur2.execute("""
        INSERT INTO dao_vote (proposal_id, voter_id, vote_weight, sqrt_weight,
            vote_choice, voting_method, token_amount, reputation_weight)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (proposal_id, voter_id) DO UPDATE SET
            vote_weight = EXCLUDED.vote_weight,
            sqrt_weight = EXCLUDED.sqrt_weight,
            vote_choice = EXCLUDED.vote_choice
        RETURNING id
    """, (proposal_id, voter_id, vote_weight, sqrt_weight, vote_choice, voting_method, token_amount, reputation_weight))
    vote_id = str(cur2.fetchone()[0])

    # Update proposal totals
    cur2.execute("""
        UPDATE dao_proposal_extended SET
            total_votes_cast = (SELECT COUNT(*) FROM dao_vote WHERE proposal_id = %s),
            total_for = (SELECT COALESCE(SUM(sqrt_weight), 0) FROM dao_vote WHERE proposal_id = %s AND vote_choice = 'for'),
            total_against = (SELECT COALESCE(SUM(sqrt_weight), 0) FROM dao_vote WHERE proposal_id = %s AND vote_choice = 'against'),
            updated_at = NOW()
        WHERE proposal_key = %s
    """, (proposal_id, proposal_id, proposal_id, proposal_id))

    conn.commit()
    cur.close()

    logger.info("QV vote cast: proposal=%s, voter=%s, weight=%.2f, sqrt=%.4f, choice=%s",
                proposal_id, voter_id[:8], vote_weight, sqrt_weight, vote_choice)
    return vote_id


def compute_proposal_result(conn, proposal_id: str) -> Dict[str, Any]:
    """Compute proposal result with QV weighting."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM dao_proposal_extended WHERE proposal_key = %s", (proposal_id,))
    proposal = cur.fetchone()
    if not proposal:
        cur.close()
        return {"status": "error", "message": "Proposal not found"}

    proposal = dict(proposal)

    # Get all votes
    cur.execute("""
        SELECT dv.*, e.trust_score, e.display_name
        FROM dao_vote dv
        JOIN evaluator e ON e.id = dv.voter_id
        WHERE dv.proposal_id = %s
    """, (proposal_id,))
    votes = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Compute QV-weighted totals
    for_votes = sum(float(v.get("sqrt_weight", 0) or 0) for v in votes if v.get("vote_choice") == "for")
    against_votes = sum(float(v.get("sqrt_weight", 0) or 0) for v in votes if v.get("vote_choice") == "against")
    total_sqrt = sum(float(v.get("sqrt_weight", 0) or 0) for v in votes)

    # Check quorum
    quorum_pct = float(proposal.get("quorum_pct", 50) or 50)
    total_voters = len(votes)
    quorum_met = total_voters > 0  # Simplified: any votes = quorum met

    # Check passing threshold
    passing_pct = float(proposal.get("passing_threshold_pct", 50) or 50)
    if for_votes + against_votes > 0:
        for_pct = for_votes / (for_votes + against_votes) * 100
    else:
        for_pct = 0

    passed = quorum_met and for_pct >= passing_pct
    result = "passed" if passed else "rejected"

    return {
        "proposal_id": proposal_id,
        "voting_method": proposal.get("voting_method"),
        "total_votes": total_voters,
        "for_sqrt": round(for_votes, 4),
        "against_sqrt": round(against_votes, 4),
        "for_pct": round(for_pct, 1),
        "quorum_met": quorum_met,
        "passing_threshold": passing_pct,
        "result": result,
        "status": proposal.get("status"),
    }


def delegate_vote(
    conn,
    delegator_id: str,
    delegate_id: str,
    domain: str = "all",
    delegation_pct: float = 100.0,
) -> str:
    """Create vote delegation."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO delegation_record (delegator_id, delegate_id, domain, delegation_pct, status)
        VALUES (%s, %s, %s, %s, 'active')
        RETURNING id
    """, (delegator_id, delegate_id, domain, delegation_pct))
    delegation_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Delegation created: %s -> %s (domain=%s, %.0f%%)", delegator_id[:8], delegate_id[:8], domain, delegation_pct)
    return delegation_id


def earn_reputation(
    conn,
    voter_id: str,
    domain: str,
    amount: float,
    source: str = "validation",
    source_record_id: str = None,
) -> str:
    """Earn reputation in a domain."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reputation_token (voter_id, domain, reputation_amount, earned_from, source_record_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (voter_id, domain, source_record_id) DO UPDATE SET
            reputation_amount = reputation_token.reputation_amount + EXCLUDED.reputation_amount
        RETURNING id
    """, (voter_id, domain, amount, source, source_record_id))
    rep_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Reputation earned: %s earned %.1f in %s from %s", voter_id[:8], amount, domain, source)
    return rep_id


def get_reputation_score(conn, voter_id: str, domain: str = None) -> Dict[str, Any]:
    """Get reputation score for a voter."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if domain:
        cur.execute("""
            SELECT domain, SUM(reputation_amount) AS total
            FROM reputation_token WHERE voter_id = %s AND domain = %s
            GROUP BY domain
        """, (voter_id, domain))
    else:
        cur.execute("""
            SELECT domain, SUM(reputation_amount) AS total
            FROM reputation_token WHERE voter_id = %s
            GROUP BY domain
        """, (voter_id,))

    domains = {r["domain"]: float(r["total"]) for r in cur.fetchall()}
    total = sum(domains.values())

    cur.close()

    return {
        "voter_id": voter_id,
        "total_reputation": round(total, 4),
        "domain_reputation": domains,
    }
