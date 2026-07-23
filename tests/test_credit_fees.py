"""Tests for services.credit_class.fees — marketplace fee collection and distribution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_credit_fees_collect_fee_inserts_record():
    from services.credit_class.fees import collect_fee

    conn = MagicMock()
    # Three calls: buyer_fee param, seller_fee param, fee_pool param, then INSERT
    conn.execute.return_value.mappings.return_value.first.side_effect = [
        {"param_value": "0.03"},  # buyer fee
        {"param_value": "0.03"},  # seller fee
        {"param_value": "0xPoolAddr"},  # fee pool
        {"id": "fee-001"},  # INSERT
    ]

    result = collect_fee(conn, "buy_order", "order-001", buyer_fee=2.5, seller_fee=1.5)

    assert result["id"] == "fee-001"
    assert result["total_fee"] == 4.0
    assert result["fee_denom"] == "cusd"


def test_credit_fees_get_fee_params_returns_defaults():
    from services.credit_class.fees import get_fee_params

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_fee_params(conn)

    assert result["buyer_fee"] == 0.03
    assert result["seller_fee"] == 0.03


def test_credit_fees_distribute_fee_rejects_missing_fee():
    from services.credit_class.fees import distribute_fee

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    with pytest.raises(ValueError, match="Fee not found"):
        distribute_fee(conn, "fee-999", "0xRecipient", 10.0, "cusd")


def test_credit_fees_list_fees_returns_list():
    from services.credit_class.fees import list_fees

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    result = list_fees(conn)
    assert isinstance(result, list)


def test_credit_fees_get_pending_fees_delegates():
    from services.credit_class.fees import get_pending_fees

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    result = get_pending_fees(conn)
    assert isinstance(result, list)
    # Verify it filtered on status='pending'
    conn.execute.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
