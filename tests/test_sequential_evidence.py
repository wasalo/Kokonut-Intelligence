"""Integration coverage for the immutable sequential evidence ledger."""

import uuid

import pytest

from services.decision import sequential_evidence
from services.ingestion.base import get_db


def test_evidence_ledger_preserves_dependence_and_likelihood_inputs():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    hypothesis_id = None
    try:
        hypothesis = sequential_evidence.create_hypothesis(conn, "threat", str(uuid.uuid4()), "Drought will occur", "Drought will not occur", 0.2)
        hypothesis_id = str(hypothesis["id"])
        event = sequential_evidence.record_evidence(conn, hypothesis_id, "weather_observation", "rainfall_deficit", "2026-07-01T00:00:00+00:00", source_ref="weather-1", value={"deficit_pct":40}, quality_status="verified", source_reliability=0.9, dependence_group="weather-provider-1", likelihood_hypothesis=0.8, likelihood_alternative=0.2)
        events = sequential_evidence.list_evidence(conn, hypothesis_id)
        assert str(events[0]["id"]) == str(event["id"])
        assert events[0]["dependence_group"] == "weather-provider-1"
        assert float(events[0]["likelihood_hypothesis"]) == 0.8
    finally:
        conn.rollback()
        if hypothesis_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM decision_hypothesis WHERE id = %s::uuid", (hypothesis_id,))
            conn.commit()
        conn.close()


@pytest.mark.parametrize("kwargs", [
    {"likelihood_hypothesis": 0.8},
    {"likelihood_hypothesis": 1.1, "likelihood_alternative": 0.2},
    {"likelihood_hypothesis": 0.8, "likelihood_alternative": 0.2, "dependence_group": " "},
    {"quality_status": "invalid"},
])
def test_record_evidence_rejects_incomplete_or_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        sequential_evidence.record_evidence(
            None, "not-a-real-hypothesis", "sensor", "signal",
            "2026-07-01T00:00:00+00:00", source_ref="source", **kwargs
        )
