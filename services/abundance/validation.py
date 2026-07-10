"""Abundance Protocol: 3-Tier Validation.

Manages validator selection (commit-reveal), review collection,
quadratic voting, and compensation.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.validation")


def _generate_commit_hash(data: str, salt: str = None) -> str:
    """Generate commit hash for commit-reveal scheme."""
    if not salt:
        salt = secrets.token_hex(32)
    return hashlib.sha256(f"{data}:{salt}".encode()).hexdigest()


def select_validators(
    conn,
    estimate_id: str,
    tier: int,
    required_expertise: float,
    slot_count: int = 5,
) -> str:
    """Select validators for a validation round using commit-reveal.

    Returns validation_round_id.
    """
    # Get category expertise requirements for the estimate
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT eca.category_id, eca.relative_impact_score, ec.category_name
        FROM estimate_category_assignment eca
        JOIN expertise_category ec ON ec.id = eca.category_id
        WHERE eca.estimate_id = %s
    """, (estimate_id,))
    categories = [dict(r) for r in cur.fetchall()]

    # Get eligible evaluators with relevant expertise
    cur.execute("""
        SELECT e.id, e.display_name, e.trust_score, e.evaluator_type
        FROM evaluator e
        WHERE e.status = 'active'
        AND e.trust_score > 0.1
        ORDER BY e.trust_score DESC
    """)
    eligible = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not eligible:
        logger.warning("No eligible evaluators for estimate %s", estimate_id[:8])
        return None

    # Simple random selection (commit-reveal will be handled separately)
    import random
    selected_count = min(slot_count, len(eligible))
    selected = random.sample(eligible, selected_count)

    # Create validation round
    now = datetime.now(timezone.utc)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO validation_round
            (estimate_id, tier, required_expertise, start_time, review_deadline, status)
        VALUES (%s, %s, %s, %s, %s, 'committing')
        RETURNING id
    """, (
        estimate_id, tier, required_expertise, now,
        now + timedelta(hours=48 if tier == 1 else 72),
    ))
    round_id = str(cur.fetchone()[0])

    # Select validators
    for i, evaluator in enumerate(selected):
        cur.execute("""
            INSERT INTO validator_selection
                (round_id, evaluator_id, tier, slot_number, expertise_score, status)
            VALUES (%s, %s, %s, %s, %s, 'selected')
        """, (round_id, str(evaluator["id"]), tier, i + 1, float(evaluator["trust_score"])))

    # Generate commit hash for the selection
    commit_data = json.dumps([str(e["id"]) for e in selected])
    commit_hash = _generate_commit_hash(commit_data)
    cur.execute("UPDATE validation_round SET commit_hash = %s WHERE id = %s", (commit_hash, round_id))

    conn.commit()
    cur.close()

    logger.info("Selected %d validators for round %s (tier %d)", selected_count, round_id[:8], tier)
    return round_id


def commit_selection(conn, round_id: str, validator_data: str) -> str:
    """Commit phase of commit-reveal: store hash of validator selections."""
    commit_hash = _generate_commit_hash(validator_data)
    cur = conn.cursor()
    cur.execute("""
        UPDATE validation_round SET commit_hash = %s, status = 'committed' WHERE id = %s
    """, (commit_hash, round_id))
    conn.commit()
    cur.close()
    return commit_hash


def reveal_selection(conn, round_id: str, validator_id: str, reveal_data: str) -> bool:
    """Reveal phase: validator reveals their participation commitment."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE validator_selection SET status = 'revealed'
        WHERE round_id = %s AND evaluator_id = %s AND status IN ('selected', 'committed')
    """, (round_id, validator_id))
    affected = cur.rowcount
    conn.commit()
    cur.close()
    return affected > 0


def cast_review(
    conn,
    validator_id: str,
    round_id: str,
    credibility_score: float,
    impact_score: float,
    sources: List[str] = None,
    confidence: str = "medium",
    category_scores: Dict[str, float] = None,
    review_text: str = None,
) -> str:
    """Submit a validator review."""
    # Get tier from round
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT tier FROM validation_round WHERE id = %s", (round_id,))
    row = cur.fetchone()
    tier = row["tier"] if row else 1

    cur.execute("""
        INSERT INTO validator_review
            (round_id, validator_id, tier, credibility_score, impact_score,
             category_scores, sources, confidence_level, review_text, status)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, 'submitted')
        RETURNING id
    """, (
        round_id, validator_id, tier, credibility_score, impact_score,
        json.dumps(category_scores or {}), sources or [], confidence, review_text,
    ))
    review_id = str(cur.fetchone()[0])

    # Update validator selection status
    cur.execute("""
        UPDATE validator_selection SET status = 'reviewed'
        WHERE round_id = %s AND evaluator_id = %s
    """, (round_id, validator_id))

    conn.commit()
    cur.close()

    logger.info("Review submitted by %s for round %s (credibility=%.2f, impact=%.1f)", validator_id[:8], round_id[:8], credibility_score, impact_score)
    return review_id


def cast_qv_vote(
    conn,
    voter_id: str,
    review_id: str,
    vote_weight: float,
    vote_type: str = "accuracy",
    justification: str = None,
) -> str:
    """Cast a quadratic vote with sqrt-weighting."""
    sqrt_weight = math.sqrt(vote_weight)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO quadratic_vote
            (round_id, voter_id, review_id, vote_weight, sqrt_weight,
             vote_type, justification, status)
        VALUES (
            (SELECT round_id FROM validator_review WHERE id = %s),
            %s, %s, %s, %s, %s, %s, 'cast'
        )
        RETURNING id
    """, (review_id, voter_id, review_id, vote_weight, sqrt_weight, vote_type, justification))
    vote_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("QV vote cast: weight=%.2f, sqrt=%.4f, type=%s", vote_weight, sqrt_weight, vote_type)
    return vote_id


