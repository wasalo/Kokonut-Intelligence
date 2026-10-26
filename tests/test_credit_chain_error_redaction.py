"""Keep provider exception details out of credit-chain responses and logs."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

SECRET = "provider returned https://user:password@example.invalid/private?token=secret"


def _query_result(*, first=None, all_rows=None):
    result = MagicMock()
    result.mappings.return_value.first.return_value = first
    result.mappings.return_value.all.return_value = all_rows or []
    return result


def _assert_no_secret(logger: MagicMock) -> None:
    assert SECRET not in repr(logger.mock_calls)


def test_issue_batch_returns_bounded_chain_sync_error(monkeypatch):
    from services.credit_class import batch_manager, chain_sync

    conn = MagicMock()
    conn.execute.side_effect = [
        _query_result(
            first={
                "id": "batch-1",
                "status": "verified",
                "credit_class_id": "class-1",
                "total_quantity": 10,
                "batch_code": "BATCH-1",
            },
        ),
        _query_result(first={"authorized": True}),
        MagicMock(),
    ]
    monkeypatch.setattr("services.credit_class.balance.upsert_balance", MagicMock())
    monkeypatch.setattr(chain_sync, "sync_credits_to_chain", MagicMock(side_effect=RuntimeError(SECRET)))
    logger = MagicMock()
    monkeypatch.setattr(batch_manager, "logger", logger)

    result = batch_manager.issue_batch(conn, "batch-1", "0xIssuer")

    assert result["status"] == "published"
    assert result["chain_sync"]["error"] == "on-chain sync failed (RuntimeError)"
    assert SECRET not in repr(result)
    _assert_no_secret(logger)


def test_mint_failure_logs_only_exception_class(monkeypatch):
    from services.credit_class import chain_sync

    conn = MagicMock()
    conn.execute.side_effect = [
        _query_result(first={"batch_code": "BATCH-1", "vintage_year": 2026}),
        _query_result(all_rows=[{"account_address": "0xRecipient", "tradable_amount": 10, "retired_amount": 0}]),
        _query_result(first={"contract_address": "0xContract"}),
        _query_result(first={"next_serial": 1}),
    ]
    web3 = MagicMock()
    account = MagicMock()
    contract = MagicMock()
    contract.functions.issue.return_value.build_transaction.side_effect = RuntimeError(SECRET)
    logger = MagicMock()
    monkeypatch.setattr(chain_sync, "ENABLED", True)
    monkeypatch.setattr(chain_sync, "logger", logger)
    monkeypatch.setattr(chain_sync, "_get_web3_and_contract", lambda **_kwargs: (web3, account, contract))
    monkeypatch.setattr(chain_sync, "_batch_id_to_bytes32", lambda _code: bytes(32))
    monkeypatch.setattr(chain_sync, "_compute_token_id", lambda *_args: 1)

    with pytest.raises(RuntimeError, match=r"on-chain mint failed \(RuntimeError\)") as error:
        chain_sync.sync_credits_to_chain(conn, "batch-1")

    assert SECRET not in str(error.value)
    _assert_no_secret(logger)
    assert "RuntimeError" in repr(logger.mock_calls)


def test_retirement_failure_logs_only_exception_class(monkeypatch):
    from services.credit_class import chain_sync

    conn = MagicMock()
    conn.execute.side_effect = [
        _query_result(
            first={
                "id": "retirement-1",
                "credit_id": "credit-1",
                "retired_tonnes": 1,
                "retirement_reason": "verified retirement",
            },
        ),
        _query_result(first={"id": "credit-1", "credit_batch_id": "batch-1", "vintage_year": 2026}),
        _query_result(first={"contract_address": "0xContract"}),
        _query_result(first={"token_id": 1}),
    ]
    web3 = MagicMock()
    account = MagicMock()
    contract = MagicMock()
    contract.functions.retire.return_value.build_transaction.side_effect = RuntimeError(SECRET)
    logger = MagicMock()
    monkeypatch.setattr(chain_sync, "ENABLED", True)
    monkeypatch.setattr(chain_sync, "logger", logger)
    monkeypatch.setattr(chain_sync, "_get_web3_and_contract", lambda **_kwargs: (web3, account, contract))

    with pytest.raises(RuntimeError, match=r"on-chain retirement failed \(RuntimeError\)") as error:
        chain_sync.retire_onchain(conn, "retirement-1")

    assert SECRET not in str(error.value)
    _assert_no_secret(logger)
    assert "RuntimeError" in repr(logger.mock_calls)


def test_balance_query_failure_logs_only_exception_class(monkeypatch):
    from services.credit_class import chain_sync

    conn = MagicMock()
    conn.execute.side_effect = [
        _query_result(first={"tradable_amount": 10, "retired_amount": 0}),
        _query_result(first={"contract_address": "0xContract"}),
    ]
    web3 = MagicMock()
    web3.to_checksum_address.side_effect = lambda address: address
    contract = MagicMock()
    contract.functions.balanceOf.return_value.call.side_effect = RuntimeError(SECRET)
    logger = MagicMock()
    monkeypatch.setattr(chain_sync, "ENABLED", True)
    monkeypatch.setattr(chain_sync, "logger", logger)
    monkeypatch.setattr(chain_sync, "_get_web3_and_contract", lambda **_kwargs: (web3, MagicMock(), contract))

    result = chain_sync.verify_chain_balance(conn, token_id=1, account="0xAccount")

    assert result["chain_balance"] == 0
    assert result["match"] is False
    assert result["chain_query_failed"] is True
    assert result["chain_query_error"] == "chain balance query failed (RuntimeError)"
    assert SECRET not in repr(result)
    _assert_no_secret(logger)
    assert "RuntimeError" in repr(logger.mock_calls)


def test_rpc_initialization_failure_omits_endpoint(monkeypatch):
    from services.credit_class import chain_sync
    from services.ingestion import config

    class _Web3:
        @staticmethod
        def HTTPProvider(url):
            assert url == SECRET
            return url

        def __init__(self, provider):
            self.provider = provider

        def is_connected(self):
            raise RuntimeError(SECRET)

    web3_module = ModuleType("web3")
    web3_module.Web3 = _Web3
    account_module = ModuleType("eth_account")
    account_module.Account = MagicMock()
    monkeypatch.setitem(sys.modules, "web3", web3_module)
    monkeypatch.setitem(sys.modules, "eth_account", account_module)
    monkeypatch.setattr(config, "CHAIN_RPC_MAP", {"celo": SECRET})

    with pytest.raises(ConnectionError, match=r"Could not initialize celo RPC client \(RuntimeError\)") as error:
        chain_sync._get_web3_and_contract("celo", private_key="not-used")

    assert SECRET not in str(error.value)
    assert error.value.__suppress_context__
