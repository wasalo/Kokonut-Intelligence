"""Wallet/signer management for EAS attestation transactions."""

from __future__ import annotations

import threading
from typing import Any

from web3 import Web3
from web3.middleware import SignAndSendRawMiddlewareBuilder
from eth_account import Account
from eth_account.signers.local import LocalAccount

from .config import ATTESTER_PRIVATE_KEY, get_chain_config


class EASSigner:
    """Manages a web3 signer for EAS transactions."""

    def __init__(self, chain: str, private_key: str | None = None):
        config = get_chain_config(chain)
        self.chain = chain
        self.chain_id = config["chain_id"]
        self.w3 = Web3(Web3.HTTPProvider(config["rpc_url"]))

        key = private_key or ATTESTER_PRIVATE_KEY
        if not key:
            raise ValueError("No private key provided. Set ATTESTER_PRIVATE_KEY env var or pass private_key.")

        self.account: LocalAccount = Account.from_key(key)
        self.w3.middleware_onion.inject(
            SignAndSendRawMiddlewareBuilder.build(self.account),
            layer=0,
        )

        self._nonce_lock = threading.Lock()
        self._pending_nonce: int | None = None

    @property
    def address(self) -> str:
        """Return the checksummed attester address."""
        return self.account.address

    def is_connected(self) -> bool:
        """Check if the web3 provider is connected."""
        return self.w3.is_connected()

    def get_balance(self) -> int:
        """Return the native token balance in wei."""
        return self.w3.eth.get_balance(self.address)

    def get_balance_eth(self) -> float:
        """Return the native token balance in human-readable units."""
        return float(self.w3.from_wei(self.get_balance(), "ether"))

    def get_nonce(self) -> int:
        """Return the next nonce, caching to avoid race conditions on concurrent calls."""
        with self._nonce_lock:
            if self._pending_nonce is None:
                self._pending_nonce = self.w3.eth.get_transaction_count(self.address)
            nonce = self._pending_nonce
            self._pending_nonce += 1
            return nonce

    def reset_nonce(self) -> None:
        """Reset the cached nonce (e.g. after a transaction fails)."""
        with self._nonce_lock:
            self._pending_nonce = None

    def estimate_and_send(self, tx: dict[str, Any]) -> Any:
        """Estimate gas, then sign and send a transaction.

        Uses cached nonce from get_nonce(). Resets on failure.
        """
        tx["from"] = self.address
        tx["nonce"] = self.get_nonce()
        if "chainId" not in tx:
            tx["chainId"] = self.chain_id

        gas_estimate = self.w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas_estimate * 1.2)

        if "maxFeePerGas" not in tx and "gasPrice" not in tx:
            try:
                block = self.w3.eth.get_block("latest")
                if "baseFeePerGas" in block:
                    base_fee = block["baseFeePerGas"]
                    tx["maxFeePerGas"] = int(base_fee * 2)
                    tx["maxPriorityFeePerGas"] = self.w3.to_wei(1, "gwei")
                else:
                    tx["gasPrice"] = self.w3.eth.gas_price
            except Exception:
                tx["gasPrice"] = self.w3.eth.gas_price

        try:
            tx_hash = self.w3.eth.send_transaction(tx)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return receipt
        except Exception:
            self.reset_nonce()
            raise
