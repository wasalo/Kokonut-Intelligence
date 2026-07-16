"""Connect sequential posterior decisions to review tasks and solution gates."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor

from services.decision.odds_engine import evaluate_action


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def evaluate_hypothesis(conn, hypothesis_id: str, *, action_threshold: float, continue_threshold: Optional[float] = None, action: str = "act", evaluated_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT p.*, h.subject_type, h.subject_id FROM decision_posterior_update p
            JOIN decision_hypothesis h ON h.id = p.hypothesis_id
            WHERE p.hypothesis_id = %s::uuid ORDER BY p.created_at DESC LIMIT 1""", (hypothesis_id,))
        posterior = cur.fetchone()
        if not posterior:
            conn.rollback()
            raise ValueError("hypothesis has no posterior update")
        decision = evaluate_action(float(posterior["posterior_probability"]), action_threshold=action_threshold, continue_threshold=continue_threshold, action=action)
        cur.execute("""INSERT INTO decision_threshold_evaluation
            (hypothesis_id, posterior_update_id, action, posterior_probability, action_threshold,
             continue_threshold, stopping_reason, calculation_version, evaluated_by_party_id)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, 'odds-v1', %s::uuid) RETURNING *""", (hypothesis_id, posterior["id"], decision["action"], decision["posterior_probability"], decision["action_threshold"], decision["continue_threshold"], decision["stopping_reason"], evaluated_by_party_id))
        evaluation = _clean(cur.fetchone())
        if decision["action"] in ("act", "escalate") and posterior["subject_type"] == "strategy_plan":
            cur.execute("""INSERT INTO strategy_review_task
                (strategy_plan_id, review_type, due_at, evidence)
                VALUES (%s::uuid, 'assumption_failure', NOW() + INTERVAL '7 days', %s::jsonb)
                RETURNING *""", (posterior["subject_id"], json.dumps({"source":"sequential_posterior", "hypothesis_id": hypothesis_id, "posterior_update_id": str(posterior["id"]), "posterior_probability": decision["posterior_probability"]})))
            evaluation["review_task"] = _clean(cur.fetchone())
        conn.commit()
        return evaluation


def evaluate_solution_gate_from_hypothesis(conn, gate_id: str, hypothesis_id: str, evaluated_by_party_id: str, *, minimum_posterior: float, evidence: list[Any]) -> Dict[str, Any]:
    if not evidence:
        raise ValueError("gate evaluation requires evidence")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT posterior_probability FROM decision_posterior_update WHERE hypothesis_id = %s::uuid ORDER BY created_at DESC LIMIT 1", (hypothesis_id,))
        posterior = cur.fetchone()
        if not posterior:
            conn.rollback()
            raise ValueError("hypothesis has no posterior update")
        passed = float(posterior["posterior_probability"]) >= minimum_posterior
    from services.innovation.solution_lifecycle import evaluate_gate
    return evaluate_gate(conn, gate_id, passed, evaluated_by_party_id, observed={"posterior_probability": float(posterior["posterior_probability"]), "minimum_posterior": minimum_posterior}, evidence=evidence)