def compute_round_results(conn, round_id: str) -> Dict[str, Any]:
    """Aggregate review results with quadratic voting weighting."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get all reviews for this round
    cur.execute("""
        SELECT vr.*, e.trust_score, e.display_name
        FROM validator_review vr
        JOIN evaluator e ON e.id = vr.validator_id
        WHERE vr.round_id = %s AND vr.status = 'submitted'
    """, (round_id,))
    reviews = [dict(r) for r in cur.fetchall()]

    if not reviews:
        cur.close()
        return {"round_id": round_id, "reviews": 0, "status": "no_reviews"}

    # Get QV votes
    cur.execute("""
        SELECT qv.review_id, SUM(qv.sqrt_weight) AS total_sqrt_weight, COUNT(*) AS vote_count
        FROM quadratic_vote qv
        WHERE qv.round_id = %s AND qv.status = 'cast'
        GROUP BY qv.review_id
    """, (round_id,))
    votes = {str(r["review_id"]): dict(r) for r in cur.fetchall()}

    # Weight each review by reviewer trust_score * sqrt(vote_weight)
    weighted_credibility = 0.0
    weighted_impact = 0.0
    total_weight = 0.0

    for review in reviews:
        review_id = str(review["id"])
        trust = float(review.get("trust_score", 0.5) or 0.5)
        vote_data = votes.get(review_id, {})
        sqrt_weight = float(vote_data.get("total_sqrt_weight", 1.0) or 1.0)

        weight = trust * sqrt_weight
        weighted_credibility += float(review.get("credibility_score", 0) or 0) * weight
        weighted_impact += float(review.get("impact_score", 0) or 0) * weight
        total_weight += weight

    if total_weight > 0:
        avg_credibility = weighted_credibility / total_weight
        avg_impact = weighted_impact / total_weight
    else:
        avg_credibility = 0
        avg_impact = 0

    cur.close()

    return {
        "round_id": round_id,
        "reviews": len(reviews),
        "total_weight": round(total_weight, 4),
        "weighted_credibility_score": round(avg_credibility, 4),
        "weighted_impact_score": round(avg_impact, 4),
        "reviews_detail": [
            {
                "validator": r["display_name"],
                "credibility": r.get("credibility_score"),
                "impact": r.get("impact_score"),
                "trust_score": r.get("trust_score"),
                "votes": votes.get(str(r["id"]), {}).get("vote_count", 0),
            }
            for r in reviews
        ],
    }


def assign_compensation(conn, round_id: str) -> List[Dict[str, Any]]:
    """Compensate validators from inflation based on accuracy."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get round results
    cur.execute("""
        SELECT vr.*, e.trust_score
        FROM validator_review vr
        JOIN evaluator e ON e.id = vr.validator_id
        WHERE vr.round_id = %s AND vr.status = 'submitted'
    """, (round_id,))
    reviews = [dict(r) for r in cur.fetchall()]

    # Get round details
    cur.execute("SELECT * FROM validation_round WHERE id = %s", (round_id,))
    round_info = dict(cur.fetchone() or {})
    tier = round_info.get("tier", 1)

    # Base compensation per tier
    tier_base = {1: 100.0, 2: 50.0, 3: 30.0}.get(tier, 30.0)

    results = []
    cur2 = conn.cursor()
    for review in reviews:
        trust = float(review.get("trust_score", 0.5) or 0.5)
        base = tier_base * trust
        # Accuracy bonus: higher trust = higher bonus
        accuracy_bonus = base * 0.1 * trust
        total = base + accuracy_bonus

        cur2.execute("""
            INSERT INTO validator_compensation
                (round_id, evaluator_id, tier, base_compensation, accuracy_bonus, total_compensation, expertise_earned, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'calculated')
            RETURNING id
        """, (round_id, str(review["validator_id"]), tier, base, accuracy_bonus, total, trust * 0.05))

        comp_id = str(cur2.fetchone()[0])
        results.append({
            "compensation_id": comp_id,
            "validator_id": str(review["validator_id"]),
            "base": round(base, 2),
            "accuracy_bonus": round(accuracy_bonus, 2),
            "total": round(total, 2),
        })

    conn.commit()
    cur.close()

    logger.info("Assigned compensation to %d validators for round %s", len(results), round_id[:8])
    return results
