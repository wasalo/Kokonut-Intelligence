"""Integration coverage for the canonical solution lifecycle."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_lifecycle


PARTY_ID = "b0000000-0000-0000-0000-000000002708"


def test_solution_requires_gate_for_validated_promotion():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Solution Owner')", (PARTY_ID,))
        conn.commit()
        solution = solution_lifecycle.create_solution(conn, f"solution-{uuid.uuid4().hex[:8]}", "Field water protocol", "practice", "Unreliable water access", owner_party_id=PARTY_ID, created_by_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        solution_lifecycle.transition(conn, solution_id, "triaged", PARTY_ID, rationale="Field need confirmed")
        with pytest.raises(ValueError, match="stage gate"):
            solution_lifecycle.transition(conn, solution_id, "validated", PARTY_ID, rationale="Validation attempted")
        gate = solution_lifecycle.create_gate(conn, solution_id, "triaged", "validated", required_experiment_count=0)
        solution_lifecycle.approve_gate(conn, str(gate["id"]), PARTY_ID)
        solution_lifecycle.evaluate_gate(conn, str(gate["id"]), True, PARTY_ID, observed={"experiments": 1}, evidence=[{"source":"experiment"}])
        promoted = solution_lifecycle.transition(conn, solution_id, "validated", PARTY_ID, approved_by_party_id=PARTY_ID, rationale="Evidence gate approved", evidence=[{"source":"field-review"}])
        assert promoted["current_stage"] == "validated"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
        conn.commit()
        conn.close()


def test_stages_constant_covers_full_lifecycle():
    assert "discovered" in solution_lifecycle.STAGES
    assert "scaled" in solution_lifecycle.STAGES
    assert "retired" in solution_lifecycle.STAGES
    assert len(solution_lifecycle.STAGES) >= 15


def test_promotion_gates_constant():
    assert "validated" in solution_lifecycle.PROMOTION_GATES
    assert "funded" in solution_lifecycle.PROMOTION_GATES
    assert "scaled" in solution_lifecycle.PROMOTION_GATES


def test_evaluate_gate_requires_evidence():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="evidence"):
        solution_lifecycle.evaluate_gate(mock_conn, "gate-id", True, "party-id")
