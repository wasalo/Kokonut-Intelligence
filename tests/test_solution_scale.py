"""Integration coverage for scale gates, learning, and retirement."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_lifecycle, solution_scale
from tests.solution_lifecycle_fixtures import create_gate_fixture, create_solution_fixture, fixture_key

PARTY_ID = "b0000000-0000-0000-0000-000000002712"
PROPOSER_ID = "b0000000-0000-0000-0000-000000002713"


def test_legacy_learning_and_stage_gate_writes_fail_closed():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PROPOSER_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Scale Reviewer')", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Retirement Proposer')", (PROPOSER_ID,))
        conn.commit()
        solution = create_solution_fixture(conn, fixture_key("scale"), "Validated practice", "practice", "A recurring problem", owner_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        gate_id = create_gate_fixture(conn, solution_id, "discovered", "scaled")
        with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
            solution_lifecycle.approve_gate(conn, gate_id, PARTY_ID)
        with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
            solution_lifecycle.evaluate_gate(
                conn, gate_id, True, PARTY_ID,
                evidence=[{"source": "review"}],
            )
        with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
            solution_lifecycle.transition(conn, solution_id, "scaled", PARTY_ID, approved_by_party_id=PARTY_ID, rationale="Attempted scale")
        with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
            solution_scale.record_learning(
                conn,
                solution_id,
                "context_transfer",
                "Training must be localized",
                "Update the adoption playbook",
                transferability="medium",
                evidence=[{"source": "replication"}],
                owner_party_id=PARTY_ID,
            )
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


def test_legacy_scale_gate_evaluation_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_scale.evaluate_gate(mock_conn, "gate-id", True, "val", [], "party-id")
    mock_conn.cursor.assert_not_called()


def test_legacy_scale_gate_creation_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_scale.create_gate(
            mock_conn, "solution-id", "location", "location-id", "safety", "Review safety"
        )
    mock_conn.cursor.assert_not_called()


def test_legacy_learning_proposal_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_scale.record_learning(
            mock_conn,
            "solution-id",
            "context_transfer",
            "A bounded finding",
            "A proposed action",
            source_replication_id="replication-id",
            evidence=[{"source": "review"}],
            owner_party_id=PARTY_ID,
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()


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
