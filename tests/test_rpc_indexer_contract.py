"""RPC indexing should close its connection on empty scoped runs and errors."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import rpc_indexer


def test_rpc_cli_scheduler_and_configured_chain_sets_match():
    from services.ingestion.config import CHAIN_RPC_MAP
    from services.security.scheduled_command_contracts import RPC_SCHEDULE_CHAINS

    assert rpc_indexer.RPC_CLI_CHAINS == RPC_SCHEDULE_CHAINS
    assert rpc_indexer.RPC_CLI_CHAINS == tuple(CHAIN_RPC_MAP)


def test_empty_chain_run_closes_database_without_contacting_rpc_provider():
    connection = MagicMock()

    with (
        patch("services.ingestion.rpc_indexer.get_db", return_value=connection),
        patch("services.ingestion.rpc_indexer.get_wallets", return_value=[]) as get_wallets,
        patch("services.ingestion.rpc_indexer.get_web3") as get_web3,
    ):
        rpc_indexer.run(chain="celo-alfajores")

    get_wallets.assert_called_once_with(connection, "celo-alfajores")
    get_web3.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_wallet_lookup_error_rolls_back_and_closes_connection():
    connection = MagicMock()
    secret = "rpc-lookup-secret"

    with (
        patch("services.ingestion.rpc_indexer.get_db", return_value=connection),
        patch(
            "services.ingestion.rpc_indexer.get_wallets",
            side_effect=RuntimeError(f"database URL contained {secret}"),
        ),
        pytest.raises(RuntimeError, match=r"RPC indexer failed \(RuntimeError\)") as error,
    ):
        rpc_indexer.run(chain="celo")

    assert secret not in str(error.value)
    assert error.value.__suppress_context__ is True
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
