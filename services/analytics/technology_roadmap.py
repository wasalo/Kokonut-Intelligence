"""Governed technology and capability roadmap service.

Roadmaps connect enterprise needs to capabilities, technology drivers,
alternatives, and human review without replacing strategy or portfolio data.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db


def _conn():
    return get_db()


def _row(row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, (datetime, uuid_mod.UUID)):
            result[key] = value.isoformat() if isinstance(value, datetime) else str(value)
    return result


def create_roadmap(
    name: str,
    *,
    description: str = "",
    entity_type: str = "platform",
    entity_id: Optional[str] = None,
    planning_horizon_start: Optional[str] = None,
    planning_horizon_end: Optional[str] = None,
    detail_level: str = "portfolio",
    sponsor: Optional[str] = None,
    owner: Optional[str] = None,
    review_cadence_days: Optional[int] = 90,
    status: str = "draft",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    roadmap_id = str(uuid_mod.uuid4())
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO technology_roadmap "
            "(id, name, description, entity_type, entity_id, planning_horizon_start, "
            "planning_horizon_end, detail_level, sponsor, owner, review_cadence_days, status, metadata) "
            "VALUES (%s, %s, %s, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) RETURNING *",
            (roadmap_id, name, description, entity_type, entity_id,
             planning_horizon_start, planning_horizon_end, detail_level,
             sponsor, owner, review_cadence_days, status,
             json.dumps(metadata or {})),
        )
        conn.commit()
        return _row(cur.fetchone())


def get_roadmap(roadmap_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM technology_roadmap WHERE id = %s::uuid", (roadmap_id,))
        return _row(cur.fetchone())


def list_roadmaps(*, status: Optional[str] = None, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM v_technology_roadmap_overview" + where + " ORDER BY name",
            params,
        )
        return [_row(row) for row in cur.fetchall()]


def update_roadmap(roadmap_id: str, **fields) -> Optional[Dict[str, Any]]:
    allowed = {
        "name", "description", "planning_horizon_start", "planning_horizon_end",
        "detail_level", "sponsor", "owner", "review_cadence_days", "next_review_at",
        "status", "metadata",
    }
    sets: List[str] = []
    params: List[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "metadata":
            sets.append("metadata = %s::jsonb")
            params.append(json.dumps(value))
        else:
            sets.append(f"{key} = %s")
            params.append(value)
    if not sets:
        return get_roadmap(roadmap_id)
    params.append(roadmap_id)
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"UPDATE technology_roadmap SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *",
            params,
        )
        conn.commit()
        return _row(cur.fetchone())


def add_requirement(roadmap_id: str, title: str, **fields) -> Dict[str, Any]:
    requirement_id = str(uuid_mod.uuid4())
    allowed = {
        "description", "need_type", "priority", "target_value", "unit", "target_date",
        "strategy_map_id", "capability_id", "value_stream_id", "status", "evidence",
    }
    values = {key: value for key, value in fields.items() if key in allowed}
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO technology_roadmap_requirement "
            "(id, roadmap_id, title, description, need_type, priority, target_value, unit, target_date, "
            "strategy_map_id, capability_id, value_stream_id, status, evidence) "
            "VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb) RETURNING *",
            (requirement_id, roadmap_id, title, values.get("description"),
             values.get("need_type", "business"), values.get("priority", 3),
             values.get("target_value"), values.get("unit"), values.get("target_date"),
             values.get("strategy_map_id"), values.get("capability_id"), values.get("value_stream_id"),
             values.get("status", "proposed"), json.dumps(values.get("evidence", []))),
        )
        conn.commit()
        return _row(cur.fetchone())


def add_area(roadmap_id: str, name: str, *, description: str = "", sequence_order: int = 1) -> Dict[str, Any]:
    area_id = str(uuid_mod.uuid4())
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO technology_area (id, roadmap_id, name, description, sequence_order) "
            "VALUES (%s, %s::uuid, %s, %s, %s) "
            "ON CONFLICT (roadmap_id, name) DO UPDATE SET description = EXCLUDED.description, "
            "sequence_order = EXCLUDED.sequence_order RETURNING *",
            (area_id, roadmap_id, name, description, sequence_order),
        )
        conn.commit()
        return _row(cur.fetchone())


def add_driver(area_id: str, name: str, **fields) -> Dict[str, Any]:
    driver_id = str(uuid_mod.uuid4())
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO technology_driver (id, area_id, requirement_id, name, metric_key, target_value, unit, target_date, weight) "
            "VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (area_id, name) DO UPDATE SET requirement_id = EXCLUDED.requirement_id, "
            "metric_key = EXCLUDED.metric_key, target_value = EXCLUDED.target_value, unit = EXCLUDED.unit, "
            "target_date = EXCLUDED.target_date, weight = EXCLUDED.weight RETURNING *",
            (driver_id, area_id, fields.get("requirement_id"), name, fields.get("metric_key"),
             fields.get("target_value"), fields.get("unit"), fields.get("target_date"), fields.get("weight", 1.0)),
        )
        conn.commit()
        return _row(cur.fetchone())


def add_alternative(driver_id: str, name: str, **fields) -> Dict[str, Any]:
    alternative_id = str(uuid_mod.uuid4())
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO technology_alternative "
            "(id, driver_id, name, description, maturity_status, expected_maturity_date, estimated_cost, confidence, recommendation, decision_rationale, metadata) "
            "VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (driver_id, name) DO UPDATE SET description = EXCLUDED.description, "
            "maturity_status = EXCLUDED.maturity_status, expected_maturity_date = EXCLUDED.expected_maturity_date, "
            "estimated_cost = EXCLUDED.estimated_cost, confidence = EXCLUDED.confidence, recommendation = EXCLUDED.recommendation, "
            "decision_rationale = EXCLUDED.decision_rationale, metadata = EXCLUDED.metadata RETURNING *",
            (alternative_id, driver_id, name, fields.get("description"), fields.get("maturity_status", "candidate"),
             fields.get("expected_maturity_date"), fields.get("estimated_cost"), fields.get("confidence"),
             fields.get("recommendation", "candidate"), fields.get("decision_rationale"),
             json.dumps(fields.get("metadata", {}))),
        )
        conn.commit()
        return _row(cur.fetchone())


def review_roadmap(roadmap_id: str, result: str, *, reviewed_by: Optional[str] = None, notes: str = "", evidence: Optional[List] = None) -> Dict[str, Any]:
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO technology_roadmap_review (roadmap_id, reviewed_by, result, notes, evidence) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb) RETURNING *",
            (roadmap_id, reviewed_by, result, notes, json.dumps(evidence or [])),
        )
        review = _row(cur.fetchone())
        cur.execute(
            "UPDATE technology_roadmap SET status = CASE %s "
            "WHEN 'approved' THEN 'approved' WHEN 'superseded' THEN 'superseded' "
            "WHEN 'rejected' THEN 'rejected' ELSE 'submitted' END, "
            "next_review_at = CASE WHEN review_cadence_days IS NOT NULL "
            "THEN NOW() + (review_cadence_days || ' days')::interval ELSE next_review_at END "
            "WHERE id = %s::uuid",
            (result, roadmap_id),
        )
        conn.commit()
        return review


def get_roadmap_detail(roadmap_id: str) -> Optional[Dict[str, Any]]:
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM technology_roadmap_requirement WHERE roadmap_id = %s::uuid ORDER BY priority DESC, title", (roadmap_id,))
        requirements = [_row(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT ta.*, td.id AS driver_id, td.requirement_id, td.name AS driver_name, td.metric_key, td.target_value, td.unit, "
            "td.target_date, td.weight, alt.id AS alternative_id, alt.name AS alternative_name, alt.maturity_status, "
            "alt.expected_maturity_date, alt.estimated_cost, alt.confidence, alt.recommendation, alt.decision_rationale "
            "FROM technology_area ta LEFT JOIN technology_driver td ON td.area_id = ta.id "
            "LEFT JOIN technology_alternative alt ON alt.driver_id = td.id "
            "WHERE ta.roadmap_id = %s::uuid ORDER BY ta.sequence_order, ta.name, td.name, alt.name",
            (roadmap_id,),
        )
        rows = [_row(row) for row in cur.fetchall()]
    roadmap["requirements"] = requirements
    roadmap["technology_areas"] = rows
    return roadmap


def recommend_alternatives(roadmap_id: str) -> List[Dict[str, Any]]:
    detail = get_roadmap_detail(roadmap_id)
    if not detail:
        return []
    recommendations = []
    priority_by_requirement = {r["id"]: r.get("priority", 3) for r in detail["requirements"]}
    for row in detail["technology_areas"]:
        if not row.get("alternative_id"):
            continue
        maturity_score = {"production": 1.0, "pilot": 0.8, "available": 0.7, "emerging": 0.4, "deprecated": 0.0}.get(row["maturity_status"], 0.0)
        confidence = row.get("confidence") or 0.0
        priority = priority_by_requirement.get(row.get("requirement_id"), 3) if row.get("requirement_id") else 3
        score = round((priority / 5 * 0.35) + (float(row.get("weight") or 1) / 10 * 0.2) + (float(confidence) * 0.25) + (maturity_score * 0.2), 4)
        recommendations.append({"alternative_id": row["alternative_id"], "name": row["alternative_name"], "score": score, "recommendation": row["recommendation"], "driver": row["driver_name"], "maturity_status": row["maturity_status"]})
    return sorted(recommendations, key=lambda item: item["score"], reverse=True)
