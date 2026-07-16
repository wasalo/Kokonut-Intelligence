"""Explainable coherence checks for versioned strategy plans."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def run_checks(conn, strategy_plan_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_plan WHERE id = %s::uuid", (strategy_plan_id,))
        plan = cur.fetchone()
        if not plan:
            raise ValueError("strategy plan not found")
        findings: List[Dict[str, Any]] = []

        def add(rule, entity_type, entity_id, severity, explanation, remediation, evidence=None):
            cur.execute("""INSERT INTO strategy_coherence_finding
                (strategy_plan_id, rule_key, entity_type, entity_id, severity, explanation, evidence, remediation)
                VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s, %s::jsonb, %s)
                ON CONFLICT (strategy_plan_id, rule_key, entity_type, entity_id) DO UPDATE SET
                  severity = EXCLUDED.severity, explanation = EXCLUDED.explanation,
                  evidence = EXCLUDED.evidence, remediation = EXCLUDED.remediation,
                  status = CASE WHEN strategy_coherence_finding.status IN ('resolved', 'waived') THEN 'open' ELSE strategy_coherence_finding.status END,
                  last_seen_at = NOW()
                RETURNING *""", (strategy_plan_id, rule, entity_type, entity_id, severity, explanation, json.dumps(evidence or {}), remediation))
            findings.append(_clean(cur.fetchone()))

        if not plan["diagnosis_summary"].strip():
            add("plan_requires_diagnosis", "strategy_plan", strategy_plan_id, "critical", "Strategy plan has no diagnosis of the challenge or opportunity.", "Record the evidence-backed strategic diagnosis.")
        if not plan["guiding_policy"].strip():
            add("plan_requires_guiding_policy", "strategy_plan", strategy_plan_id, "critical", "Strategy plan has no guiding policy.", "Record the policy that translates diagnosis into a coherent approach.")

        cur.execute("SELECT COUNT(*) AS count FROM strategy_choice WHERE strategy_plan_id = %s::uuid AND status = 'approved'", (strategy_plan_id,))
        if cur.fetchone()["count"] == 0:
            add("plan_requires_approved_choice", "strategy_plan", strategy_plan_id, "critical", "Strategy plan has no approved strategic choice.", "Approve at least one strategic choice.")
        cur.execute("SELECT COUNT(*) AS count FROM strategy_allocation_policy WHERE strategy_plan_id = %s::uuid", (strategy_plan_id,))
        if cur.fetchone()["count"] == 0:
            add("plan_requires_allocation_policy", "strategy_plan", strategy_plan_id, "high", "Strategy plan has no resource-allocation policy.", "Define composite allocation weights before approval.")
        if plan["status"] == "active":
            cur.execute("SELECT COUNT(*) AS count FROM strategy_position WHERE strategy_plan_id = %s::uuid AND status = 'approved'", (strategy_plan_id,))
            if cur.fetchone()["count"] == 0:
                add("active_plan_requires_external_position", "strategy_plan", strategy_plan_id, "high", "Active strategy plan has no approved external position.", "Document and approve the target position and value proposition.")

        cur.execute("SELECT * FROM strategy_map WHERE strategy_plan_id = %s::uuid", (strategy_plan_id,))
        entries = cur.fetchall()
        for entry in entries:
            if not entry["accountable_party_id"]:
                add("objective_requires_accountability", "strategy_map", entry["id"], "high", "Strategic objective has no accountable party.", "Assign a governed accountable party.")
            cur.execute("SELECT COUNT(*) AS count FROM objective_kpi WHERE objective_id = %s", (entry["objective_id"],))
            kpi_count = cur.fetchone()["count"] if entry["objective_id"] else 0
            if not kpi_count:
                add("objective_requires_kpi", "strategy_map", entry["id"], "high", "Strategic objective has no KPI binding.", "Bind a metric or CRISP dimension with a target.")

        cur.execute("""SELECT si.* FROM strategy_initiative si
            JOIN strategy_map sm ON sm.id = si.strategy_map_id
            WHERE sm.strategy_plan_id = %s::uuid""", (strategy_plan_id,))
        for initiative in cur.fetchall():
            if not initiative["owner"]:
                add("initiative_requires_owner", "strategy_initiative", initiative["id"], "medium", "Strategic initiative has no owner.", "Assign an accountable initiative owner.")
            if not initiative["target_date"]:
                add("initiative_requires_target_date", "strategy_initiative", initiative["id"], "medium", "Strategic initiative has no target date.", "Set a target date for execution review.")

        cur.execute("SELECT * FROM strategy_investment_case WHERE strategy_plan_id = %s::uuid", (strategy_plan_id,))
        for investment in cur.fetchall():
            if not investment["objective_id"] and not investment["initiative_id"]:
                add("investment_requires_strategy_link", "strategy_investment_case", investment["id"], "high", "Investment case is not linked to an objective or initiative.", "Link the investment to a strategic objective or initiative.")
            if investment["risk_evidence_status"] == "missing":
                add("investment_requires_risk_evidence", "strategy_investment_case", investment["id"], "high", "Investment case has no CRISP risk evidence.", "Link a CRISP assessment and mitigation record before allocation.")

        cur.execute("SELECT * FROM v_strategy_advantage_fit WHERE strategy_plan_id = %s::uuid", (strategy_plan_id,))
        for advantage in cur.fetchall():
            if advantage["fit_status"] == "unlinked":
                add("advantage_requires_operating_fit", "strategy_advantage", advantage["advantage_id"], "high", "Claimed advantage has no capability, value-chain, choice, or investment link.", "Link the advantage to the operating model and funding path.")
            elif advantage["fit_status"] == "partial":
                add("advantage_has_partial_operating_fit", "strategy_advantage", advantage["advantage_id"], "medium", "Claimed advantage has incomplete capability or investment support.", "Complete both capability and funded-investment links.")

        conn.commit()
        return findings


def list_findings(conn, strategy_plan_id: str, *, status: str = "open") -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_coherence_finding WHERE strategy_plan_id = %s::uuid AND status = %s ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END, first_seen_at", (strategy_plan_id, status))
        return [_clean(row) for row in cur.fetchall()]


def resolve_finding(conn, finding_id: str, resolved_by_party_id: str, status: str, note: str) -> Dict[str, Any]:
    if status not in ("resolved", "waived", "accepted"):
        raise ValueError("invalid finding resolution status")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_coherence_finding SET status = %s, resolved_by_party_id = %s::uuid,
            resolved_at = NOW(), resolution_note = %s WHERE id = %s::uuid RETURNING *""", (status, resolved_by_party_id, note, finding_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("coherence finding not found")
        conn.commit()
        return _clean(row)
