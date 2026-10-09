"""Tests for strategy risk evidence validation."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from services.planning import strategy_allocation


def test_risk_refresh_requires_an_existing_investment():
    with pytest.raises(ValueError, match="investment case"):
        strategy_allocation.refresh_risk_evidence(None, str(uuid.uuid4()))


def test_risk_refresh_requires_connection():
    with pytest.raises(ValueError, match="connection is required"):
        strategy_allocation.refresh_risk_evidence(None, str(uuid.uuid4()))


def test_risk_refresh_sets_missing_when_no_crisp():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_row = {
        "location_id": str(uuid.uuid4()),
        "crisp_assessment_id": None,
        "risk_mitigation_id": None,
        "composite_score": None,
        "methodology_version": None,
        "confidence_level": None,
        "crisp_status": None,
        "mitigation_status": None,
    }
    mock_cursor.fetchone.side_effect = [mock_row, {"risk_evidence_status": "missing", "id": str(uuid.uuid4())}]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = strategy_allocation.refresh_risk_evidence(mock_conn, str(uuid.uuid4()))
    assert result["risk_evidence_status"] == "missing"


def test_risk_refresh_verifies_when_both_published():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_row = {
        "location_id": str(uuid.uuid4()),
        "crisp_assessment_id": str(uuid.uuid4()),
        "risk_mitigation_id": str(uuid.uuid4()),
        "composite_score": 75.0,
        "methodology_version": "v2026.01",
        "confidence_level": "high",
        "crisp_status": "published",
        "mitigation_status": "verified",
    }
    mock_cursor.fetchone.side_effect = [mock_row, {"risk_evidence_status": "verified", "id": str(uuid.uuid4())}]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = strategy_allocation.refresh_risk_evidence(mock_conn, str(uuid.uuid4()))
    assert result["risk_evidence_status"] == "verified"


def test_risk_refresh_provisional_when_partial_verification():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_row = {
        "location_id": str(uuid.uuid4()),
        "crisp_assessment_id": str(uuid.uuid4()),
        "risk_mitigation_id": str(uuid.uuid4()),
        "composite_score": 50.0,
        "methodology_version": "v2026.01",
        "confidence_level": "moderate",
        "crisp_status": "verified",
        "mitigation_status": "draft",
    }
    mock_cursor.fetchone.side_effect = [mock_row, {"risk_evidence_status": "provisional", "id": str(uuid.uuid4())}]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = strategy_allocation.refresh_risk_evidence(mock_conn, str(uuid.uuid4()))
    assert result["risk_evidence_status"] == "provisional"
