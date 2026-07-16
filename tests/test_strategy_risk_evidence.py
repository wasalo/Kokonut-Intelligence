"""Tests for strategy risk evidence validation."""

import uuid

import pytest

from services.planning import strategy_allocation


def test_risk_refresh_requires_an_existing_investment():
    with pytest.raises(ValueError, match="investment case"):
        strategy_allocation.refresh_risk_evidence(None, str(uuid.uuid4()))
