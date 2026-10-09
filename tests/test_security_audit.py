"""Tests for services.security.audit — AuditLogger."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.security.audit import AuditLogger


@pytest.fixture
def mock_conn():
    return MagicMock()


@pytest.fixture
def audit(mock_conn):
    return AuditLogger(conn=mock_conn)


def test_log_access_returns_id(audit, mock_conn):
    """log_access returns a UUID string on success."""
    cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    log_id = audit.log_access(
        caller="agent-1",
        resource_type="harvest_event",
        action="write",
        status="allowed",
    )
    assert isinstance(log_id, str)
    assert len(log_id) == 36  # UUID format
    mock_conn.commit.assert_called_once()


def test_log_access_denied_status(audit, mock_conn):
    """log_access with denied status still returns a log id."""
    cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    log_id = audit.log_access(
        caller="agent-2",
        resource_type="metric_value",
        action="read",
        status="denied",
    )
    assert isinstance(log_id, str)


def test_log_access_serializes_gateway_metadata(audit, mock_conn):
    """Gateway audit metadata remains queryable without raw HTTP verbs."""
    cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    audit.log_access(
        caller="gateway-client",
        resource_type="gateway:data_stream_post",
        action="write",
        status="allowed",
        metadata={"http_method": "POST", "status_code": 201},
    )

    params = cursor.execute.call_args[0][1]
    assert params[5] == "write"
    assert json.loads(params[9]) == {"http_method": "POST", "status_code": 201}


def test_query_logs_builds_conditions(audit, mock_conn):
    """query_logs builds WHERE conditions from provided filters."""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    audit.query_logs(caller="agent-1", status="denied", limit=10)
    # Verify the SQL was executed
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "caller = %s" in sql
    assert "status = %s" in sql


def test_query_logs_returns_dicts(audit, mock_conn):
    """query_logs returns a list of dicts with expected keys."""
    now = datetime.now(timezone.utc)
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("id-1", "agent-1", None, "harvest_event", "res-1", "write", "allowed", None, now),
    ]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    results = audit.query_logs()
    assert len(results) == 1
    assert results[0]["caller"] == "agent-1"
    assert results[0]["action"] == "write"
    assert results[0]["status"] == "allowed"


def test_log_access_rolls_back_on_exception(audit, mock_conn):
    """log_access rolls back the connection on DB error."""
    cursor = MagicMock()
    cursor.execute.side_effect = Exception("DB error")
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(Exception, match="DB error"):
        audit.log_access("agent-1", "harvest_event", "write", "allowed")
    mock_conn.rollback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
