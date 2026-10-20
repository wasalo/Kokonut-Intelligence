"""Integration coverage for solution experiments and replication."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_experiments
from tests.solution_lifecycle_fixtures import create_solution_fixture, fixture_key

PARTY_ID = "b0000000-0000-0000-0000-000000002709"


def test_validated_experiment_can_create_replication():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = experiment_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Experiment Lead')", (PARTY_ID,))
        conn.commit()
        solution = create_solution_fixture(conn, fixture_key("experiment"), "Water protocol", "practice", "Water access", owner_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        # Establish the lifecycle prerequisite as fixture state. Legacy stage
        # transitions now fail closed; their authorized path is the Gateway.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE solution SET current_stage = 'experiment_ready' WHERE id = %s::uuid",
                (solution_id,),
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO solution_experiment (
                       solution_id, hypothesis, baseline_definition,
                       treatment_definition, unit_of_analysis, rollback_plan,
                       sample_plan, owner_party_id
                   ) VALUES (
                       %s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s::uuid
                   ) RETURNING id""",
                (
                    solution_id, "Protocol improves water reliability",
                    "Current practice", "New protocol", "Field zone",
                    "Document rollback", '{"minimum_sample":1}', PARTY_ID,
                ),
            )
            experiment_id = str(cur.fetchone()[0])
        conn.commit()
        solution_experiments.submit_protocol(conn, experiment_id)
        solution_experiments.approve_protocol(conn, experiment_id, PARTY_ID)
        solution_experiments.start_experiment(conn, experiment_id, PARTY_ID)
        solution_experiments.record_observation(conn, experiment_id, "water_reliability", 80, "baseline", recorded_by_party_id=PARTY_ID)
        solution_experiments.record_observation(conn, experiment_id, "water_reliability", 95, "treatment", recorded_by_party_id=PARTY_ID)
        analysis = solution_experiments.analyze_sequentially(conn, experiment_id, "water_reliability", minimum_sample=1, posterior_threshold=0.8)
        assert analysis["decision"] == "benefit"
        solution_experiments.complete_experiment(conn, experiment_id)
        solution_experiments.review_result(conn, experiment_id, "validated", PARTY_ID, primary_results={"lift": 15}, evidence=[{"source":"observations"}])
        replication = solution_experiments.create_replication(conn, solution_id, experiment_id, "location", str(uuid.uuid4()), "Different climate context", adaptation_required="Adjust schedule", context_similarity=0.7)
        assert replication["status"] == "proposed"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
        conn.commit()
        conn.close()


def test_clean_helper_converts_uuids():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "hypothesis": "test"}
    cleaned = solution_experiments._clean(row)
    assert cleaned["id"] == str(mock_uuid)


def test_approve_protocol_rejects_non_submitted():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only submitted"):
        solution_experiments.approve_protocol(mock_conn, "exp-id", "party-id")


def test_legacy_experiment_creation_fails_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(RuntimeError, match="location-scoped Solution Lifecycle Gateway"):
        solution_experiments.create_experiment(
            mock_conn, "solution-id", "hypothesis", "baseline", "treatment",
            "unit", "rollback", owner_party_id=PARTY_ID,
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()
