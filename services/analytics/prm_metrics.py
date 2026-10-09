"""PRM Performance Reference Model metrics service layer.

Provides customer satisfaction tracking and total cost of ownership
computation for the tables and views introduced in migration 196.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db


def _conn():
    return get_db()


def _row_to_dict(row: psycopg2.extras.RealDictRow) -> Dict[str, Any]:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, uuid_mod.UUID):
            d[k] = str(v)
    return d


# --- Customer Satisfaction ---------------------------------------------------

def record_satisfaction(
    *,
    entity_type: str,
    entity_id: str,
    score: int,
    respondent_id: Optional[str] = None,
    nps: Optional[int] = None,
    feedback: Optional[str] = None,
    dimension: str = "overall",
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a customer satisfaction response.

    Validates score 1-5 and NPS -10 to 10.
    """
    if not 1 <= score <= 5:
        raise ValueError("score must be between 1 and 5")
    if nps is not None and not -10 <= nps <= 10:
        raise ValueError("nps must be between -10 and 10")

    sql = """
        INSERT INTO customer_satisfaction
            (entity_type, entity_id, respondent_id, score, nps,
             feedback, dimension, location_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (
                    entity_type,
                    entity_id,
                    respondent_id,
                    score,
                    nps,
                    feedback,
                    dimension,
                    location_id,
                ))
                conn.commit()
                return _row_to_dict(cur.fetchone())
    except Exception:
        return {}


def list_satisfaction(
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    location_id: Optional[str] = None,
    dimension: Optional[str] = None,
    days: int = 90,
) -> List[Dict[str, Any]]:
    """List customer satisfaction records with optional filters."""
    clauses: List[str] = ["recorded_at >= NOW() - make_interval(days => %s)"]
    params: List[Any] = [days]

    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = %s")
        params.append(uuid_mod.UUID(entity_id))
    if location_id:
        clauses.append("location_id = %s")
        params.append(uuid_mod.UUID(location_id))
    if dimension:
        clauses.append("dimension = %s")
        params.append(dimension)

    where = " AND ".join(clauses)
    sql = f"SELECT * FROM customer_satisfaction WHERE {where} ORDER BY recorded_at DESC"

    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def satisfaction_summary(
    *,
    entity_type: Optional[str] = None,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return aggregate satisfaction metrics.

    Includes average score, NPS, response count, and distribution by dimension.
    """
    clauses: List[str] = []
    params: List[Any] = []

    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if location_id:
        clauses.append("location_id = %s")
        params.append(uuid_mod.UUID(location_id))

    where = " AND ".join(clauses) if clauses else "TRUE"

    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Overall aggregates
                agg_sql = f"""
                    SELECT
                        COUNT(*) AS response_count,
                        ROUND(AVG(score), 2) AS avg_score,
                        ROUND(AVG(nps), 2) AS avg_nps,
                        SUM(CASE WHEN nps >= 9 THEN 1 ELSE 0 END) AS promoters,
                        SUM(CASE WHEN nps BETWEEN 7 AND 8 THEN 1 ELSE 0 END) AS passives,
                        SUM(CASE WHEN nps <= 6 THEN 1 ELSE 0 END) AS detractors
                    FROM customer_satisfaction
                    WHERE {where}
                """
                cur.execute(agg_sql, params)
                agg = _row_to_dict(cur.fetchone())

                # NPS = %promoters - %detractors
                rc = agg.get("response_count") or 0
                promoters = agg.get("promoters") or 0
                detractors = agg.get("detractors") or 0
                if rc > 0:
                    agg["nps_score"] = round(((promoters - detractors) / rc) * 100, 1)
                else:
                    agg["nps_score"] = 0.0

                # Distribution by dimension
                dist_sql = f"""
                    SELECT dimension, COUNT(*) AS count, ROUND(AVG(score), 2) AS avg_score
                    FROM customer_satisfaction
                    WHERE {where}
                    GROUP BY dimension
                    ORDER BY dimension
                """
                cur.execute(dist_sql, params)
                agg["by_dimension"] = [_row_to_dict(r) for r in cur.fetchall()]

                return agg
    except Exception:
        return {}


# --- Total Cost of Ownership ------------------------------------------------

