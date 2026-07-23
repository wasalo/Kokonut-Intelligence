"""Tests for services.security.capabilities — CapabilityManager."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.security.capabilities import CapabilityManager


@pytest.fixture
def mock_conn():
    return MagicMock()


@pytest.fixture
def manager(mock_conn):
    return CapabilityManager(conn=mock_conn)


def test_hash_token_returns_sha256(manager):
    """_hash_token produces a deterministic SHA-256 hex digest."""
    token = "test-token-abc"
    expected = hashlib.sha256(token.encode()).hexdigest()
    assert manager._hash_token(token) == expected


def test_hash_token_deterministic(manager):
    """Same token always hashes to the same value."""
    h1 = manager._hash_token("my-secret")
    h2 = manager._hash_token("my-secret")
    assert h1 == h2


def test_hash_token_different_inputs(manager):
    """Different tokens produce different hashes."""
    h1 = manager._hash_token("token-a")
    h2 = manager._hash_token("token-b")
    assert h1 != h2


@patch("services.security.capabilities.secrets.token_urlsafe", return_value="fake-token-value")
def test_issue_returns_token_metadata(MockToken, manager, mock_conn):
    """issue() returns a dict with token, token_id, holder, capabilities, expires_at."""
    cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    caps = [{"resource": "harvest_event", "action": "write"}]
    result = manager.issue(holder="agent-1", capabilities=caps, ttl_seconds=3600)

    assert result["token"] == "fake-token-value"
    assert result["holder"] == "agent-1"
    assert result["capabilities"] == caps
    assert "token_id" in result
    assert "expires_at" in result


@patch("services.security.capabilities.secrets.token_urlsafe", return_value="fake-token-value")
def test_issue_inserts_into_db(MockToken, manager, mock_conn):
    """issue() executes an INSERT and commits."""
    cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    manager.issue(holder="agent-2", capabilities=[{"resource": "metric", "action": "read"}])
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "INSERT INTO capability_token" in sql
    mock_conn.commit.assert_called_once()


def test_verify_returns_none_for_unknown_hash(manager, mock_conn):
    """verify() returns None when the token hash is not in the DB."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    result = manager.verify("unknown-token", resource="harvest_event", action="write")
    assert result is None


def test_verify_returns_none_for_revoked_token(manager, mock_conn):
    """verify() returns None when the token has been revoked."""
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)
    cursor = MagicMock()
    cursor.fetchone.return_value = ("tok-id", "holder", '[{"resource":"harvest_event","action":"write"}]', future, None, True)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    result = manager.verify("some-token", resource="harvest_event", action="write")
    assert result is None


def test_revoke_returns_true_on_success(manager, mock_conn):
    """revoke() returns True when the token was successfully revoked."""
    cursor = MagicMock()
    cursor.fetchone.return_value = ("tok-id",)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    assert manager.revoke("tok-id") is True
    mock_conn.commit.assert_called_once()


def test_revoke_returns_false_on_failure(manager, mock_conn):
    """revoke() returns False when the token is not found."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    assert manager.revoke("nonexistent-tok-id") is False


def test_revoke_by_holder_returns_count(manager, mock_conn):
    """revoke_by_holder() returns the number of tokens revoked."""
    cursor = MagicMock()
    cursor.rowcount = 3
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    count = manager.revoke_by_holder("agent-1")
    assert count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
