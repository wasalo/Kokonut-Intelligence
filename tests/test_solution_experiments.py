"""Integration coverage for solution experiments and replication."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_experiments, solution_lifecycle


PARTY_ID = "b0000000-0000-0000-0000-000000002709"


def test_validated_experiment_can_create_replication():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = experiment_id = replication_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Experiment Lead')", (PARTY_ID,))
        conn.commit()
        solution = solution_lifecycle.create_solution(conn, f"experiment-{uuid.uuid4().hex[:8]}", "Water protocol", "practice", "Water access", owner_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        solution_lifecycle.transition(conn, solution_id, "triaged", PARTY_ID, rationale="Need screened")
        solution_lifecycle.transition(conn, solution_id, "framed", PARTY_ID, rationale="Problem framed")
        solution_lifecycle.transition(conn, solution_id, "experiment_ready", PARTY_ID, rationale="Protocol ready")
        experiment = solution_experiments.create_experiment(conn, solution_id, "Protocol improves water reliability", "Current practice", "New protocol", "Field zone", "Document rollback")
        experiment_id = str(experiment["id"])
        solution_experiments.submit_protocol(conn, experiment_id)
        solution_experiments.approve_protocol(conn, experiment_id, PARTY_ID)
        solution_experiments.start_experiment(conn, experiment_id, PARTY_ID)
        solution_experiments.record_observation(conn, experiment_id, "water_reliability", 80, "baseline", recorded_by_party_id=PARTY_ID)
        solution_experiments.record_observation(conn, experiment_id, "water_reliability", 95, "treatment", recorded_by_party_id=PARTY_ID)
        solution_experiments.complete_experiment(conn, experiment_id)
        solution_experiments.review_result(conn, experiment_id, "validated", PARTY_ID, primary_results={"lift": 15}, evidence=[{"source":"observations"}])
        replication = solution_experiments.create_replication(conn, solution_id, experiment_id, "location", str(uuid.uuid4()), "Different climate context", adaptation_required="Adjust schedule", context_similarity=0.7)
        replication_id = str(replication["id"])
        assert replication["status"] == "proposed"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
        conn.commit()
        conn.close()
