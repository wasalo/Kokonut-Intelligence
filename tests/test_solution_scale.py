"""Integration coverage for scale gates, learning, and retirement."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_lifecycle, solution_scale

PARTY_ID = "b0000000-0000-0000-0000-000000002712"
PROPOSER_ID = "b0000000-0000-0000-0000-000000002713"


def test_scale_requires_evidence_and_learning_can_be_applied():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = learning_id = retirement_id = replacement_id = None
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
        with pytest.raises(ValueError, match="not available for application"):
            solution_scale.apply_learning(conn, learning_id, "solution-v2", PARTY_ID)
        replacement_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("INSERT INTO solution (id, canonical_key, name, solution_type, problem_statement) VALUES (%s::uuid, %s, 'Replacement', 'practice', 'Safer approach')", (replacement_id, f"replacement-{uuid.uuid4().hex[:8]}"))
        retirement = solution_scale.propose_retirement(conn, solution_id, "superseded", "A safer validated version exists", evidence_refs=[{"source":"review"}], migration_plan="Migrate adopters to the replacement", replacement_solution_id=replacement_id, created_by_party_id=PROPOSER_ID)
        retirement_id = str(retirement["id"])
        with pytest.raises(ValueError, match="independent reviewer"):
            solution_scale.approve_retirement(conn, retirement_id, PROPOSER_ID)
        approved = solution_scale.approve_retirement(conn, retirement_id, PARTY_ID)
        assert approved["status"] == "approved"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            if replacement_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (replacement_id,))
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


def test_apply_learning_requires_accepted_review_attribution():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"id": "learning-id", "decision_status": "applied"}

    result = solution_scale.apply_learning(
        connection, "learning-id", "solution-v2", PARTY_ID
    )

    sql = cursor.execute.call_args.args[0]
    assert "decision_status = 'accepted'" in sql
    assert "reviewed_by_party_id IS NOT NULL" in sql
    assert "reviewed_at IS NOT NULL" in sql
    assert result["decision_status"] == "applied"


def test_apply_learning_rejects_proposed_records_without_opening_a_second_query():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None

    with pytest.raises(ValueError, match="not available for application"):
        solution_scale.apply_learning(connection, "learning-id", "solution-v2", PARTY_ID)

    connection.rollback.assert_called_once()
    assert cursor.execute.call_count == 1
