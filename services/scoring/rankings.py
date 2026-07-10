"""Ranking algorithms and preference signal management.

Supports plurality of ranking algorithms and continuous
preference expression for the Impact Web of Trust.

Usage:
    python3 -m services.scoring --list-algorithms
    python3 -m services.scoring --compute-ranking --algorithm-id UUID --period 2026-Q2
    python3 -m services.scoring --compare-rankings --algorithm-ids UUID1 UUID2 --period 2026-Q2
    python3 -m services.scoring --submit-preference --evaluator-id UUID --type metric_preference --subject-id UUID --value 0.8
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("scoring.rankings")


def register_algorithm(
    conn,
    algorithm_key: str,
    algorithm_name: str,
    weighting_config: dict,
    description: str = None,
    author_evaluator_id: str = None,
    is_default: bool = False,
) -> str:
    """Register a new ranking algorithm.

    Args:
        weighting_config: Dict mapping dimension keys to weights (must sum to ~1.0).
            Example: {"ebf_environmental": 0.30, "ebf_economic": 0.25, ...}

    Returns:
        Algorithm UUID.
    """
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ranking_algorithm (algorithm_key, algorithm_name, description, weighting_config, author_evaluator_id, is_default)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (algorithm_key) DO UPDATE SET
            algorithm_name = EXCLUDED.algorithm_name,
            description = EXCLUDED.description,
            weighting_config = EXCLUDED.weighting_config,
            author_evaluator_id = EXCLUDED.author_evaluator_id,
            is_default = EXCLUDED.is_default
        RETURNING id
    """, (algorithm_key, algorithm_name, description, json.dumps(weighting_config), author_evaluator_id, is_default))
    algo_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Registered ranking algorithm: %s", algorithm_name)
    return algo_id


def list_algorithms(conn) -> List[Dict[str, Any]]:
    """List all active ranking algorithms."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM ranking_algorithm WHERE status = 'active' ORDER BY is_default DESC, algorithm_name
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def compute_ranking(conn, algorithm_id: str, period: str) -> Dict[str, Any]:
    """Compute ranking for all locations using an algorithm's weighting config.

    Scores are computed from the latest EBF scorecard data for each location,
    weighted by the algorithm's config.
    """
    # Get algorithm config
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM ranking_algorithm WHERE id = %s", (algorithm_id,))
    algo = cur.fetchone()
    cur.close()

    if not algo:
        return {"status": "error", "message": "Algorithm not found"}

    config = algo["weighting_config"]

    # Get latest EBF scorecard per location
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT ON (es.location_id)
            es.location_id,
            l.name AS location_name,
            es.overall_score,
            es.period_start,
            es.period_end
        FROM ebf_score es
        JOIN ebf_scorecard esc ON esc.id = es.scorecard_id
        JOIN location l ON l.id = es.location_id
        WHERE esc.status = 'published'
        ORDER BY es.location_id, esc.period_end DESC
    """)
    locations = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not locations:
        return {"status": "success", "rankings": [], "computed": 0}

    # Get per-dimension scores
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT ON (es.location_id, ep.pillar_key)
            es.location_id,
            ep.pillar_key,
            es.normalized_score
        FROM ebf_score es
        JOIN ebf_scorecard esc ON esc.id = es.scorecard_id
        JOIN ebf_pillar ep ON ep.id = es.pillar_id
        WHERE esc.status = 'published'
        ORDER BY es.location_id, ep.pillar_key, esc.period_end DESC
    """)
    dimension_scores = {}
    for row in cur.fetchall():
        loc_id = str(row["location_id"])
        pillar = row["pillar_key"]
        if loc_id not in dimension_scores:
            dimension_scores[loc_id] = {}
        dimension_scores[loc_id][pillar] = float(row["normalized_score"])
    cur.close()

    # Compute weighted scores
    results = []
    for loc in locations:
        loc_id = str(loc["location_id"])
        dims = dimension_scores.get(loc_id, {})

        weighted_score = 0.0
        total_weight = 0.0
        for dim_key, weight in config.items():
            if dim_key in dims:
                weighted_score += dims[dim_key] * weight
                total_weight += weight

        if total_weight > 0:
            normalized_score = weighted_score / total_weight
        else:
            normalized_score = 0.0

        results.append({
            "location_id": loc_id,
            "location_name": loc["location_name"],
            "score": round(normalized_score, 4),
            "dimension_scores": dims,
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    # Assign ranks
    for i, r in enumerate(results):
        r["rank"] = i + 1

    # Store results
    cur = conn.cursor()
    for r in results:
        cur.execute("""
            INSERT INTO ranking_result (algorithm_id, location_id, ranking_period, rank, score, dimension_scores)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (algorithm_id, location_id, ranking_period) DO UPDATE SET
                rank = EXCLUDED.rank,
                score = EXCLUDED.score,
                dimension_scores = EXCLUDED.dimension_scores,
                computed_at = NOW()
        """, (algorithm_id, r["location_id"], period, r["rank"], r["score"], json.dumps(r["dimension_scores"])))
    conn.commit()
    cur.close()

    return {
        "status": "success",
        "algorithm": algo["algorithm_name"],
        "period": period,
        "rankings": results,
        "computed": len(results),
    }


def compare_rankings(conn, algorithm_ids: List[str], period: str) -> Dict[str, Any]:
    """Compare rankings across multiple algorithms for the same period."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    results = {}
    for algo_id in algorithm_ids:
        cur.execute("""
            SELECT ra.algorithm_key, ra.algorithm_name, rr.rank, rr.score, l.name AS location_name, rr.location_id
            FROM ranking_result rr
            JOIN ranking_algorithm ra ON ra.id = rr.algorithm_id
            JOIN location l ON l.id = rr.location_id
            WHERE rr.algorithm_id = %s AND rr.ranking_period = %s
            ORDER BY rr.rank
        """, (algo_id, period))
        rows = [dict(r) for r in cur.fetchall()]
        if rows:
            algo_key = rows[0]["algorithm_key"]
            results[algo_key] = rows

    cur.close()

    # Build comparison matrix
    all_locations = set()
    for algo_key, rankings in results.items():
        for r in rankings:
            all_locations.add(r["location_id"])

    comparison = []
    for loc_id in all_locations:
        row = {"location_id": loc_id, "algorithms": {}}
        for algo_key, rankings in results.items():
            for r in rankings:
                if r["location_id"] == loc_id:
                    row["algorithms"][algo_key] = {
                        "rank": r["rank"],
                        "score": r["score"],
                    }
                    row["location_name"] = r["location_name"]
                    break
        comparison.append(row)

    return {
        "status": "success",
        "period": period,
        "algorithms_compared": len(results),
        "comparison": comparison,
    }


