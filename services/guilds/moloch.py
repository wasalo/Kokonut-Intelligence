"""Read-only integration helpers for the Kokonut Moloch DAO on Gnosis."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from web3 import Web3

from ..ingestion.config import GNOSIS_RPC_URL, KOKONUT_MOLOCH_ADDRESSES

ERC20_BALANCE_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class MolochReadClient:
    """Read-only client; this module deliberately has no transaction methods."""

    def __init__(self, w3: Web3 | None = None):
        self.w3 = w3 or Web3(Web3.HTTPProvider(GNOSIS_RPC_URL))

    def chain_id(self) -> int:
        return int(self.w3.eth.chain_id)

    def token_balance(self, wallet: str, token_key: str) -> dict[str, Any]:
        token_address = KOKONUT_MOLOCH_ADDRESSES[token_key]
        contract = self.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_BALANCE_ABI)
        raw = int(contract.functions.balanceOf(Web3.to_checksum_address(wallet)).call())
        decimals = int(contract.functions.decimals().call())
        return {
            "wallet": Web3.to_checksum_address(wallet),
            "token": token_key,
            "token_address": token_address,
            "raw_balance": raw,
            "balance": str(Decimal(raw) / (Decimal(10) ** decimals)),
            "decimals": decimals,
            "chain_id": self.chain_id(),
        }


def link_guild_motion_to_moloch(cursor, guild_motion_id: str, proposal_code: str) -> None:
    """Link an operational Guild motion to an existing DAO proposal only."""
    cursor.execute("SELECT id FROM dao_proposal WHERE proposal_code = %s", (proposal_code,))
    proposal = cursor.fetchone()
    if not proposal:
        raise ValueError(f"Unknown Moloch proposal code: {proposal_code}")
    cursor.execute(
        """
        UPDATE guild_motion
        SET dao_proposal_id = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id
        """,
        (proposal[0], guild_motion_id),
    )
    if cursor.fetchone() is None:
        raise ValueError(f"Unknown Guild motion: {guild_motion_id}")
