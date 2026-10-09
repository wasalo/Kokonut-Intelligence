"""Tests for snapshot comparison and scheduled review decisions."""

import uuid

import pytest

from services.analytics.strategy_execution import compare_snapshots, complete_review_task


def test_snapshot_comparison_requires_history():
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass
        def fetchall(self): return []
    class Conn:
        def cursor(self, **_): return Cursor()
    assert compare_snapshots(Conn(), str(uuid.uuid4()))["available"] is False


def test_invalid_review_decision_is_rejected():
    with pytest.raises(ValueError, match="review decision"):
        complete_review_task(None, str(uuid.uuid4()), str(uuid.uuid4()), "invalid")


def test_calculate_variance_returns_percentage():
    from services.analytics.strategy_execution import calculate_variance
    result = calculate_variance(100, 125)
    assert result["variance_pct"] == 25.0
    assert result["variance_value"] == 25.0
    assert result["status"] == "warning"


def test_calculate_variance_within_tolerance():
    from services.analytics.strategy_execution import calculate_variance
    result = calculate_variance(100, 105)
    assert result["status"] == "within_tolerance"
    assert result["variance_pct"] == 5.0


def test_calculate_variance_breach_threshold():
    from services.analytics.strategy_execution import calculate_variance
    result = calculate_variance(100, 130)
    assert result["status"] == "breach"
    assert result["variance_pct"] == 30.0
