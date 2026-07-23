"""Tests for services.credit_class.params — ecocredit module parameters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_credit_params_get_param_returns_none():
    from services.credit_class.params import get_param

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_param(conn, "nonexistent_key")
    assert result is None


def test_credit_params_get_param_returns_dict():
    from services.credit_class.params import get_param

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "param_key": "class_fee",
        "param_value": '{"denom":"cusd","amount":10}',
    }

    result = get_param(conn, "class_fee")
    assert result["param_key"] == "class_fee"


def test_credit_params_get_params_returns_all():
    from services.credit_class.params import get_params

    conn = MagicMock()
    mock_row1 = MagicMock()
    mock_row1.__getitem__ = lambda self, key: {"param_key": "key1", "param_value": "val1"}[key]
    mock_row2 = MagicMock()
    mock_row2.__getitem__ = lambda self, key: {"param_key": "key2", "param_value": "val2"}[key]
    conn.execute.return_value.mappings.return_value.all.return_value = [mock_row1, mock_row2]

    result = get_params(conn)

    assert "key1" in result
    assert "key2" in result


def test_credit_params_set_param_upserts():
    from services.credit_class.params import set_param

    conn = MagicMock()

    result = set_param(conn, "new_key", "new_value", description="Test param")

    assert result["param_key"] == "new_key"
    assert result["param_value"] == "new_value"
    conn.execute.assert_called()


def test_credit_params_set_param_serializes_dict():
    from services.credit_class.params import set_param

    conn = MagicMock()

    set_param(conn, "config", {"a": 1, "b": 2})

    conn.execute.assert_called()


def test_credit_params_get_class_fee_defaults():
    from services.credit_class.params import get_class_fee

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_class_fee(conn)
    assert result == {"denom": "cusd", "amount": 0}


def test_credit_params_get_allowed_bridge_chains_defaults():
    from services.credit_class.params import get_allowed_bridge_chains

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_allowed_bridge_chains(conn)
    assert "celo" in result
    assert "gnosis" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
