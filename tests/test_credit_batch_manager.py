"""Tests for services.credit_class.batch_manager — issuance, retirement, balance."""

from __future__ import annotations

from unittest.mock import MagicMock

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


def _batch_create_connection(*rows):
    conn = MagicMock()
    conn.text = lambda sql: sql
    results = []
    for row in rows:
        result = MagicMock()
        result.mappings.return_value.first.return_value = row
        results.append(result)
    conn.execute.side_effect = results
    return conn


def test_credit_batch_manager_origin_reference_is_persisted_and_indexed():
    from services.credit_class.batch_manager import create_batch

    conn = _batch_create_connection(
        {"id": "class-1"},
        {"methodology": "IPCC"},
        {"name": "Adelphi"},
        {"seq": 1},
        {"id": "batch-1"},
        None,
    )

    result = create_batch(
        conn,
        credit_class_id="class-1",
        location_id="location-1",
        vintage_year=2026,
        total_quantity=10,
        origin_tx_id="0xabc123",
        origin_tx_source="celo",
        origin_tx_contract="0xcontract",
    )

    assert result["origin_tx_id"] == "0xabc123"
    batch_sql, batch_params = conn.execute.call_args_list[4].args
    assert "origin_tx_id" in batch_sql
    assert batch_params["otxid"] == "0xabc123"
    index_sql, index_params = conn.execute.call_args_list[5].args
    assert "INSERT INTO origin_tx_index" in index_sql
    assert index_params == {
        "ccid": "class-1",
        "otxid": "0xabc123",
        "otxsource": "celo",
        "bid": "batch-1",
    }


@pytest.mark.parametrize(
    "origin_values",
    [
        {"origin_tx_id": "tx-only"},
        {"origin_tx_source": "celo-only"},
        {"origin_tx_contract": "contract-only"},
    ],
)
def test_credit_batch_manager_rejects_incomplete_origin_reference_before_database(origin_values):
    from services.credit_class.batch_manager import create_batch

    conn = MagicMock()

    with pytest.raises(ValueError, match="origin_tx"):
        create_batch(
            conn,
            credit_class_id="class-1",
            location_id="location-1",
            vintage_year=2026,
            total_quantity=10,
            **origin_values,
        )

    conn.execute.assert_not_called()


def test_credit_batch_manager_requires_transactional_connection_for_origin_index():
    from services.credit_class.batch_manager import create_batch

    conn = MagicMock()
    conn.autocommit = True

    with pytest.raises(ValueError, match="transactional connection"):
        create_batch(
            conn,
            credit_class_id="class-1",
            location_id="location-1",
            vintage_year=2026,
            total_quantity=10,
            origin_tx_id="tx-1",
            origin_tx_source="celo",
        )

    conn.execute.assert_not_called()


def test_credit_batch_manager_origin_index_conflict_propagates_for_transaction_rollback():
    from services.credit_class.batch_manager import create_batch

    conn = _batch_create_connection(
        {"id": "class-1"},
        {"methodology": "IPCC"},
        {"name": "Adelphi"},
        {"seq": 1},
        {"id": "batch-1"},
    )
    results = list(conn.execute.side_effect)
    results.append(RuntimeError("origin index conflict"))
    conn.execute.side_effect = results

    with pytest.raises(RuntimeError, match="origin index conflict"):
        create_batch(
            conn,
            credit_class_id="class-1",
            location_id="location-1",
            vintage_year=2026,
            total_quantity=10,
            origin_tx_id="tx-1",
            origin_tx_source="celo",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
