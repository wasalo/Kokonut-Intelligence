"""Odds, posterior, and utility-based sequential decision calculations."""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, Iterable, Optional

from psycopg2.extras import RealDictCursor


CALCULATION_VERSION = "odds-v1"


def _finite(value: float, name: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be finite") from None
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def probability_to_odds(probability: float) -> float:
    probability = _finite(probability, "probability")
    if not 0 < probability < 1:
        raise ValueError("probability must be between zero and one")
    return probability / (1 - probability)


def odds_to_probability(odds: float) -> float:
    odds = _finite(odds, "odds")
    if odds <= 0:
        raise ValueError("odds must be positive")
    return odds / (1 + odds)


def update_posterior(prior_probability: float, likelihood_hypothesis: float, likelihood_alternative: float) -> Dict[str, float]:
    for name, value in (("prior probability", prior_probability), ("hypothesis likelihood", likelihood_hypothesis), ("alternative likelihood", likelihood_alternative)):
        value = _finite(value, name)
        if not 0 < value <= 1:
            raise ValueError(f"{name} must be greater than zero and at most one")
    prior_odds = probability_to_odds(prior_probability)
    likelihood_ratio = likelihood_hypothesis / likelihood_alternative
    posterior_odds = prior_odds * likelihood_ratio
    return {
        "prior_odds": prior_odds,
        "likelihood_ratio": likelihood_ratio,
        "posterior_odds": posterior_odds,
        "posterior_probability": odds_to_probability(posterior_odds),
    }


def odds_strategy(probabilities: Iterable[float]) -> Dict[str, Any]:
    """Return the optimal last-success threshold for a finite independent sequence."""
    probabilities = list(probabilities)
    if not probabilities:
        raise ValueError("at least one probability is required")
    odds = [probability_to_odds(p) for p in probabilities]
    cumulative = 0.0
    threshold = 0
    for index in range(len(odds) - 1, -1, -1):
        cumulative += odds[index]
        if cumulative >= 1:
            threshold = index
            break
    q_product = math.prod(1 - probabilities[index] for index in range(threshold, len(probabilities)))
    win_probability = q_product * cumulative
    return {"threshold_index": threshold, "odds_sum": cumulative, "win_probability": win_probability, "probabilities": probabilities}


def utility_threshold(*, true_positive_benefit: float, false_positive_cost: float, false_negative_cost: float, action_cost: float = 0.0) -> float:
    """Probability above which acting has greater expected utility than waiting."""
    values = {"true positive benefit": true_positive_benefit, "false positive cost": false_positive_cost, "false negative cost": false_negative_cost, "action cost": action_cost}
    if any(_finite(value, name) < 0 for name, value in values.items()):
        raise ValueError("utility inputs must be finite and non-negative")
    denominator = true_positive_benefit + false_negative_cost
    if denominator <= 0:
        raise ValueError("benefit and false-negative cost must produce a positive denominator")
    threshold = (false_positive_cost + action_cost) / denominator
    return min(max(threshold, 0.0), 1.0)


def evaluate_action(posterior_probability: float, *, action_threshold: float, continue_threshold: Optional[float] = None, action: str = "act") -> Dict[str, Any]:
    posterior_probability = _finite(posterior_probability, "posterior probability")
    action_threshold = _finite(action_threshold, "action threshold")
    if not 0 <= posterior_probability <= 1:
        raise ValueError("posterior probability must be between zero and one")
    if not 0 <= action_threshold <= 1:
        raise ValueError("action threshold must be between zero and one")
    continue_threshold = continue_threshold if continue_threshold is not None else action_threshold * 0.5
    continue_threshold = _finite(continue_threshold, "continue threshold")
    if not 0 <= continue_threshold <= action_threshold:
        raise ValueError("continue threshold must be between zero and the action threshold")
    if posterior_probability >= action_threshold:
        decision = action
        reason = "posterior reached action threshold"
    elif posterior_probability <= continue_threshold:
        decision = "stop"
        reason = "posterior is below continuation threshold"
    else:
        decision = "continue"
        reason = "posterior remains in continuation region"
    return {"action": decision, "posterior_probability": posterior_probability, "action_threshold": action_threshold, "continue_threshold": continue_threshold, "stopping_reason": reason}


def apply_evidence(conn, hypothesis_id: str, evidence_event_id: str, *, evaluated_by_party_id: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM decision_hypothesis WHERE id = %s::uuid FOR UPDATE", (hypothesis_id,))
        hypothesis = cur.fetchone()
        cur.execute("SELECT * FROM decision_evidence_event WHERE id = %s::uuid AND hypothesis_id = %s::uuid FOR UPDATE", (evidence_event_id, hypothesis_id))
        evidence = cur.fetchone()
        if not hypothesis or not evidence or evidence["likelihood_hypothesis"] is None or evidence["likelihood_alternative"] is None:
            conn.rollback()
            raise ValueError("hypothesis and complete likelihood-bearing evidence are required")
        if evidence["quality_status"] in ("rejected", "stale"):
            conn.rollback()
            raise ValueError("rejected or stale evidence cannot be applied")
        cur.execute("SELECT 1 FROM decision_posterior_update WHERE evidence_event_id = %s::uuid", (evidence_event_id,))
        if cur.fetchone():
            conn.rollback()
            raise ValueError("evidence has already been applied")
        if evidence["dependence_group"]:
            cur.execute("""SELECT 1 FROM decision_evidence_event e
                JOIN decision_posterior_update p ON p.evidence_event_id = e.id
                WHERE e.hypothesis_id = %s::uuid AND e.dependence_group = %s
                LIMIT 1""", (hypothesis_id, evidence["dependence_group"]))
            if cur.fetchone():
                conn.rollback()
                raise ValueError("dependent evidence group has already been applied")
        cur.execute("SELECT * FROM decision_posterior_update WHERE hypothesis_id = %s::uuid ORDER BY created_at DESC LIMIT 1", (hypothesis_id,))
        previous = cur.fetchone()
        prior_probability = float(previous["posterior_probability"]) if previous else float(hypothesis["prior_probability"])
        update = update_posterior(prior_probability, float(evidence["likelihood_hypothesis"]), float(evidence["likelihood_alternative"]))
        cur.execute("""INSERT INTO decision_posterior_update
            (hypothesis_id, evidence_event_id, prior_odds, likelihood_ratio, posterior_odds,
             posterior_probability, effective_evidence_count, calculation_version)
             VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s) RETURNING *""", (hypothesis_id, evidence_event_id, update["prior_odds"], update["likelihood_ratio"], update["posterior_odds"], update["posterior_probability"], (float(previous["effective_evidence_count"]) + 1 if previous else 1), CALCULATION_VERSION))
        row = dict(cur.fetchone())
        conn.commit()
        return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in row.items()}
