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
