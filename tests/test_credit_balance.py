"""Tests for services.credit_class.balance — per-account balance tracking."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _mock_conn():
    """Build a mock connection with chaining .execute().mappings().first() pattern."""
    conn = MagicMock()
    return conn


def _mock_mapping_row(**overrides):
    """Return a MagicMock whose .mappings().first() yields the given dict."""
    defaults = {
        "id": "bal-001",
        "credit_batch_id": "batch-001",
        "account_address": "0x1234",
        "tradable_amount": 100.0,
        "retired_amount": 0.0,
        "escrowed_amount": 0.0,
    }
    defaults.update(overrides)
    row = MagicMock()
    row.__iter__ = lambda self: iter(defaults.items())
    row.__getitem__ = lambda self, key: defaults[key]
    return row


def test_credit_balance_get_balance_returns_default_when_missing():
    from services.credit_class.balance import get_balance

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_balance(conn, "batch-001", "0x1234")

    assert result["tradable_amount"] == 0
    assert result["retired_amount"] == 0
    assert result["escrowed_amount"] == 0
    assert result["credit_batch_id"] == "batch-001"
    assert result["account_address"] == "0x1234"


def test_credit_balance_get_balance_returns_existing():
    from services.credit_class.balance import get_balance

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "tradable_amount": 50.0,
        "retired_amount": 10.0,
        "escrowed_amount": 5.0,
    }

    result = get_balance(conn, "batch-001", "0x1234")

    assert result["tradable_amount"] == 50.0
    assert result["retired_amount"] == 10.0
    assert result["escrowed_amount"] == 5.0


def test_credit_balance_upsert_rejects_negative_without_existing():
    from services.credit_class.balance import upsert_balance

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    with pytest.raises(ValueError, match="Insufficient balance"):
        upsert_balance(conn, "batch-001", "0x1234", tradable_delta=-10)


def test_credit_balance_upsert_success():
    from services.credit_class.balance import upsert_balance

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": "bal-002",
        "tradable_amount": 110.0,
        "retired_amount": 0.0,
        "escrowed_amount": 0.0,
    }

    result = upsert_balance(conn, "batch-001", "0x1234", tradable_delta=10)

    assert result["tradable"] == 110.0
    assert result["id"] == "bal-002"


def test_credit_balance_get_supply_aggregates():
    from services.credit_class.balance import get_supply

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "tradable_supply": 500.0,
        "retired_supply": 100.0,
        "escrowed_supply": 50.0,
    }

    result = get_supply(conn, "batch-001")

    assert result["tradable_supply"] == 500.0
    assert result["retired_supply"] == 100.0
    assert result["escrowed_supply"] == 50.0
    assert result["credit_batch_id"] == "batch-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