def submit_preference(
    conn,
    evaluator_id: str,
    signal_type: str,
    subject_type: str,
    subject_id: str,
    value: float = None,
    rank: int = None,
) -> str:
    """Submit a continuous preference signal.

    The evaluator's trust score is used as the weight for the preference.
    """
    # Get evaluator trust score for weighting
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT trust_score FROM evaluator WHERE id = %s", (evaluator_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        raise ValueError("Evaluator not found")

    weight = float(row["trust_score"])

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO preference_signal (evaluator_id, signal_type, subject_type, subject_id, preference_value, preference_rank, weight)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (evaluator_id, signal_type, subject_type, subject_id, value, rank, weight))
    pref_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Preference submitted by %s: %s -> %s = %s", evaluator_id[:8], signal_type, subject_type, value)
    return pref_id


def aggregate_preferences(
    conn,
    signal_type: str,
    subject_type: str = None,
    subject_id: str = None,
) -> List[Dict[str, Any]]:
    """Aggregate preferences with decay and reputation weighting.

    Applies exponential decay based on signal age and weights by
    evaluator trust score.
    """
    now = datetime.now(timezone.utc)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT
            ps.subject_id,
            ps.subject_type,
            ps.preference_value,
            ps.preference_rank,
            ps.weight AS evaluator_weight,
            ps.decay_rate,
            ps.created_at,
            e.trust_score,
            e.evaluator_type
        FROM preference_signal ps
        JOIN evaluator e ON e.id = ps.evaluator_id
        WHERE ps.signal_type = %s
        AND e.status = 'active'
    """
    params = [signal_type]

    if subject_type:
        query += " AND ps.subject_type = %s"
        params.append(subject_type)
    if subject_id:
        query += " AND ps.subject_id = %s"
        params.append(subject_id)

    query += " ORDER BY ps.created_at DESC"
    cur.execute(query, params)
    signals = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Aggregate by subject
    aggregated = {}
    for sig in signals:
        subject_key = str(sig["subject_id"])

        # Apply decay
        created = sig["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_old = (now - created).total_seconds() / 86400
        decay = math.exp(-sig["decay_rate"] * days_old)

        # Weight by evaluator trust score
        evaluator_weight = float(sig["trust_score"])
        effective_weight = decay * evaluator_weight

        if subject_key not in aggregated:
            aggregated[subject_key] = {
                "subject_id": subject_key,
                "subject_type": sig["subject_type"],
                "weighted_sum": 0.0,
                "total_weight": 0.0,
                "signal_count": 0,
                "latest_signal": str(sig["created_at"]),
            }

        if sig["preference_value"] is not None:
            aggregated[subject_key]["weighted_sum"] += float(sig["preference_value"]) * effective_weight
        aggregated[subject_key]["total_weight"] += effective_weight
        aggregated[subject_key]["signal_count"] += 1

    # Compute final aggregated values
    results = []
    for subject_key, data in aggregated.items():
        if data["total_weight"] > 0:
            data["aggregated_value"] = round(data["weighted_sum"] / data["total_weight"], 4)
        else:
            data["aggregated_value"] = 0.0
        del data["weighted_sum"]
        del data["total_weight"]
        results.append(data)

    results.sort(key=lambda x: x["aggregated_value"], reverse=True)
    return results


def get_preference_influence(conn, evaluator_id: str) -> Dict[str, Any]:
    """Show how an evaluator's preferences influence rankings."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get evaluator info
    cur.execute("SELECT evaluator_type, trust_score, total_attestations FROM evaluator WHERE id = %s", (evaluator_id,))
    evaluator = cur.fetchone()
    cur.close()

    if not evaluator:
        return {"status": "error", "message": "Evaluator not found"}

    # Count preferences
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT signal_type, COUNT(*) AS count, AVG(preference_value) AS avg_value
        FROM preference_signal WHERE evaluator_id = %s
        GROUP BY signal_type
    """, (evaluator_id,))
    preferences = [dict(r) for r in cur.fetchall()]
    cur.close()

    return {
        "evaluator_id": evaluator_id,
        "evaluator_type": evaluator["evaluator_type"],
        "trust_score": float(evaluator["trust_score"]),
        "total_attestations": evaluator["total_attestations"],
        "preferences": preferences,
        "influence_score": round(float(evaluator["trust_score"]) * len(preferences) * 0.1, 4),
    }
