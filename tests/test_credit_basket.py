"""Tests for services.credit_class.basket — deposit credits for fungible basket tokens."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_credit_basket_denom_computation():
    from services.credit_class.basket import _compute_basket_denom

    # exponent 6 maps to SI prefix "u" in the SI_PREFIX_MAP
    denom = _compute_basket_denom("voluntary", "C", 6)
    assert denom == "eco.uC.voluntary"


def test_credit_basket_token_amount_computation():
    from services.credit_class.basket import _compute_token_amount, _compute_credit_amount

    tokens = _compute_token_amount(100.0, 6)
    assert tokens == 100_000_000.0

    credits = _compute_credit_amount(100_000_000.0, 6)
    assert credits == 100.0


def test_credit_basket_create_basket_inserts_record():
    from services.credit_class.basket import create_basket

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"id": "basket-001"}

    result = create_basket(conn, "Carbon Basket", credit_type_abbrev="C", exponent=6)

    assert result["id"] == "basket-001"
    assert result["name"] == "Carbon Basket"
    conn.execute.assert_called()


def test_credit_basket_deposit_rejects_inactive_basket():
    from services.credit_class.basket import deposit_credits

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "status": "paused",
        "exponent": 6,
    }

    with pytest.raises(ValueError, match="not active"):
        deposit_credits(conn, "basket-001", "batch-001", "0x1234", 100.0)


def test_credit_basket_deposit_rejects_zero_quantity():
    from services.credit_class.basket import deposit_credits

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "status": "active",
        "exponent": 6,
    }

    with pytest.raises(ValueError, match="positive"):
        deposit_credits(conn, "basket-001", "batch-001", "0x1234", 0)


def test_credit_basket_get_token_balance_defaults_to_zero():
    from services.credit_class.basket import get_token_balance

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_token_balance(conn, "basket-001", "0x1234")

    assert result["token_amount"] == 0
    assert result["basket_id"] == "basket-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
