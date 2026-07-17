"""Tests for sequential odds and utility decisions."""

import uuid

import pytest

from services.decision import odds_engine, sequential_evidence
from services.ingestion.base import get_db


def test_odds_update_and_last_success_strategy():
    update = odds_engine.update_posterior(0.2, 0.8, 0.2)
    assert round(update["posterior_probability"], 4) == 0.5
    strategy = odds_engine.odds_strategy([0.1, 0.2, 0.3, 0.4])
    assert strategy["threshold_index"] == 2
    assert odds_engine.utility_threshold(true_positive_benefit=100, false_positive_cost=10, false_negative_cost=50, action_cost=5) == 0.1


@pytest.mark.parametrize("values", [(0.2, 0, 0.2), (0.2, 1.1, 0.2), (0.2, 0.8, float("nan"))])
def test_posterior_rejects_invalid_probability_inputs(values):
    with pytest.raises(ValueError):
        odds_engine.update_posterior(*values)


def test_action_evaluation_rejects_invalid_continuation_region():
    with pytest.raises(ValueError, match="continue threshold"):
        odds_engine.evaluate_action(0.5, action_threshold=0.6, continue_threshold=0.7)


def test_utility_threshold_rejects_negative_costs():
    with pytest.raises(ValueError, match="non-negative"):
        odds_engine.utility_threshold(true_positive_benefit=100, false_positive_cost=-1, false_negative_cost=50)


def test_database_posterior_rejects_dependent_evidence():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    hypothesis_id = None
    try:
        hypothesis = sequential_evidence.create_hypothesis(conn, "test", str(uuid.uuid4()), "event", "no event", 0.2)
        hypothesis_id = str(hypothesis["id"])
        first = sequential_evidence.record_evidence(conn, hypothesis_id, "sensor", "signal", "2026-07-01T00:00:00+00:00", source_ref="a", dependence_group="sensor-a", likelihood_hypothesis=0.8, likelihood_alternative=0.2)
        second = sequential_evidence.record_evidence(conn, hypothesis_id, "sensor", "signal", "2026-07-02T00:00:00+00:00", source_ref="b", dependence_group="sensor-a", likelihood_hypothesis=0.8, likelihood_alternative=0.2)
        odds_engine.apply_evidence(conn, hypothesis_id, str(first["id"]))
        with pytest.raises(ValueError, match="dependent"):
            odds_engine.apply_evidence(conn, hypothesis_id, str(second["id"]))
    finally:
        conn.rollback()
        if hypothesis_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM decision_hypothesis WHERE id = %s::uuid", (hypothesis_id,))
            conn.commit()
        conn.close()
