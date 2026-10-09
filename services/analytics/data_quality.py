"""BRM Data Reference Model (DRM) service layer.

Provides data quality scoring and rule management for the data_quality_rule
and data_quality_score tables introduced in migration 195_service_catalog.sql.
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
        elif isinstance(v, dict):
            pass
    return d


# --- Rule CRUD ---------------------------------------------------------------

def list_rules(
    *,
    entity_type: Optional[str] = None,
    dimension: Optional[str] = None,
    active: bool = True,
) -> List[Dict[str, Any]]:
    """List data_quality_rule rows with optional filters."""
    clauses: List[str] = []
    params: List[Any] = []
    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if dimension:
        clauses.append("dimension = %s")
        params.append(dimension)
    if active:
        clauses.append("active = %s")
        params.append(active)
    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"SELECT * FROM data_quality_rule WHERE {where} ORDER BY entity_type, dimension"
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def create_rule(
    *,
    entity_type: str,
    dimension: str,
    rule_type: str,
    rule_config: Dict[str, Any],
    severity: str = "warning",
) -> Dict[str, Any]:
    """Create a new data quality rule."""
    sql = """
        INSERT INTO data_quality_rule (entity_type, dimension, rule_type, rule_config, severity)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (
                    entity_type, dimension, rule_type,
                    json.dumps(rule_config), severity,
                ))
                conn.commit()
                return _row_to_dict(cur.fetchone())
    except Exception:
        return {}


def deactivate_rule(rule_id: str) -> bool:
    """Set active = FALSE for a rule."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE data_quality_rule SET active = FALSE WHERE id = %s",
                    (rule_id,),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception:
        return False


# --- Scoring -----------------------------------------------------------------

def score_entity(
    *,
    entity_type: str,
    entity_id: str,
    rule_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute and store a data quality score for a specific entity.

    If *rule_results* is provided, compute from those; otherwise use a
    default scoring of 100 across all dimensions.

    Returns the inserted data_quality_score row as a dict.
    """
    if rule_results is None:
        rule_results = []

    dim_totals: Dict[str, Dict[str, float]] = {
        "completeness": {"passed": 0, "total": 0},
        "accuracy": {"passed": 0, "total": 0},
        "timeliness": {"passed": 0, "total": 0},
        "consistency": {"passed": 0, "total": 0},
    }

    for rr in rule_results:
        dim = rr.get("dimension", "completeness")
        if dim not in dim_totals:
            dim_totals[dim] = {"passed": 0, "total": 0}
        dim_totals[dim]["total"] += 1
        if rr.get("passed", False):
            dim_totals[dim]["passed"] += 1

    def _pct(d: str) -> float:
        t = dim_totals[d]
        if t["total"] == 0:
            return 100.0
        return round(t["passed"] / t["total"] * 100, 2)

    completeness_pct = _pct("completeness")
    accuracy_pct = _pct("accuracy")
    timeliness_pct = _pct("timeliness")
    consistency_pct = _pct("consistency")
    overall_score = round(
        (completeness_pct + accuracy_pct + timeliness_pct + consistency_pct) / 4, 2
    )

    sql = """
        INSERT INTO data_quality_score
            (entity_type, entity_id, completeness_pct, accuracy_pct,
             timeliness_pct, consistency_pct, overall_score, rule_results)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (
                    entity_type, entity_id,
                    completeness_pct, accuracy_pct,
                    timeliness_pct, consistency_pct,
                    overall_score, json.dumps(rule_results),
                ))
                conn.commit()
                return _row_to_dict(cur.fetchone())
    except Exception:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "completeness_pct": completeness_pct,
            "accuracy_pct": accuracy_pct,
            "timeliness_pct": timeliness_pct,
            "consistency_pct": consistency_pct,
            "overall_score": overall_score,
        }


def get_latest_score(entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent data quality score for an entity."""
    sql = """
        SELECT * FROM data_quality_score
        WHERE entity_type = %s AND entity_id = %s
        ORDER BY scored_at DESC
        LIMIT 1
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (entity_type, entity_id))
                r = cur.fetchone()
                return _row_to_dict(r) if r else None
    except Exception:
        return None


def entity_quality_summary(entity_type: str) -> Dict[str, Any]:
    """Return aggregate quality scores for an entity type.

    Includes average scores across dimensions, total entities scored,
    and distribution of overall scores (excellent >=90, good >=70,
    fair >=50, poor <50).
    """
    sql = """
        SELECT
            COUNT(DISTINCT entity_id) AS total_entities,
            COALESCE(AVG(completeness_pct), 0) AS avg_completeness,
            COALESCE(AVG(accuracy_pct), 0) AS avg_accuracy,
            COALESCE(AVG(timeliness_pct), 0) AS avg_timeliness,
            COALESCE(AVG(consistency_pct), 0) AS avg_consistency,
            COALESCE(AVG(overall_score), 0) AS avg_overall,
            COALESCE(SUM(CASE WHEN overall_score >= 90 THEN 1 ELSE 0 END), 0) AS excellent,
            COALESCE(SUM(CASE WHEN overall_score >= 70 AND overall_score < 90 THEN 1 ELSE 0 END), 0) AS good,
            COALESCE(SUM(CASE WHEN overall_score >= 50 AND overall_score < 70 THEN 1 ELSE 0 END), 0) AS fair,
            COALESCE(SUM(CASE WHEN overall_score < 50 THEN 1 ELSE 0 END), 0) AS poor
        FROM data_quality_score
        WHERE entity_type = %s
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (entity_type,))
                row = cur.fetchone()
                if not row:
                    return {
                        "entity_type": entity_type,
                        "total_entities": 0,
                        "avg_completeness": 0,
                        "avg_accuracy": 0,
                        "avg_timeliness": 0,
                        "avg_consistency": 0,
                        "avg_overall": 0,
                        "distribution": {"excellent": 0, "good": 0, "fair": 0, "poor": 0},
                    }
                d = dict(row)
                for k in ("avg_completeness", "avg_accuracy", "avg_timeliness",
                          "avg_consistency", "avg_overall"):
                    d[k] = round(float(d[k]), 2)
                d["distribution"] = {
                    "excellent": int(d.pop("excellent")),
                    "good": int(d.pop("good")),
                    "fair": int(d.pop("fair")),
                    "poor": int(d.pop("poor")),
                }
                d["total_entities"] = int(d["total_entities"])
                d["entity_type"] = entity_type
                return d
    except Exception:
        return {
            "entity_type": entity_type,
            "total_entities": 0,
            "avg_completeness": 0,
            "avg_accuracy": 0,
            "avg_timeliness": 0,
            "avg_consistency": 0,
            "avg_overall": 0,
            "distribution": {"excellent": 0, "good": 0, "fair": 0, "poor": 0},
        }


