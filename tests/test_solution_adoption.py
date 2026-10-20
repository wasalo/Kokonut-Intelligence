"""Coverage for solution adoption readiness and retired unsafe writers."""

from unittest.mock import MagicMock

import pytest

from services.innovation import solution_adoption


def test_legacy_create_program_fails_before_database_access():
    mock_conn = MagicMock()
    with pytest.raises(RuntimeError, match="exact-location solution-lifecycle Gateway"):
        solution_adoption.create_program(
            mock_conn, "solution-id", "location", "location-id", "community pathway"
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()


@pytest.mark.parametrize("consent_checked", [False, True])
def test_legacy_record_event_fails_closed_before_database_access(consent_checked):
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="consent-aware, location-scoped Gateway"):
        solution_adoption.record_event(
            mock_conn, "program-id", "adopter-1", "first_use",
            consent_checked=consent_checked,
        )
    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()


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
