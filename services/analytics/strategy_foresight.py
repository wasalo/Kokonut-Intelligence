"""Unified foresight framing for strategy plans."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_frame(
    conn, strategy_plan_id: str, focal_question: str, decision_question: str,
    system_boundary: str, time_horizon_start: str, time_horizon_end: str, *,
    geographic_boundary: Optional[str] = None, stakeholder_boundary: Optional[str] = None,
    method: str = "integrated_scan_scenario_review", baseline_summary: Optional[str] = None,
    known_blind_spots: Optional[str] = None, owner_party_id: Optional[str] = None,
    created_by_party_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not focal_question.strip() or not decision_question.strip() or not system_boundary.strip():
        raise ValueError("foresight frame requires focal question, decision question, and system boundary")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_foresight_frame
            (strategy_plan_id, focal_question, decision_question, system_boundary,
             geographic_boundary, stakeholder_boundary, time_horizon_start, time_horizon_end,
             method, baseline_summary, known_blind_spots, owner_party_id, created_by_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s::uuid)
            RETURNING *""", (strategy_plan_id, focal_question, decision_question, system_boundary,
                              geographic_boundary, stakeholder_boundary, time_horizon_start,
                              time_horizon_end, method, baseline_summary, known_blind_spots,
                              owner_party_id, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def submit_frame(conn, frame_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE strategy_foresight_frame SET status = 'submitted', updated_at = NOW() WHERE id = %s::uuid AND status = 'draft' RETURNING *", (frame_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only draft foresight frames can be submitted")
        conn.commit()
        return _clean(row)


def add_driver(conn, frame_id: str, driver_type: str, title: str, description: str, *, time_to_impact: Optional[str] = None, impact_level: Optional[str] = None, confidence: str = "moderate", reversibility: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_foresight_driver
            (frame_id, driver_type, title, description, time_to_impact, impact_level, confidence, reversibility)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s) RETURNING *""", (frame_id, driver_type, title, description, time_to_impact, impact_level, confidence, reversibility))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def link_input(conn, frame_id: str, source_type: str, input_role: str, *, source_id: Optional[str] = None, source_ref: Optional[str] = None, interpretation: Optional[str] = None, confidence: str = "moderate", created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if not source_id and not source_ref:
        raise ValueError("foresight input requires source_id or source_ref")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_foresight_input
            (frame_id, source_type, source_id, source_ref, input_role, interpretation, confidence, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s::uuid)
            ON CONFLICT DO NOTHING RETURNING *""", (frame_id, source_type, source_id, source_ref, input_role, interpretation, confidence, created_by_party_id))
        row = cur.fetchone()
        if not row:
            cur.execute("""SELECT * FROM strategy_foresight_input
                WHERE frame_id = %s::uuid AND source_type = %s AND input_role = %s
                  AND source_id IS NOT DISTINCT FROM %s::uuid
                  AND source_ref IS NOT DISTINCT FROM %s""", (frame_id, source_type, input_role, source_id, source_ref))
            row = cur.fetchone()
        conn.commit()
        return _clean(row)


def get_frame(conn, strategy_plan_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_foresight_frame WHERE strategy_plan_id = %s::uuid", (strategy_plan_id,))
        frame = cur.fetchone()
        if not frame:
            return None
        result = _clean(frame)
        cur.execute("SELECT * FROM strategy_foresight_driver WHERE frame_id = %s::uuid ORDER BY created_at", (frame["id"],))
        result["drivers"] = [_clean(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM strategy_foresight_input WHERE frame_id = %s::uuid ORDER BY created_at", (frame["id"],))
        result["inputs"] = [_clean(row) for row in cur.fetchall()]
        return result