def quality_trend(
    entity_type: str,
    *,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Return daily average quality scores over the last N days."""
    sql = """
        SELECT
            DATE(scored_at) AS score_date,
            ROUND(AVG(completeness_pct), 2) AS avg_completeness,
            ROUND(AVG(accuracy_pct), 2) AS avg_accuracy,
            ROUND(AVG(timeliness_pct), 2) AS avg_timeliness,
            ROUND(AVG(consistency_pct), 2) AS avg_consistency,
            ROUND(AVG(overall_score), 2) AS avg_overall,
            COUNT(DISTINCT entity_id) AS entities_scored
        FROM data_quality_score
        WHERE entity_type = %s
          AND scored_at >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(scored_at)
        ORDER BY score_date
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (entity_type, days))
                return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


# --- Rule Evaluation Helpers -------------------------------------------------

def _table_exists(table_name: str) -> bool:
    """Check if a PostgreSQL table exists."""
    sql = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
    """
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (table_name,))
                return cur.fetchone()[0]
    except Exception:
        return False


def evaluate_not_null_rule(
    entity_type: str,
    field_name: str,
    *,
    sample_size: int = 100,
) -> Dict[str, Any]:
    """Evaluate a not_null completeness rule by querying the database.

    Maps common entity_type names to their corresponding table names.
    Returns the percentage of non-null values for the field in a sample
    of the most recent records.
    """
    entity_table_map = {
        "farm_activity": "farm_activity",
        "harvest_event": "harvest_event",
        "traceability_batch": "traceability_batch",
        "data_stream_post": "data_stream_post",
        "weather_observation": "weather_observation",
        "sensor_reading": "sensor_reading",
        "soil_sample": "soil_sample",
        "location": "location",
        "farm_zone": "farm_zone",
        "tree_inventory": "tree_inventory",
        "metric_value": "metric_value",
        "crop_cycle": "crop_cycle",
    }

    table_name = entity_table_map.get(entity_type, entity_type)

    if not _table_exists(table_name):
        return {
            "entity_type": entity_type,
            "field_name": field_name,
            "completeness_pct": 0.0,
            "total_rows": 0,
            "non_null_rows": 0,
            "error": f"table '{table_name}' not found",
        }

    sql = f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(CASE WHEN {field_name} IS NOT NULL THEN 1 END) AS non_null_rows
        FROM (
            SELECT {field_name}
            FROM {table_name}
            ORDER BY created_at DESC NULLS LAST
            LIMIT %s
        ) sub
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (sample_size,))
                row = cur.fetchone()
                if not row:
                    return {
                        "entity_type": entity_type,
                        "field_name": field_name,
                        "completeness_pct": 0.0,
                        "total_rows": 0,
                        "non_null_rows": 0,
                    }
                total = int(row["total_rows"])
                non_null = int(row["non_null_rows"])
                pct = round(non_null / total * 100, 2) if total > 0 else 0.0
                return {
                    "entity_type": entity_type,
                    "field_name": field_name,
                    "completeness_pct": pct,
                    "total_rows": total,
                    "non_null_rows": non_null,
                }
    except Exception:
        return {
            "entity_type": entity_type,
            "field_name": field_name,
            "completeness_pct": 0.0,
            "total_rows": 0,
            "non_null_rows": 0,
        }
