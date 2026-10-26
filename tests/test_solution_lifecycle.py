"""Integration coverage for the canonical solution lifecycle."""

from unittest.mock import MagicMock

import pytest

from services.innovation import solution_lifecycle


def test_legacy_stage_transition_fails_closed_before_database_access():
    mock_conn = MagicMock()
    for target_stage in ("triaged", "validated", "scaled"):
        with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
            solution_lifecycle.transition(
                mock_conn,
                "solution-id",
                target_stage,
                "actor-id",
                approved_by_party_id="reviewer-id",
                rationale="Attempted legacy stage transition",
            )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_not_called()


def test_stages_constant_covers_full_lifecycle():
    assert "discovered" in solution_lifecycle.STAGES
    assert "scaled" in solution_lifecycle.STAGES
    assert "retired" in solution_lifecycle.STAGES
    assert len(solution_lifecycle.STAGES) >= 15


def test_promotion_gates_constant():
    assert "validated" in solution_lifecycle.PROMOTION_GATES
    assert "funded" in solution_lifecycle.PROMOTION_GATES
    assert "scaled" in solution_lifecycle.PROMOTION_GATES


def test_legacy_solution_create_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_lifecycle.create_solution(
            mock_conn, "local-key", "A practice", "practice", "A field need"
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()


def test_legacy_solution_link_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="location-scoped sharing workflow"):
        solution_lifecycle.add_link(
            mock_conn, "solution-id", "location", "location-id", "supports"
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()


def test_legacy_stage_gate_create_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="location-scoped Gateway grant"):
        solution_lifecycle.create_gate(mock_conn, "solution-id", "testing", "validated")
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()


def test_legacy_gate_approval_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_lifecycle.approve_gate(mock_conn, "gate-id", "party-id")
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_not_called()


def test_legacy_gate_evaluation_fails_closed_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="authenticated location-scoped Gateway grant"):
        solution_lifecycle.evaluate_gate(
            mock_conn, "gate-id", True, "party-id", evidence=[{"source": "review"}]
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_not_called()


def test_legacy_retirement_stage_transition_fails_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="location-scoped execution and sunset"):
        solution_lifecycle.transition(
            mock_conn,
            "solution-id",
            "retired",
            "actor-id",
            approved_by_party_id="reviewer-id",
            rationale="Retirement was independently approved.",
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_not_called()


def test_legacy_transition_still_rejects_unknown_stage_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="invalid solution stage"):
        solution_lifecycle.transition(
            mock_conn, "solution-id", "not-a-stage", rationale="Invalid stage"
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_not_called()
