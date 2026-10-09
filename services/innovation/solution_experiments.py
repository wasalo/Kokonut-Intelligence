"""Governed solution experiments and replication records."""

from __future__ import annotations

import json
import math
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_experiment(conn, solution_id: str, hypothesis: str, baseline_definition: str, treatment_definition: str, unit_of_analysis: str, rollback_plan: str, *, null_hypothesis: Optional[str] = None, comparator_definition: Optional[str] = None, primary_metric_keys: Optional[list[str]] = None, secondary_metric_keys: Optional[list[str]] = None, sample_plan: Optional[dict[str, Any]] = None, stopping_rules: Optional[dict[str, Any]] = None, safety_boundaries: Optional[dict[str, Any]] = None, consent_requirements: Optional[dict[str, Any]] = None, owner_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_experiment
            (solution_id, hypothesis, null_hypothesis, baseline_definition, treatment_definition,
             comparator_definition, unit_of_analysis, rollback_plan, primary_metric_keys,
             secondary_metric_keys, sample_plan, stopping_rules, safety_boundaries,
             consent_requirements, owner_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::uuid)
            RETURNING *""", (solution_id, hypothesis, null_hypothesis, baseline_definition,
                              treatment_definition, comparator_definition, unit_of_analysis,
                              rollback_plan, json.dumps(primary_metric_keys or []),
                              json.dumps(secondary_metric_keys or []), json.dumps(sample_plan or {}),
                              json.dumps(stopping_rules or {}), json.dumps(safety_boundaries or {}),
                              json.dumps(consent_requirements or {}), owner_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def submit_protocol(conn, experiment_id: str) -> Dict[str, Any]:
    return _transition(conn, experiment_id, "submitted", "draft")


def approve_protocol(conn, experiment_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE solution_experiment SET status = 'protocol_approved', approved_by_party_id = %s::uuid, approved_at = NOW(), updated_at = NOW() WHERE id = %s::uuid AND status = 'submitted' RETURNING *", (approved_by_party_id, experiment_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only submitted experiment protocols can be approved")
        conn.commit()
        return _clean(row)


def start_experiment(conn, experiment_id: str, started_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT e.*, s.current_stage FROM solution_experiment e
            JOIN solution s ON s.id = e.solution_id
            WHERE e.id = %s::uuid FOR UPDATE""", (experiment_id,))
        row = cur.fetchone()
        if not row or row["status"] != "protocol_approved":
            conn.rollback()
            raise ValueError("only approved experiment protocols can start")
        if row["current_stage"] not in ("experiment_ready", "testing"):
            conn.rollback()
            raise ValueError("solution must be experiment-ready before experiment start")
        cur.execute("UPDATE solution_experiment SET status = 'active', started_at = NOW(), updated_at = NOW() WHERE id = %s::uuid RETURNING *", (experiment_id,))
        result = _clean(cur.fetchone())
        conn.commit()
        return result


