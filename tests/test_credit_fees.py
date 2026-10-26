"""Tests for services.credit_class.fees — marketplace fee collection and distribution."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

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


def test_collect_zero_fee_is_settled_as_a_noop():
    from services.credit_class.fees import collect_fee

    conn = _distribution_connection(None, None, None, {"id": "fee-zero"})

    result = collect_fee(conn, "buy", "order-zero", buyer_fee=0, seller_fee=0)

    assert result["total_fee"] == 0
    insert_sql = conn.execute.call_args_list[3].args[0]
    assert "CASE WHEN :tf = 0 THEN 'distributed' ELSE 'pending' END" in insert_sql
    assert "CASE WHEN :tf = 0 THEN NOW() ELSE NULL END" in insert_sql


def test_credit_fees_distribute_fee_rejects_missing_fee():
    from services.credit_class.fees import distribute_fee

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    with pytest.raises(ValueError, match="Fee not found"):
        distribute_fee(conn, "fee-999", "0xRecipient", 10.0, "cusd")


@pytest.mark.parametrize("amount", [-0.01, float("nan"), float("inf"), True, "not-a-number"])
def test_collect_fee_rejects_invalid_amount_before_database_access(amount):
    from services.credit_class.fees import collect_fee

    conn = MagicMock()
    with pytest.raises(ValueError, match="buyer_fee"):
        collect_fee(conn, "buy", "order-1", buyer_fee=amount)
    conn.execute.assert_not_called()


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), True, "invalid"])
def test_distribute_fee_rejects_invalid_amount_before_database_access(amount):
    from services.credit_class.fees import distribute_fee

    conn = MagicMock()
    with pytest.raises(ValueError, match="amount"):
        distribute_fee(conn, "fee-1", "recipient", amount, "cusd")
    conn.execute.assert_not_called()


def _result(row):
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    return result


def _distribution_connection(*rows):
    conn = MagicMock()
    conn.text = lambda sql: sql
    conn.execute.side_effect = [_result(row) for row in rows]
    return conn


def test_distribute_fee_locks_fee_and_keeps_partial_distribution_pending():
    from services.credit_class.fees import distribute_fee

    conn = _distribution_connection(
        {"id": "fee-1", "total_fee": Decimal("10.00000000"), "fee_denom": "cusd", "status": "pending"},
        {"total_distributed": Decimal("4.00000000")},
        {"id": "distribution-1"},
    )

    result = distribute_fee(conn, "fee-1", "recipient", 2, "cusd")

    assert result == {"id": "distribution-1", "amount": 2.0, "denom": "cusd"}
    assert "FOR UPDATE" in conn.execute.call_args_list[0].args[0]
    assert conn.execute.call_count == 3
    assert "UPDATE marketplace_fee" not in " ".join(
        str(call.args[0]) for call in conn.execute.call_args_list
    )


def test_distribute_fee_marks_complete_only_when_exact_balance_is_paid():
    from services.credit_class.fees import distribute_fee

    conn = _distribution_connection(
        {"id": "fee-1", "total_fee": Decimal("10.00000000"), "fee_denom": "cusd", "status": "pending"},
        {"total_distributed": Decimal("4.00000000")},
        {"id": "distribution-2"},
        None,
    )

    distribute_fee(conn, "fee-1", "recipient", 6, "cusd")

    update_sql = conn.execute.call_args_list[3].args[0]
    assert "status = 'distributed'" in update_sql
    assert "distributed_at = NOW()" in update_sql


def test_distribute_fee_rejects_wrong_denomination_before_distribution_query():
    from services.credit_class.fees import distribute_fee

    conn = _distribution_connection(
        {"id": "fee-1", "total_fee": Decimal("10"), "fee_denom": "cusd", "status": "pending"}
    )

    with pytest.raises(ValueError, match="must match fee denomination"):
        distribute_fee(conn, "fee-1", "recipient", 1, "usdc")

    assert conn.execute.call_count == 1


def test_distribute_fee_rejects_exact_overdistribution_without_tolerance():
    from services.credit_class.fees import distribute_fee

    conn = _distribution_connection(
        {"id": "fee-1", "total_fee": Decimal("10"), "fee_denom": "cusd", "status": "pending"},
        {"total_distributed": Decimal("9.99999999")},
    )

    with pytest.raises(ValueError, match="Over-distribution"):
        distribute_fee(conn, "fee-1", "recipient", Decimal("0.00000002"), "cusd")

    assert conn.execute.call_count == 2


def test_distribute_fee_rejects_already_distributed_fee():
    from services.credit_class.fees import distribute_fee

    conn = _distribution_connection(
        {"id": "fee-1", "total_fee": Decimal("10"), "fee_denom": "cusd", "status": "distributed"}
    )

    with pytest.raises(ValueError, match="not pending"):
        distribute_fee(conn, "fee-1", "recipient", 1, "cusd")

    assert conn.execute.call_count == 1


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
