"""Integration coverage for scale gates, learning, and retirement."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_lifecycle, solution_scale


PARTY_ID = "b0000000-0000-0000-0000-000000002712"


def test_scale_requires_evidence_and_learning_can_be_applied():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = learning_id = retirement_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Scale Reviewer')", (PARTY_ID,))
        conn.commit()
        solution = solution_lifecycle.create_solution(conn, f"scale-{uuid.uuid4().hex[:8]}", "Validated practice", "practice", "A recurring problem", owner_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        gate = solution_scale.create_gate(conn, solution_id, "organization", str(uuid.uuid4()), "replicability", "Replicate in a distinct context")
        with pytest.raises(ValueError, match="evidence"):
            solution_scale.evaluate_gate(conn, str(gate["id"]), True, "pass", [], PARTY_ID)
        evaluated = solution_scale.evaluate_gate(conn, str(gate["id"]), True, "pass", [{"replication":"reviewed"}], PARTY_ID)
        assert evaluated["status"] == "passed"
        learning = solution_scale.record_learning(conn, solution_id, "context_transfer", "Training must be localized", "Update the adoption playbook", transferability="medium", evidence=[{"source":"replication"}], owner_party_id=PARTY_ID)
        learning_id = str(learning["id"])
        applied = solution_scale.apply_learning(conn, learning_id, "solution-v2", PARTY_ID)
        assert applied["decision_status"] == "applied"
        retirement = solution_scale.propose_retirement(conn, solution_id, "superseded", "A safer validated version exists", evidence_refs=[{"source":"review"}], created_by_party_id=PARTY_ID)
        retirement_id = str(retirement["id"])
        approved = solution_scale.approve_retirement(conn, retirement_id, PARTY_ID)
        assert approved["status"] == "approved"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
        conn.commit()
        conn.close()