def total_cost_of_ownership(
    *,
    location_id: Optional[str] = None,
    process_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query the v_total_cost_of_ownership view with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []

    if location_id:
        clauses.append("location_id = %s")
        params.append(uuid_mod.UUID(location_id))
    if process_key:
        clauses.append("process_key = %s")
        params.append(process_key)

    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"""
        SELECT * FROM v_total_cost_of_ownership
        WHERE {where}
        ORDER BY total_cost DESC
    """

    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def process_cost_breakdown(
    process_key: str,
    *,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return detailed cost breakdown for a specific process.

    Includes total cost, instance count, cost per instance, and cost by type.
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Total and per-instance
                clauses: List[str] = ["pco.process_key = %s"]
                params: List[Any] = [process_key]
                if location_id:
                    clauses.append("pco.location_id = %s")
                    params.append(uuid_mod.UUID(location_id))
                where = " AND ".join(clauses)

                total_sql = f"""
                    SELECT
                        COUNT(DISTINCT pco.entity_id) AS instance_count,
                        COALESCE(SUM(pco.cost_amount), 0) AS total_cost,
                        CASE WHEN COUNT(DISTINCT pco.entity_id) > 0
                             THEN SUM(pco.cost_amount) / COUNT(DISTINCT pco.entity_id)
                             ELSE 0 END AS cost_per_instance,
                        pco.currency
                    FROM process_cost_observation pco
                    WHERE {where}
                    GROUP BY pco.currency
                """
                cur.execute(total_sql, params)
                totals = [_row_to_dict(r) for r in cur.fetchall()]

                # By cost_type
                type_sql = f"""
                    SELECT
                        pco.cost_type,
                        COALESCE(SUM(pco.cost_amount), 0) AS type_cost,
                        COUNT(DISTINCT pco.entity_id) AS instance_count
                    FROM process_cost_observation pco
                    WHERE {where}
                    GROUP BY pco.cost_type
                    ORDER BY type_cost DESC
                """
                cur.execute(type_sql, params)
                by_type = [_row_to_dict(r) for r in cur.fetchall()]

                return {
                    "process_key": process_key,
                    "totals": totals,
                    "by_type": by_type,
                }
    except Exception:
        return {}


def cost_efficiency_ranking(
    *,
    location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Rank processes by cost efficiency (cost per instance, ascending)."""
    clauses: List[str] = []
    params: List[Any] = []

    if location_id:
        clauses.append("location_id = %s")
        params.append(uuid_mod.UUID(location_id))

    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"""
        SELECT
            process_key,
            process_name,
            process_type,
            instance_count,
            total_cost,
            cost_per_instance,
            currency
        FROM v_total_cost_of_ownership
        WHERE {where} AND cost_per_instance > 0
        ORDER BY cost_per_instance ASC
    """

    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


# --- Outcome Correlation ----------------------------------------------------

def outcome_correlation() -> List[Dict[str, Any]]:
    """Query the v_process_outcome_correlation view."""
    sql = "SELECT * FROM v_process_outcome_correlation ORDER BY process_key, maturity_level"

    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


# --- Improvement ROI --------------------------------------------------------

def improvement_roi(improvement_id: str) -> Dict[str, Any]:
    """Compute ROI for a process improvement initiative.

    Compares pre/post cost observations for the process around the
    improvement completion date.
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get improvement record
                cur.execute(
                    "SELECT * FROM process_improvement WHERE id = %s",
                    (uuid_mod.UUID(improvement_id),),
                )
                improvement = cur.fetchone()
                if not improvement:
                    return {"error": "improvement not found"}

                imp = _row_to_dict(improvement)
                process_key = imp["process_key"]
                completed_at = imp.get("completed_at")

                # Pre-cost: sum of costs before improvement completion
                # Post-cost: sum of costs after improvement completion
                if completed_at:
                    pre_sql = """
                        SELECT COALESCE(SUM(cost_amount), 0) AS pre_cost
                        FROM process_cost_observation
                        WHERE process_key = %s AND recorded_at < %s
                    """
                    post_sql = """
                        SELECT COALESCE(SUM(cost_amount), 0) AS post_cost
                        FROM process_cost_observation
                        WHERE process_key = %s AND recorded_at >= %s
                    """
                    cur.execute(pre_sql, (process_key, completed_at))
                    pre_cost = cur.fetchone()["pre_cost"]

                    cur.execute(post_sql, (process_key, completed_at))
                    post_cost = cur.fetchone()["post_cost"]
                else:
                    # No completion date yet — use all observations
                    cur.execute(
                        "SELECT COALESCE(SUM(cost_amount), 0) AS pre_cost FROM process_cost_observation WHERE process_key = %s",
                        (process_key,),
                    )
                    pre_cost = cur.fetchone()["pre_cost"]
                    post_cost = 0

                savings = float(pre_cost) - float(post_cost)
                savings_pct = (
                    round((savings / float(pre_cost)) * 100, 2)
                    if float(pre_cost) > 0
                    else 0.0
                )

                imp["pre_cost"] = float(pre_cost)
                imp["post_cost"] = float(post_cost)
                imp["savings"] = savings
                imp["savings_pct"] = savings_pct
                return imp
    except Exception:
        return {}
