"""Tests for services.credit_class.batch_manager — issuance, retirement, balance."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_credit_batch_manager_get_batch_returns_none():
    from services.credit_class.batch_manager import get_batch

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_batch(conn, "batch-001")
    assert result is None


def test_credit_batch_manager_get_batch_returns_dict():
    from services.credit_class.batch_manager import get_batch

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": "batch-001",
        "batch_code": "CC-IPCC-2026-ADEL-0001",
        "status": "published",
        "total_quantity": 100.0,
        "issued_quantity": 100.0,
        "retired_quantity": 10.0,
        "cancelled_quantity": 0.0,
        "available_quantity": 90.0,
        "unit": "tonneCO2e",
    }

    result = get_batch(conn, "batch-001")
    assert result["batch_code"] == "CC-IPCC-2026-ADEL-0001"
    assert result["total_quantity"] == 100.0


def test_credit_batch_manager_issue_batch_rejects_non_verified():
    from services.credit_class.batch_manager import issue_batch

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "status": "draft",
        "credit_class_id": "cc-001",
        "total_quantity": 100.0,
        "batch_code": "BATCH-001",
    }

    with pytest.raises(ValueError, match="must be verified"):
        issue_batch(conn, "batch-001", "0xIssuer")


def test_credit_batch_manager_issue_batch_rejects_unauthorized_issuer():
    from services.credit_class.batch_manager import issue_batch

    conn = MagicMock()
    first_call = True

    def side_effect(*args, **kwargs):
        nonlocal first_call
        mock = MagicMock()
        if first_call:
            first_call = False
            mock.mappings.return_value.first.return_value = {
                "status": "verified",
                "credit_class_id": "cc-001",
                "total_quantity": 100.0,
                "batch_code": "BATCH-001",
            }
        else:
            mock.mappings.return_value.first.return_value = None
        return mock

    conn.execute.side_effect = side_effect

    with pytest.raises(ValueError, match="not authorized"):
        issue_batch(conn, "batch-001", "0xUnauthorized")


def test_credit_batch_manager_get_batch_balance():
    from services.credit_class.batch_manager import get_batch_balance

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "batch_code": "BATCH-001",
        "total_quantity": 200.0,
        "issued_quantity": 200.0,
        "retired_quantity": 50.0,
        "cancelled_quantity": 0.0,
        "available_quantity": 150.0,
        "unit": "tonneCO2e",
    }

    result = get_batch_balance(conn, "batch-001")
    assert result["available_quantity"] == 150.0
    assert result["batch_code"] == "BATCH-001"


def test_credit_batch_manager_list_batches_returns_list():
    from services.credit_class.batch_manager import list_batches

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    result = list_batches(conn)
    assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
