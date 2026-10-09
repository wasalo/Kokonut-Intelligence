"""Tests for services.cache.cache — ComputationCache."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.cache.cache import ComputationCache


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    return conn


@pytest.fixture
def cache(mock_conn):
    return ComputationCache(conn=mock_conn, default_ttl_seconds=3600)


def test_cache_make_key_deterministic(cache):
    """Same inputs always produce the same cache key."""
    key1 = cache._make_key("analytics", "loc-123", {"metric": "yield"})
    key2 = cache._make_key("analytics", "loc-123", {"metric": "yield"})
    assert key1 == key2
    assert key1.startswith("analytics:loc-123:")


def test_cache_make_key_global_fallback(cache):
    """None location_id maps to 'global' segment."""
    key = cache._make_key("crisp", None, {})
    assert key.startswith("crisp:global:")


def test_cache_get_returns_none_on_miss(cache, mock_conn):
    """Cache miss returns None without error."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    result = cache.get("analytics", "loc-1", {"x": 1})
    assert result is None


def test_cache_get_returns_none_on_expired(cache, mock_conn):
    """Expired entry is marked invalid and returns None."""
    now = datetime.now(timezone.utc)
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        "entry-id-1", '{"value": 42}', now - timedelta(hours=2), now - timedelta(hours=1), 5
    )
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    result = cache.get("analytics", "loc-1", {"x": 1})
    assert result is None
    # Should have issued the expiration UPDATE
    assert cursor.execute.call_count >= 2


def test_cache_set_returns_key(cache, mock_conn):
    """set() returns a cache key string on success."""
    cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    key = cache.set(
        "analytics", {"value": 99}, location_id="loc-1", parameters={"x": 1}
    )
    assert isinstance(key, str)
    assert "analytics:loc-1:" in key
    mock_conn.commit.assert_called_once()


def test_cache_invalidate_returns_count(cache, mock_conn):
    """invalidate() returns the number of rows affected."""
    cursor = MagicMock()
    cursor.rowcount = 3
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    count = cache.invalidate(computation_type="analytics")
    assert count == 3


def test_cache_stats_returns_dict(cache, mock_conn):
    """stats() returns a dictionary with expected keys."""
    cursor = MagicMock()
    cursor.fetchone.return_value = (10, 8, 2, 50, 5.0, 1024, 1)
    cursor.fetchall.return_value = [("analytics", 5, 30)]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    result = cache.stats()
    assert "total_entries" in result
    assert result["total_entries"] == 10
    assert result["by_type"][0]["type"] == "analytics"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
