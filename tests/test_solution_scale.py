"""Integration coverage for scale gates, learning, and retirement."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_lifecycle, solution_scale

PARTY_ID = "b0000000-0000-0000-0000-000000002712"
PROPOSER_ID = "b0000000-0000-0000-0000-000000002713"


def test_scale_requires_evidence_and_learning_application_uses_gateway():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = learning_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PROPOSER_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Scale Reviewer')", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Retirement Proposer')", (PROPOSER_ID,))
        conn.commit()
        solution = solution_lifecycle.create_solution(conn, f"scale-{uuid.uuid4().hex[:8]}", "Validated practice", "practice", "A recurring problem", owner_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        gate = solution_scale.create_gate(conn, solution_id, "organization", str(uuid.uuid4()), "replicability", "Replicate in a distinct context", threshold="1",)
        with pytest.raises(ValueError, match="evidence"):
            solution_scale.evaluate_gate(conn, str(gate["id"]), True, "pass", [], PARTY_ID)
        lifecycle_gate = solution_lifecycle.create_gate(conn, solution_id, "discovered", "scaled")
        solution_lifecycle.approve_gate(conn, str(lifecycle_gate["id"]), PARTY_ID)
        solution_lifecycle.evaluate_gate(conn, str(lifecycle_gate["id"]), True, PARTY_ID, evidence=[{"source": "review"}])
        with pytest.raises(ValueError, match="scale gates"):
            solution_lifecycle.transition(conn, solution_id, "scaled", PARTY_ID, approved_by_party_id=PARTY_ID, rationale="Attempted scale")
        evaluated = solution_scale.evaluate_gate(conn, str(gate["id"]), True, "pass", [{"replication":"reviewed"}], PARTY_ID)
        assert evaluated["status"] == "passed"
        learning = solution_scale.record_learning(conn, solution_id, "context_transfer", "Training must be localized", "Update the adoption playbook", transferability="medium", evidence=[{"source":"replication"}], owner_party_id=PARTY_ID)
        learning_id = str(learning["id"])
        with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
            solution_scale.apply_learning(conn, learning_id, "solution-v2", PARTY_ID)
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PROPOSER_ID,))
        conn.commit()
        conn.close()


def test_clean_helper_converts_uuids():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "status": "passed"}
    cleaned = solution_scale._clean(row)
    assert cleaned["id"] == str(mock_uuid)


def test_evaluate_gate_rejects_empty_evidence():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="evidence"):
        solution_scale.evaluate_gate(mock_conn, "gate-id", True, "val", [], "party-id")


def test_retirement_proposal_requires_attributed_proposer_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="attributed proposer"):
        solution_scale.propose_retirement(
            mock_conn, "solution-id", "unsafe", "Evidence withdrawn"
        )
    mock_conn.cursor.assert_not_called()


def test_legacy_retirement_proposal_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_scale.propose_retirement(
            mock_conn,
            "solution-id",
            "unsafe",
            "Evidence withdrawn",
            evidence_refs=[{"source": "review"}],
            migration_plan="Preserve active deployments",
            created_by_party_id=PROPOSER_ID,
        )
    mock_conn.cursor.assert_not_called()


def test_legacy_retirement_approval_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_scale.approve_retirement(mock_conn, "retirement-id", PARTY_ID)
    mock_conn.cursor.assert_not_called()


def test_apply_learning_legacy_helper_fails_closed_without_gateway_context():
    connection = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_scale.apply_learning(connection, "learning-id", "solution-v2", PARTY_ID)
    connection.cursor.assert_not_called()
