"""Composite strategic investment scoring and allocation decisions."""

from __future__ import annotations

import json
import itertools
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


SCORE_FIELDS = ("financial_score", "ecological_score", "social_score", "governance_score", "resilience_score", "strategic_fit_score")
WEIGHT_FIELDS = tuple(field.replace("_score", "_weight") for field in SCORE_FIELDS)


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_policy(conn, strategy_plan_id: str, **weights) -> Dict[str, Any]:
    values = {field: float(weights.get(field, default)) for field, default in zip(WEIGHT_FIELDS, (0.20, 0.20, 0.20, 0.15, 0.15, 0.10))}
    if abs(sum(values.values()) - 1.0) > 0.00001:
        raise ValueError("allocation weights must sum to 1")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_allocation_policy
            (strategy_plan_id, financial_weight, ecological_weight, social_weight, governance_weight, resilience_weight, strategic_fit_weight)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (strategy_plan_id) DO UPDATE SET
              financial_weight = EXCLUDED.financial_weight, ecological_weight = EXCLUDED.ecological_weight,
              social_weight = EXCLUDED.social_weight, governance_weight = EXCLUDED.governance_weight,
              resilience_weight = EXCLUDED.resilience_weight, strategic_fit_weight = EXCLUDED.strategic_fit_weight,
              updated_at = NOW() RETURNING *""", (strategy_plan_id, values["financial_weight"], values["ecological_weight"], values["social_weight"], values["governance_weight"], values["resilience_weight"], values["strategic_fit_weight"]))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def create_investment_case(conn, strategy_plan_id: str, name: str, *, objective_id: Optional[str] = None, initiative_id: Optional[str] = None, program_id: Optional[str] = None, project_id: Optional[str] = None, financial_plan_id: Optional[str] = None, budget_line_id: Optional[str] = None, location_id: Optional[str] = None, crisp_assessment_id: Optional[str] = None, risk_mitigation_id: Optional[str] = None, description: Optional[str] = None, expected_benefit: Optional[str] = None, estimated_cost: Optional[float] = None, minimum_viable_funding: Optional[float] = None, required_capacity_hours: Optional[float] = None, dependencies: Optional[List[Any]] = None, created_by_party_id: Optional[str] = None, **scores) -> Dict[str, Any]:
    params = [strategy_plan_id, objective_id, initiative_id, program_id, project_id, financial_plan_id, budget_line_id, location_id, crisp_assessment_id, risk_mitigation_id, name, description, expected_benefit, estimated_cost, minimum_viable_funding, required_capacity_hours]
    score_values = [scores.get(field, 0) for field in SCORE_FIELDS] + [scores.get("risk_score", 0)]
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO strategy_investment_case
            (strategy_plan_id, objective_id, initiative_id, program_id, project_id, financial_plan_id, budget_line_id,
             location_id, crisp_assessment_id, risk_mitigation_id,
             name, description, expected_benefit, estimated_cost, minimum_viable_funding, required_capacity_hours,
             financial_score, ecological_score, social_score, governance_score, resilience_score, strategic_fit_score, risk_score,
             dependencies, created_by_party_id)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::uuid) RETURNING *""", params + score_values + [json.dumps(dependencies or []), created_by_party_id])
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def refresh_risk_evidence(conn, investment_id: str) -> Dict[str, Any]:
    if conn is None:
        raise ValueError("investment case connection is required")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT sic.location_id, sic.crisp_assessment_id, sic.risk_mitigation_id,
            cra.composite_score, cra.methodology_version, cra.confidence_level, cra.status AS crisp_status,
            rmr.status AS mitigation_status
            FROM strategy_investment_case sic
            LEFT JOIN crisp_risk_assessment cra ON cra.id = sic.crisp_assessment_id
            LEFT JOIN risk_mitigation_register rmr ON rmr.id = sic.risk_mitigation_id
            WHERE sic.id = %s::uuid FOR UPDATE""", (investment_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("investment case not found")
        if not row["crisp_assessment_id"]:
            cur.execute("UPDATE strategy_investment_case SET risk_evidence_status = 'missing', updated_at = NOW() WHERE id = %s::uuid RETURNING *", (investment_id,))
        else:
            status = "verified" if row["crisp_status"] in ("verified", "published") and row["mitigation_status"] in ("verified", "published") else "provisional"
            cur.execute("""UPDATE strategy_investment_case SET risk_score = %s,
                risk_as_of = NOW(), risk_methodology_version = %s, risk_confidence = %s,
                risk_evidence_status = %s, updated_at = NOW()
                WHERE id = %s::uuid RETURNING *""", (row["composite_score"], row["methodology_version"], row["confidence_level"], status, investment_id))
        result = dict(cur.fetchone())
        conn.commit()
        return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in result.items()}


def score_investment(conn, investment_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT sic.*, sap.* FROM strategy_investment_case sic
            JOIN strategy_allocation_policy sap ON sap.strategy_plan_id = sic.strategy_plan_id
            WHERE sic.id = %s::uuid FOR UPDATE""", (investment_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("investment or allocation policy not found")
        score = sum(float(row[field] or 0) * float(row[field.replace("_score", "_weight")]) for field in SCORE_FIELDS)
        score -= float(row["risk_score"] or 0) * float(row["risk_penalty_weight"])
        cur.execute("UPDATE strategy_investment_case SET composite_score = %s, status = 'scored', updated_at = NOW() WHERE id = %s::uuid RETURNING *", (round(score, 2), investment_id))
        result = _clean(cur.fetchone())
        conn.commit()
        return result


def recommend_investments(conn, strategy_plan_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE strategy_investment_case SET status = 'recommended', updated_at = NOW()
            WHERE strategy_plan_id = %s::uuid AND status = 'scored' AND composite_score IS NOT NULL""", (strategy_plan_id,))
        cur.execute("SELECT * FROM strategy_investment_case WHERE strategy_plan_id = %s::uuid ORDER BY composite_score DESC NULLS LAST", (strategy_plan_id,))
        rows = [_clean(row) for row in cur.fetchall()]
        conn.commit()
        return rows


def optimize_candidates(candidates: List[Dict[str, Any]], budget_limit: Optional[float] = None, capacity_limit: Optional[float] = None) -> Dict[str, Any]:
    """Select the highest-scoring feasible subset, including dependencies."""
    candidates = [dict(candidate) for candidate in candidates if candidate.get("status") in ("scored", "recommended", "approved")]
    by_id = {str(candidate["id"]): candidate for candidate in candidates}
    best = (0.0, (), 0.0, 0.0)
    for size in range(len(candidates) + 1):
        for subset in itertools.combinations(candidates, size):
            selected = {str(candidate["id"]) for candidate in subset}
            changed = True
            while changed:
                changed = False
                for candidate_id in list(selected):
                    for dependency in by_id.get(candidate_id, {}).get("dependencies", []) or []:
                        dependency = str(dependency)
                        if dependency not in by_id:
                            selected = set()
                            changed = False
                            break
                        if dependency not in selected:
                            selected.add(dependency)
                            changed = True
                    if not selected:
                        break
            if not selected:
                continue
            selected_rows = [by_id[candidate_id] for candidate_id in selected]
            cost = sum(float(row.get("estimated_cost") or row.get("minimum_viable_funding") or 0) for row in selected_rows)
            capacity = sum(float(row.get("required_capacity_hours") or 0) for row in selected_rows)
            score = sum(float(row.get("composite_score") or 0) for row in selected_rows)
            if budget_limit is not None and cost > budget_limit:
                continue
            if capacity_limit is not None and capacity > capacity_limit:
                continue
            if score > best[0]:
                best = (score, tuple(sorted(selected)), cost, capacity)
    selected_ids = list(best[1])
    all_ids = {str(candidate["id"]) for candidate in candidates}
    return {
        "selected_ids": selected_ids,
        "deferred_ids": sorted(all_ids - set(selected_ids)),
        "objective_score": round(best[0], 2),
        "used_budget": round(best[2], 2),
        "used_capacity_hours": round(best[3], 2),
    }


def select_feasible_portfolio(conn, strategy_plan_id: str, *, budget_limit: Optional[float] = None, capacity_limit_hours: Optional[float] = None, created_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM strategy_investment_case WHERE strategy_plan_id = %s::uuid AND status IN ('scored', 'recommended', 'approved')", (strategy_plan_id,))
        candidates = [dict(row) for row in cur.fetchall()]
        result = optimize_candidates(candidates, budget_limit, capacity_limit_hours)
        selected = set(result["selected_ids"])
        cur.execute("""INSERT INTO strategy_portfolio_selection
            (strategy_plan_id, budget_limit, capacity_limit_hours, selected_investment_ids,
             deferred_investment_ids, objective_score, used_budget, used_capacity_hours,
             constraint_explanations, created_by_party_id)
            VALUES (%s::uuid, %s, %s, %s::uuid[], %s::uuid[], %s, %s, %s, %s::jsonb, %s::uuid)
            RETURNING *""", (strategy_plan_id, budget_limit, capacity_limit_hours, result["selected_ids"], result["deferred_ids"], result["objective_score"], result["used_budget"], result["used_capacity_hours"], json.dumps([]), created_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row
