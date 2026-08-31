"""Safe propose-only client — the agent proposes, humans sign/execute.

Phase D of KI-14: extends the read-only ``SafeReadClient`` with write-path
capability. The server holds a **delegate key that can only propose**
transactions via the SAFE Transaction Service API. It computes the EIP-712
``safeTxHash``, signs it with the delegate key, and POSTs the proposal.
Owners/confirmers approve in the Safe app. The delegate key can never execute
or move funds.

Security model:
- Delegate key is propose-only (Safe enforces this at the contract level).
- Even a full key leak lets an attacker propose, not execute.
- Execute requires human owner confirmation (threshold m-of-n).
- Official Safe Transaction Service API; chain-agnostic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import requests
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import to_bytes, to_checksum_address, to_hex
from web3 import Web3

from services.treasury.safe import SAFE_API_BASE, SafeReadClient

_DEFAULT_OPERATION = 0       # CALL
_DEFAULT_SAFE_TX_GAS = 0     # auto-compute
_DEFAULT_BASE_GAS = 0
_DEFAULT_GAS_PRICE = 0
_DEFAULT_GAS_TOKEN = "0x0000000000000000000000000000000000000000"
_DEFAULT_REFUND = "0x0000000000000000000000000000000000000000"


@dataclass
class SafeTxData:
    """A Safe multisig transaction ready to propose."""

    to: str
    value: int
    data: str            # hex-encoded
    operation: int = _DEFAULT_OPERATION
    safe_tx_gas: int = _DEFAULT_SAFE_TX_GAS
    base_gas: int = _DEFAULT_BASE_GAS
    gas_price: int = _DEFAULT_GAS_PRICE
    gas_token: str = _DEFAULT_GAS_TOKEN
    refund_receiver: str = _DEFAULT_REFUND
    nonce: int | None = None
    safe_tx_hash: str | None = None
    chain: str = "gnosis"
    safe_address: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class SafeProposeClient:
    """Propose-only client for Safe multisig transactions.

    Args:
        chain: Chain name (gnosis, celo, sepolia, ...)
        safe_address: The Safe address (checksummed)
        delegate_key: Private key of the delegate (propose-only role).
            If None, reads from ``SAFE_DELEGATE_KEY`` env var.
        api_key: Optional hosted API key (free Builder tier).
    """

    def __init__(
        self,
        chain: str = "gnosis",
        safe_address: str | None = None,
        delegate_key: str | None = None,
        api_key: str | None = None,
    ):
        if chain not in SAFE_API_BASE:
            raise ValueError(
                f"Unsupported chain '{chain}'. Supported: {sorted(SAFE_API_BASE)}"
            )
        self.chain = chain
        self.base_url = SAFE_API_BASE[chain]
        self.safe_address = safe_address or ""
        self._read_client = SafeReadClient(chain=chain, api_key=api_key)

        key = delegate_key or os.environ.get("SAFE_DELEGATE_KEY", "")
        if key:
            self._account = Account.from_key(key)
            self.delegate_address = to_checksum_address(self._account.address)
        else:
            self._account = None
            self.delegate_address = None

        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        api_key = api_key or os.environ.get("SAFE_API_KEY", "")
        if api_key:
            self._session.headers.update({"Authorization": f"Bearer {api_key}"})

    # ── EIP-712 safeTxHash computation ──────────────────────────────────

    def compute_safe_tx_hash(self, tx: SafeTxData) -> str:
        """Compute the EIP-712 safeTxHash for a Safe transaction.

        Verified against a real executed transaction on the Core Team SAFE
        (Gnosis, nonce 6: safeTxHash 0x776c65...) — the domain separator must
        use abi.encode (address padded to 32 bytes), NOT encodePacked.
        """
        safe = to_checksum_address(self.safe_address)
        chain_id = self._resolve_chain_id()

        from eth_abi import encode as abi_encode
        from web3 import Web3
        def _keccak(b: bytes) -> bytes:
            return Web3.keccak(b)

        # Safe v1.3.0+ domain: EIP712Domain(uint256 chainId,address verifyingContract)
        domain_typehash = _keccak(
            b"EIP712Domain(uint256 chainId,address verifyingContract)"
        )
        domain_separator = _keccak(
            abi_encode(
                ["bytes32", "uint256", "address"],
                [domain_typehash, chain_id, safe],
            )
        )

        safe_tx_typehash = _keccak(
            b"SafeTx(address to,uint256 value,bytes data,uint8 operation,"
            b"uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,"
            b"address gasToken,address refundReceiver,uint256 nonce)"
        )

        data_bytes = to_bytes(hexstr=tx.data) if isinstance(tx.data, str) and tx.data.startswith("0x") else (
            tx.data if isinstance(tx.data, bytes) else b""
        )
        struct_hash = _keccak(
            abi_encode(
                ["bytes32", "address", "uint256", "bytes32", "uint8",
                 "uint256", "uint256", "uint256", "address", "address", "uint256"],
                [safe_tx_typehash,
                 to_checksum_address(tx.to),
                 tx.value,
                 _keccak(data_bytes),
                 tx.operation,
                 tx.safe_tx_gas,
                 tx.base_gas,
                 tx.gas_price,
                 to_checksum_address(tx.gas_token),
                 to_checksum_address(tx.refund_receiver),
                 tx.nonce or 0],
            )
        )
        final = _keccak(bytes([0x19, 0x01]) + domain_separator + struct_hash)
        return "0x" + final.hex()

    def _resolve_chain_id(self) -> int:
        """Look up the chain ID for the current chain."""
        # Common chain IDs
        chain_ids = {
            "gnosis": 100,
            "mainnet": 1,
            "celo": 42220,
            "sepolia": 11155111,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "base": 8453,
        }
        return chain_ids.get(self.chain, 0)

    # ── Propose ─────────────────────────────────────────────────────────

    def propose(self, tx: SafeTxData) -> dict[str, Any]:
        """Propose a Safe transaction to the Transaction Service API.

        The delegate key signs the ``safeTxHash`` and the proposal is
        submitted. Owners must confirm and execute in the Safe app.
        """
        if not self._account:
            raise PermissionError(
                "No delegate key configured. Set SAFE_DELEGATE_KEY or pass delegate_key."
            )
        if not self.safe_address:
            raise ValueError("safe_address not set")

        safe = to_checksum_address(self.safe_address)
        # Ensure nonce
        if tx.nonce is None:
            state = self._read_client.safe_state(safe)
            tx.nonce = state.nonce or 0

        # Compute safeTxHash if not already set
        safe_tx_hash = tx.safe_tx_hash or self.compute_safe_tx_hash(tx)

        # Sign the raw safeTxHash bytes (ECDSA without EIP-191 prefix)
        # Safe's contract validates: ECDSA.recover(safeTxHash, signature)
        signed = self._account.unsafe_sign_hash(to_bytes(hexstr=safe_tx_hash))
        signature = to_hex(signed.signature)

        payload = {
            "safe": safe,
            "to": to_checksum_address(tx.to),
            "value": str(tx.value),
            "data": to_hex(tx.data) if isinstance(tx.data, bytes) else tx.data,
            "operation": tx.operation,
            "safeTxGas": str(tx.safe_tx_gas),
            "baseGas": str(tx.base_gas),
            "gasPrice": str(tx.gas_price),
            "gasToken": to_checksum_address(tx.gas_token),
            "refundReceiver": to_checksum_address(tx.refund_receiver),
            "nonce": str(tx.nonce),
            "safeTxHash": safe_tx_hash,
            "sender": self.delegate_address,
            "signature": signature,
            "origin": "kokonut-intelligence",
        }

        resp = self._session.post(
            f"{self.base_url}/safes/{safe}/multisig-transactions/",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Delegate management ────────────────────────────────────────────

    def register_delegate(
        self, label: str = "syntropic-agent", signer: str | None = None,
        signature: str | None = None,
    ) -> dict[str, Any]:
        """Register the delegate key with the SAFE Transaction Service.

        NOTE: This registers *this* delegate for the configured safe. The
        signature must be from a SAFE owner authorizing the delegate.
        For initial setup, an owner must call this once. The delegate
        cannot self-register.
        """
        if not self._account:
            raise PermissionError("No delegate key configured")
        safe = to_checksum_address(self.safe_address)
        delegate = to_checksum_address(self.delegate_address)
        payload = {
            "safe": safe,
            "delegate": delegate,
            "label": label,
            "signer": signer or delegate,
            "signature": signature or "0x",
        }
        resp = self._session.post(
            f"{self.base_url}/safes/{safe}/delegates/",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_delegates(self) -> list[dict[str, Any]]:
        """List all delegates for the configured safe."""
        safe = to_checksum_address(self.safe_address)
        resp = self._session.get(
            f"{self.base_url}/safes/{safe}/delegates/",
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    # ── Convenience builders ────────────────────────────────────────────

    def build_tx(
        self,
        to: str,
        value: int | str | Decimal = 0,
        data: str = "0x",
        nonce: int | None = None,
    ) -> SafeTxData:
        """Build a simple SafeTxData (CALL operation)."""
        wei_value = int(value) if isinstance(value, int) else (
            int(Decimal(value) * 10**18) if isinstance(value, Decimal) else int(value)
        )
        return SafeTxData(
            to=to_checksum_address(to),
            value=wei_value,
            data=data,
            operation=0,
            nonce=nonce,
            chain=self.chain,
            safe_address=self.safe_address,
        )