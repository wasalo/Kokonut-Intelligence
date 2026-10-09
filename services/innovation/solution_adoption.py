"""Solution adoption journeys, local configurations, and readiness."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_program(conn, solution_id: str, target_scope_type: str, target_scope_id: str, adoption_pathway: str, *, target_population: Optional[dict[str, Any]] = None, local_adaptation_policy: Optional[str] = None, champion_party_id: Optional[str] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_adoption_program
            (solution_id, target_scope_type, target_scope_id, target_population, adoption_pathway,
             local_adaptation_policy, champion_party_id, created_by_party_id)
            VALUES (%s::uuid, %s, %s::uuid, %s::jsonb, %s, %s, %s::uuid, %s::uuid) RETURNING *""", (solution_id, target_scope_type, target_scope_id, json.dumps(target_population or {}), adoption_pathway, local_adaptation_policy, champion_party_id, created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def assess_readiness(conn, solution_id: str, adopter_scope_type: str, adopter_scope_id: str, current_level: float, required_level: float, *, remediation_plan: Optional[str] = None, assessed_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    status = "ready" if current_level >= required_level else "remediating" if remediation_plan else "not_ready"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_adopter_readiness
            (solution_id, adopter_scope_type, adopter_scope_id, current_level, required_level,
             remediation_plan, readiness_status, assessed_by_party_id, assessed_at)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s::uuid, NOW())
            ON CONFLICT (solution_id, adopter_scope_type, adopter_scope_id) DO UPDATE SET
              current_level = EXCLUDED.current_level, required_level = EXCLUDED.required_level,
              remediation_plan = EXCLUDED.remediation_plan, readiness_status = EXCLUDED.readiness_status,
              assessed_by_party_id = EXCLUDED.assessed_by_party_id, assessed_at = NOW()
            RETURNING *""", (solution_id, adopter_scope_type, adopter_scope_id, current_level, required_level, remediation_plan, status, assessed_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def approve_configuration(conn, solution_id: str, scope_type: str, scope_id: str, invariant_components: dict[str, Any], configurable_components: dict[str, Any], *, prohibited_components: Optional[dict[str, Any]] = None, local_assumptions: Optional[dict[str, Any]] = None, adaptation_owner_party_id: Optional[str] = None, comparability_class: str = "comparable", evidence_impact: Optional[str] = None, approved_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM solution_configuration WHERE solution_id = %s::uuid AND scope_type = %s AND scope_id = %s::uuid", (solution_id, scope_type, scope_id))
        version = cur.fetchone()["version"]
        cur.execute("""INSERT INTO solution_configuration
            (solution_id, scope_type, scope_id, version, invariant_components, configurable_components,
             prohibited_components, local_assumptions, adaptation_owner_party_id, comparability_class,
             evidence_impact, approval_status, approved_by_party_id, approved_at)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::uuid, %s, %s, 'approved', %s::uuid, NOW()) RETURNING *""", (solution_id, scope_type, scope_id, version, json.dumps(invariant_components), json.dumps(configurable_components), json.dumps(prohibited_components or {}), json.dumps(local_assumptions or {}), adaptation_owner_party_id, comparability_class, evidence_impact, approved_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def record_event(conn, program_id: str, adopter_ref: str, event_type: str, *, cohort_id: Optional[str] = None, fidelity_score: Optional[float] = None, support_required: Optional[str] = None, outcome: Optional[dict[str, Any]] = None, consent_checked: bool = False, evidence: Optional[dict[str, Any]] = None, recorded_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    if event_type not in ("aware", "interested") and not consent_checked:
        raise ValueError("adoption events beyond interest require consent confirmation")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_adoption_event
            (program_id, cohort_id, adopter_ref, event_type, fidelity_score, support_required,
             outcome, consent_checked, evidence, recorded_by_party_id)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::uuid) RETURNING *""", (program_id, cohort_id, adopter_ref, event_type, fidelity_score, support_required, json.dumps(outcome or {}), consent_checked, json.dumps(evidence or {}), recorded_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row
