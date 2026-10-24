"""Transaction and capability checks for the Impact Office orchestrator."""

from unittest.mock import MagicMock

import pytest

from services.office import UnsupportedOperationError, get_run_status, run_cycle, run_full_cycle


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


def test_run_status_redacts_persisted_errors_from_run_and_steps():
    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.fetchone.return_value = (
        "run-1", "full-cycle-1", "Full Cycle", "full_cycle", "failed",
        "started", "completed", "synthetic database diagnostic",
    )
    cur.fetchall.return_value = [
        ("Compute metrics", "compute_metric", "failed", "started", "completed", "synthetic step diagnostic")
    ]

    result = get_run_status(conn, "run-1")

    assert result["status"] == "failed"
    assert result["error_message"] == "[details redacted]"
    assert result["steps"][0]["status"] == "failed"
    assert result["steps"][0]["error"] == "[details redacted]"
    assert "synthetic database diagnostic" not in str(result)
    assert "synthetic step diagnostic" not in str(result)
    cur.close.assert_called_once_with()
