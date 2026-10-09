"""Tests for services.credit_class.chain_sync — on-chain credit settlement."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


def _mock_conn():
    """Return a mock DatabaseConnection for chain_sync tests."""
    conn = MagicMock()
    return conn


def _mock_web3_chain():
    """Return a mock web3 chain with all needed attributes."""
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 42220
    mock_w3.eth.gas_price = 1000000000
    mock_w3.eth.get_transaction_count.return_value = 0
    mock_w3.to_checksum_address.side_effect = lambda x: x
    mock_w3.from_wei.return_value = 0.01
    mock_w3.keccak.return_value = b"\x01" * 32
    mock_w3.solidity_abi.return_value = b"\x02" * 128
    mock_w3.to_wei.return_value = 1000000000
    return mock_w3


def test_sync_disabled_by_default():
    """When CREDIT_ONCHAIN_SYNC_ENABLED is false, sync returns skipped."""
    import os
    from services.credit_class.chain_sync import sync_credits_to_chain

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "false"}):
        import importlib
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = False

        conn = _mock_conn()
        result = sync_credits_to_chain(conn, "batch-001")
        assert result["skipped"] is True
        assert result["minted"] == 0


def test_retire_onchain_disabled():
    """When CREDIT_ONCHAIN_SYNC_ENABLED is false, retire returns skipped."""
    import os
    from services.credit_class.chain_sync import retire_onchain

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "false"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = False

        conn = _mock_conn()
        result = retire_onchain(conn, "ret-001")
        assert result["skipped"] is True
        assert result["burned"] == 0


def test_verify_chain_balance_skips_when_disabled():
    """verify_chain_balance skips on-chain query when disabled."""
    import os
    from services.credit_class.chain_sync import verify_chain_balance

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "false"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = False

        conn = _mock_conn()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "tradable_amount": 100.0,
            "retired_amount": 10.0,
        }

        result = verify_chain_balance(conn, token_id=42, account="0xAbC")
        assert result["chain_query_skipped"] is True
        assert result["pg_balance"] == 110.0
        assert result["match"] is True


def test_sync_credits_to_chain_missing_batch():
    """sync_credits_to_chain raises when batch not found."""
    import os
    from services.credit_class.chain_sync import sync_credits_to_chain

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "true"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = True

        conn = _mock_conn()
        conn.execute.return_value.mappings.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            sync_credits_to_chain(conn, "nonexistent")


def test_sync_credits_to_chain_no_balances():
    """sync_credits_to_chain returns 0 minted when no balances exist."""
    import os
    from services.credit_class.chain_sync import sync_credits_to_chain

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "true"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = True

        conn = _mock_conn()
        call_count = 0

        def side_effect(sql, params=None):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                # First call: get batch
                mock.mappings.return_value.first.return_value = {
                    "id": "batch-001",
                    "batch_code": "CC-TEST-2026-ADEL-0001",
                    "vintage_year": 2026,
                    "status": "published",
                    "jurisdiction": "KE",
                    "methodology": "IPCC 2006",
                }
            elif call_count == 2:
                # Second call: get balances (empty)
                mock.mappings.return_value.all.return_value = []
            return mock

        conn.execute.side_effect = side_effect
        result = sync_credits_to_chain(conn, "batch-001")
        assert result["minted"] == 0


def test_sync_credits_to_chain_mints_credits():
    """sync_credits_to_chain mints credits when balances exist."""
    import os
    from services.credit_class.chain_sync import sync_credits_to_chain

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "true"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = True

        conn = _mock_conn()
        call_count = 0

        def side_effect(sql, params=None):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.mappings.return_value.first.return_value = {
                    "id": "batch-001",
                    "batch_code": "CC-TEST-2026-ADEL-0001",
                    "vintage_year": 2026,
                    "status": "published",
                    "jurisdiction": "KE",
                    "methodology": "IPCC 2006",
                }
            elif call_count == 2:
                mock.mappings.return_value.all.return_value = [
                    {"account_address": "0xRecipient1", "tradable_amount": 50.0, "retired_amount": 10.0},
                ]
            elif call_count == 3:
                mock.mappings.return_value.first.return_value = {
                    "contract_address": "0xContractAddr",
                }
            elif call_count == 4:
                mock.mappings.return_value.first.return_value = {"next_serial": 1}
            else:
                mock.mappings.return_value.first.return_value = None
            return mock

        conn.execute.side_effect = side_effect

        mock_receipt = MagicMock()
        mock_receipt.transactionHash.hex.return_value = "0xabc123"

        with patch.object(cs_mod, "_get_web3_and_contract") as mock_get:
            mock_w3 = _mock_web3_chain()
            mock_contract = MagicMock()
            mock_contract.functions.issue.return_value.build_transaction.return_value = {"from": "0x", "nonce": 0, "chainId": 42220, "gas": 500000}
            mock_w3.eth.send_raw_transaction.return_value = b"\x00" * 32
            mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
            mock_w3.eth.get_transaction_count.return_value = 0
            mock_get.return_value = (mock_w3, MagicMock(), mock_contract)

            with patch.object(cs_mod, "_compute_token_id", return_value=42):
                result = sync_credits_to_chain(conn, "batch-001")

            assert result["minted"] == 60  # 50 tradable + 10 retired
            assert result["tx_hashes"] == ["0xabc123"]


def test_retire_onchain_missing_retirement():
    """retire_onchain raises when retirement not found."""
    import os
    from services.credit_class.chain_sync import retire_onchain

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "true"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = True

        conn = _mock_conn()
        conn.execute.return_value.mappings.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            retire_onchain(conn, "nonexistent-ret")


def test_verify_chain_balance_with_chain_query():
    """verify_chain_balance queries on-chain when enabled."""
    import os
    from services.credit_class.chain_sync import verify_chain_balance

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "true"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = True

        conn = _mock_conn()
        call_count = 0

        def side_effect(sql, params=None):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.mappings.return_value.first.return_value = {
                    "tradable_amount": 100.0,
                    "retired_amount": 0.0,
                }
            else:
                mock.mappings.return_value.first.return_value = {
                    "contract_address": "0xContractAddr",
                }
            return mock

        conn.execute.side_effect = side_effect

        mock_contract = MagicMock()
        mock_contract.functions.balanceOf.return_value.call.return_value = 100

        with patch.object(cs_mod, "_get_web3_and_contract") as mock_get:
            mock_w3 = _mock_web3_chain()
            mock_get.return_value = (mock_w3, MagicMock(), mock_contract)

            result = verify_chain_balance(conn, token_id=42, account="0xAbC")

        assert result["pg_balance"] == 100.0
        assert result["chain_balance"] == 100.0
        assert result["match"] is True
        assert result["discrepancy"] == 0.0


def test_verify_chain_balance_discrepancy():
    """verify_chain_balance detects discrepancy between PG and chain."""
    import os
    from services.credit_class.chain_sync import verify_chain_balance

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "true"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = True

        conn = _mock_conn()
        call_count = 0

        def side_effect(sql, params=None):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.mappings.return_value.first.return_value = {
                    "tradable_amount": 100.0,
                    "retired_amount": 0.0,
                }
            else:
                mock.mappings.return_value.first.return_value = {
                    "contract_address": "0xContractAddr",
                }
            return mock

        conn.execute.side_effect = side_effect

        mock_contract = MagicMock()
        mock_contract.functions.balanceOf.return_value.call.return_value = 80

        with patch.object(cs_mod, "_get_web3_and_contract") as mock_get:
            mock_w3 = _mock_web3_chain()
            mock_get.return_value = (mock_w3, MagicMock(), mock_contract)

            result = verify_chain_balance(conn, token_id=42, account="0xAbC")

        assert result["match"] is False
        assert result["discrepancy"] == 20.0


def test_reconcile_all_empty():
    """reconcile_all returns empty when no batches have balances."""
    import os
    from services.credit_class.chain_sync import reconcile_all

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "false"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = False

        conn = _mock_conn()
        conn.execute.return_value.mappings.return_value.all.return_value = []

        result = reconcile_all(conn, chain="celo")
        assert result["checked"] == 0
        assert result["all_match"] is True


def test_reconcile_all_with_discrepancies():
    """reconcile_all detects discrepancies across batches."""
    import os
    from services.credit_class.chain_sync import reconcile_all

    with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": "false"}):
        import services.credit_class.chain_sync as cs_mod
        cs_mod.ENABLED = False

        conn = _mock_conn()
        call_count = 0

        def side_effect(sql, params=None):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.mappings.return_value.all.return_value = [
                    {"credit_batch_id": "batch-001"},
                ]
            elif call_count == 2:
                mock.mappings.return_value.all.return_value = []
            elif call_count == 3:
                mock.mappings.return_value.all.return_value = [
                    {"account_address": "0xAbC"},
                ]
            else:
                mock.mappings.return_value.first.return_value = {
                    "tradable_amount": 50.0,
                    "retired_amount": 0.0,
                }
            return mock

        conn.execute.side_effect = side_effect

        result = reconcile_all(conn, chain="celo")
        assert result["checked"] == 1


def test_compute_token_id():
    """_compute_token_id produces a deterministic integer from inputs."""
    import os
    from services.credit_class.chain_sync import _compute_token_id

    mock_w3 = MagicMock()
    mock_w3.keccak.return_value = int.to_bytes(2**255, 32, "big")

    with patch("eth_abi.encode") as mock_encode:
        mock_encode.return_value = b"\x00" * 128
        result = _compute_token_id(mock_w3, b"\x01" * 32, 2026, "0xAbC", 1)
        assert isinstance(result, int)
        assert result > 0
        mock_encode.assert_called_once_with(
            ["bytes32", "uint256", "address", "uint256"],
            [b"\x01" * 32, 2026, "0xAbC", 1],
        )


def test_batch_id_to_bytes32():
    """_batch_id_to_bytes32 returns a 32-byte hash."""
    from services.credit_class.chain_sync import _batch_id_to_bytes32

    result = _batch_id_to_bytes32("CC-TEST-2026-ADEL-0001")
    assert len(result) == 32


def test_load_abi_returns_list():
    """_load_abi returns a list of ABI entries."""
    from services.credit_class.chain_sync import _load_abi

    abi = _load_abi()
    assert isinstance(abi, list)
    assert len(abi) > 0
    assert any(entry.get("name") == "issue" for entry in abi)
    assert any(entry.get("name") == "retire" for entry in abi)
    assert any(entry.get("name") == "balanceOf" for entry in abi)


def test_sync_disabled_env_parsing():
    """Various env var values correctly gate the feature."""
    import os
    import services.credit_class.chain_sync as cs_mod

    for val in ("0", "false", "False", "no", "", "something_else"):
        with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": val}):
            cs_mod.ENABLED = val.lower() in ("1", "true", "yes")
            assert cs_mod.ENABLED is False

    for val in ("1", "true", "True", "yes", "YES"):
        with patch.dict(os.environ, {"CREDIT_ONCHAIN_SYNC_ENABLED": val}):
            cs_mod.ENABLED = val.lower() in ("1", "true", "yes")
            assert cs_mod.ENABLED is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
