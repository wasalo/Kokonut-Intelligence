"""Competitive landscape and Five Forces evidence."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_landscape(conn, strategy_plan_id: str, scope_type: str, scope_id: str, period_start: str, period_end: str, *, industry: Optional[str] = None, geography: Optional[str] = None, summary: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if scope_type not in ("organization", "location"):
        raise ValueError("scope_type must be organization or location")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO competitive_landscape
            (strategy_plan_id, scope_type, scope_id, industry, geography, period_start, period_end, summary, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s::uuid) RETURNING *""", (strategy_plan_id, scope_type, scope_id, industry, geography, period_start, period_end, summary, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def add_actor(conn, landscape_id: str, party_id: str, actor_type: str, *, strategic_group: Optional[str] = None, position_summary: Optional[str] = None, threat_level: Optional[str] = None, evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO competitive_actor
            (landscape_id, party_id, actor_type, strategic_group, position_summary, threat_level, evidence)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (landscape_id, party_id, actor_type) DO UPDATE SET
              strategic_group = EXCLUDED.strategic_group, position_summary = EXCLUDED.position_summary,
              threat_level = EXCLUDED.threat_level, evidence = EXCLUDED.evidence
            RETURNING *""", (landscape_id, party_id, actor_type, strategic_group, position_summary, threat_level, json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def record_force(conn, landscape_id: str, force_type: str, pressure_score: float, rationale: str, *, trend: str = "stable", confidence: str = "moderate", evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO competitive_force_observation
            (landscape_id, force_type, pressure_score, trend, rationale, evidence, confidence)
            VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s) RETURNING *""", (landscape_id, force_type, pressure_score, trend, rationale, json.dumps(evidence or []), confidence))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def record_signal(conn, landscape_id: str, signal_type: str, source_system: str, content: str, *, source_ref: Optional[str] = None, impact_direction: str = "uncertain", materiality: str = "medium", confidence: str = "moderate", evidence: Optional[List[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO competitive_signal
            (landscape_id, signal_type, source_system, source_ref, content, impact_direction, materiality, confidence, evidence)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) RETURNING *""", (landscape_id, signal_type, source_system, source_ref, content, impact_direction, materiality, confidence, json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def get_landscape(conn, landscape_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM competitive_landscape WHERE id = %s::uuid", (landscape_id,))
        landscape = cur.fetchone()
        if not landscape:
            raise ValueError("competitive landscape not found")
        cur.execute("SELECT ca.*, p.display_name FROM competitive_actor ca JOIN party p ON p.id = ca.party_id WHERE ca.landscape_id = %s::uuid ORDER BY ca.actor_type, p.display_name", (landscape_id,))
        actors = [_clean(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM competitive_force_observation WHERE landscape_id = %s::uuid ORDER BY observed_at DESC", (landscape_id,))
        forces = [_clean(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM competitive_signal WHERE landscape_id = %s::uuid ORDER BY observed_at DESC", (landscape_id,))
        signals = [_clean(row) for row in cur.fetchall()]
        return {"landscape": _clean(landscape), "actors": actors, "forces": forces, "signals": signals}