def record_observation(conn, experiment_id: str, metric_key: str, value: Optional[float], arm: str, *, unit_ref: Optional[str] = None, adverse_event: bool = False, evidence: Optional[dict[str, Any]] = None, recorded_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_experiment_observation
            (experiment_id, unit_ref, metric_key, value, arm, adverse_event, evidence, recorded_by_party_id)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s::uuid) RETURNING *""", (experiment_id, unit_ref, metric_key, value, arm, adverse_event, json.dumps(evidence or {}), recorded_by_party_id))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def complete_experiment(conn, experiment_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT decision FROM solution_experiment_analysis_run WHERE experiment_id = %s::uuid ORDER BY created_at DESC LIMIT 1", (experiment_id,))
        analysis = cur.fetchone()
        if not analysis or analysis["decision"] == "continue":
            conn.rollback()
            raise ValueError("experiment requires a terminal sequential analysis decision")
    return _transition(conn, experiment_id, "completed", "active")


def analyze_sequentially(conn, experiment_id: str, metric_key: str, *, minimum_sample: int = 2, benefit_threshold: float = 0.0, posterior_threshold: float = 0.9, safety_event_limit: Optional[int] = None, analysis_version: str = "sequential-v1") -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT arm, value, adverse_event FROM solution_experiment_observation
            WHERE experiment_id = %s::uuid AND metric_key = %s AND value IS NOT NULL""", (experiment_id, metric_key))
        rows = cur.fetchall()
        baseline = [float(row["value"]) for row in rows if row["arm"] == "baseline"]
        treatment = [float(row["value"]) for row in rows if row["arm"] == "treatment"]
        adverse = sum(1 for row in rows if row["adverse_event"])
        if len(baseline) < minimum_sample or len(treatment) < minimum_sample:
            decision, reason, posterior, effect, se, lower, upper = "insufficient_data", "minimum sample has not been reached", None, None, None, None, None
        else:
            baseline_mean = sum(baseline) / len(baseline)
            treatment_mean = sum(treatment) / len(treatment)
            effect = treatment_mean - baseline_mean
            variance = (sum((x - baseline_mean) ** 2 for x in baseline) / max(len(baseline) - 1, 1) / len(baseline)) + (sum((x - treatment_mean) ** 2 for x in treatment) / max(len(treatment) - 1, 1) / len(treatment))
            se = math.sqrt(max(variance, 1e-12))
            z = effect / se
            posterior = 0.5 * (1 + math.erf(z / math.sqrt(2)))
            lower, upper = effect - 1.96 * se, effect + 1.96 * se
            if safety_event_limit is not None and adverse > safety_event_limit:
                decision, reason = "safety_stop", "adverse-event limit exceeded"
            elif posterior >= posterior_threshold and effect > benefit_threshold:
                decision, reason = "benefit", "posterior benefit probability reached threshold"
            elif posterior <= (1 - posterior_threshold) and effect <= benefit_threshold:
                decision, reason = "futility", "posterior benefit probability is below futility threshold"
            else:
                decision, reason = "continue", "evidence remains in the continuation region"
        cur.execute("""INSERT INTO solution_experiment_analysis_run
            (experiment_id, metric_key, baseline_count, treatment_count, baseline_mean, treatment_mean,
             effect_estimate, standard_error, lower_bound, upper_bound, posterior_probability_benefit,
             adverse_event_count, decision, stopping_reason, analysis_version)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""", (experiment_id, metric_key, len(baseline), len(treatment), sum(baseline) / len(baseline) if baseline else None, sum(treatment) / len(treatment) if treatment else None, effect, se, lower, upper, posterior, adverse, decision, reason, analysis_version))
        result = _clean(cur.fetchone())
        conn.commit()
        return result


def review_result(conn, experiment_id: str, outcome: str, reviewed_by_party_id: str, *, primary_results: Optional[dict[str, Any]] = None, secondary_results: Optional[dict[str, Any]] = None, limitations: Optional[str] = None, evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    if outcome not in ("validated", "invalidated", "inconclusive", "requires_replication"):
        raise ValueError("invalid experiment outcome")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT status, solution_id FROM solution_experiment WHERE id = %s::uuid FOR UPDATE", (experiment_id,))
        experiment = cur.fetchone()
        if not experiment or experiment["status"] != "completed":
            conn.rollback()
            raise ValueError("only completed experiments can be reviewed")
        cur.execute("""INSERT INTO solution_experiment_result
            (experiment_id, outcome, primary_results, secondary_results, limitations, evidence, reviewed_by_party_id, reviewed_at)
            VALUES (%s::uuid, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::uuid, NOW())
            RETURNING *""", (experiment_id, outcome, json.dumps(primary_results or {}), json.dumps(secondary_results or {}), limitations, json.dumps(evidence or []), reviewed_by_party_id))
        result = cur.fetchone()
        cur.execute("UPDATE solution_experiment SET status = %s, updated_at = NOW() WHERE id = %s::uuid", (outcome, experiment_id))
        conn.commit()
        return _clean(result)


def create_replication(conn, solution_id: str, source_experiment_id: str, target_scope_type: str, target_scope_id: str, target_context: str, *, adaptation_required: Optional[str] = None, context_similarity: Optional[float] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT outcome FROM solution_experiment_result WHERE experiment_id = %s::uuid AND outcome = 'validated'", (source_experiment_id,))
        if not cur.fetchone():
            conn.rollback()
            raise ValueError("replication requires a validated source experiment")
        cur.execute("""INSERT INTO solution_replication
            (solution_id, source_experiment_id, target_scope_type, target_scope_id, target_context, adaptation_required, context_similarity)
            VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s) RETURNING *""", (solution_id, source_experiment_id, target_scope_type, target_scope_id, target_context, adaptation_required, context_similarity))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def _transition(conn, experiment_id: str, to_status: str, expected_status: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE solution_experiment SET status = %s, updated_at = NOW() WHERE id = %s::uuid AND status = %s RETURNING *", (to_status, experiment_id, expected_status))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError(f"experiment must be {expected_status}")
        conn.commit()
        return _clean(row)
