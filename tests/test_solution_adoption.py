"""Integration coverage for solution adoption readiness and consent."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_adoption, solution_lifecycle


PARTY_ID = "b0000000-0000-0000-0000-000000002711"


def test_adoption_requires_readiness_and_consent_for_use():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = program_id = None
    adopter_id = str(uuid.uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Adoption Lead')", (PARTY_ID,))
        conn.commit()
        solution = solution_lifecycle.create_solution(conn, f"adoption-{uuid.uuid4().hex[:8]}", "Water practice", "practice", "Water access", owner_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        program = solution_adoption.create_program(conn, solution_id, "location", adopter_id, "cooperative enablement", local_adaptation_policy="Keep water safety invariants")
        program_id = str(program["id"])
        readiness = solution_adoption.assess_readiness(conn, solution_id, "location", adopter_id, 0.5, 0.8, remediation_plan="Train field coordinators", assessed_by_party_id=PARTY_ID)
        assert readiness["readiness_status"] == "remediating"
        with pytest.raises(ValueError, match="consent"):
            solution_adoption.record_event(conn, program_id, "adopter-1", "first_use")
        event = solution_adoption.record_event(conn, program_id, "adopter-1", "first_use", consent_checked=True, recorded_by_party_id=PARTY_ID)
        assert event["event_type"] == "first_use"
        configuration = solution_adoption.approve_configuration(conn, solution_id, "location", adopter_id, {"safety":"required"}, {"schedule":"local"}, adaptation_owner_party_id=PARTY_ID, approved_by_party_id=PARTY_ID)
        assert configuration["approval_status"] == "approved"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
        conn.commit()
        conn.close()


def test_record_event_rejects_missing_consent():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="consent"):
        solution_adoption.record_event(
            mock_conn, "program-id", "adopter-1", "first_use"
        )


def test_assess_readiness_status_logic():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": "test", "readiness_status": "ready"}
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = solution_adoption.assess_readiness(
        mock_conn, "sol-id", "loc", "scope-id", 0.9, 0.5
    )
    assert result["readiness_status"] == "ready"
