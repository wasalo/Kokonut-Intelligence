"""Tests for scope-dependent strategy governance routes."""

import uuid

import pytest

from services.analytics import strategy_governance


def test_dual_route_requires_both_approval_types():
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass
        def fetchall(self): return [("governance_circle",)]
    class Conn:
        def cursor(self, **_): return Cursor()
    assert not strategy_governance.approval_route_satisfied(Conn(), str(uuid.uuid4()), "dual")


def test_invalid_route_is_rejected():
    with pytest.raises(ValueError, match="approval mode"):
        strategy_governance.approval_route_satisfied(None, str(uuid.uuid4()), "invalid")


def test_invalid_record_type_is_rejected():
    with pytest.raises(ValueError, match="record type"):
        strategy_governance.validate_link(None, str(uuid.uuid4()), "unknown", str(uuid.uuid4()))
