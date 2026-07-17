"""Transaction and capability checks for the Impact Office orchestrator."""

from unittest.mock import MagicMock

import pytest

from services.office import UnsupportedOperationError, run_cycle, run_full_cycle


def test_full_cycle_commits_one_atomic_workflow():
    conn = MagicMock()
    cur = conn.cursor.return_value

    result = run_full_cycle(conn, "location-1", "organization-1")

    assert result["steps_completed"] == 5
    conn.commit.assert_called_once_with()
    conn.rollback.assert_not_called()
    cur.close.assert_called_once_with()


def test_cycle_rolls_back_and_propagates_database_error():
    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.execute.side_effect = RuntimeError("database failed")

    with pytest.raises(RuntimeError, match="database failed"):
        run_full_cycle(conn)

    conn.rollback.assert_called_once_with()
    conn.commit.assert_not_called()
    cur.close.assert_called_once_with()


def test_unsupported_cycle_fails_before_persistence():
    conn = MagicMock()

    with pytest.raises(UnsupportedOperationError, match="Unsupported Impact Office cycle"):
        run_cycle(conn, "attestation_cycle")

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    conn.rollback.assert_not_called()
