"""Read-only integration client for the Kokonut DAO (Moloch v3 / Baal).

Mirrors the conventions of ``services/guilds/moloch.py``: a Web3-backed read
client with **no transaction methods**. It resolves the deployed Baal core
contract and its Shares/Loot ERC20 tokens, and normalizes on-chain state into
the framework-agnostic types from ``services/governance/base.py``.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from web3 import Web3

from ..ingestion.config import GNOSIS_RPC_URL, KOKONUT_BAAL_ADDRESSES
from .base import (
    GovernanceConfig,
    MemberState,
    ProposalLifecycle,
    ProposalState,
    VoteChoice,
)

_ABI_DIR = Path(__file__).resolve().parents[2] / "contracts" / "abis"

# Baal proposal.status enum (see Baal.sol ProposalState).
_BAAL_STATUS = {
    0: ProposalLifecycle.UNKNOWN,
    1: ProposalLifecycle.VOTING,
    2: ProposalLifecycle.GRACE,
    3: ProposalLifecycle.READY,
    4: ProposalLifecycle.EXECUTED,
    5: ProposalLifecycle.DEFEATED,
    6: ProposalLifecycle.CANCELLED,
    7: ProposalLifecycle.SPONSORED,
}


def _load_abi(name: str) -> list[dict[str, Any]]:
    with open(_ABI_DIR / name) as fh:
        return json.load(fh)


_ERC20_ABI = [
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


class BaalReadClient:
    """Read-only client for a Moloch v3 (Baal) DAO. No tx methods."""

    key = "moloch_v3_baal"
    name = "Kokonut DAO (Moloch v3 / Baal)"
    chain = "gnosis"

    def __init__(self, w3: Web3 | None = None, addresses: dict[str, str] | None = None):
        self.w3 = w3 or Web3(Web3.HTTPProvider(GNOSIS_RPC_URL))
        self.addresses = addresses or KOKONUT_BAAL_ADDRESSES
        self._baal_abi = _load_abi("Baal.json")
        self._baal = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.addresses["baal"]),
            abi=self._baal_abi,
        )

    def chain_id(self) -> int:
        return int(self.w3.eth.chain_id)

    def _token(self, token_key: str):
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(self.addresses[token_key]),
            abi=_ERC20_ABI,
        )

    def _normalize_token_balance(self, token_key: str, wallet: str) -> dict[str, Any]:
        contract = self._token(token_key)
        raw = int(contract.functions.balanceOf(Web3.to_checksum_address(wallet)).call())
        decimals = int(contract.functions.decimals().call())
        return {
            "wallet": Web3.to_checksum_address(wallet),
            "token": token_key,
            "token_address": self.addresses[token_key],
            "raw_balance": raw,
            "balance": str(Decimal(raw) / (Decimal(10) ** decimals)),
            "decimals": decimals,
            "chain_id": self.chain_id(),
        }

    def proposal(self, proposal_id: str) -> ProposalState:
        pid = int(proposal_id)
        data = self._baal.functions.proposals(pid).call()
        flags = self._baal.functions.getProposalFlags(pid).call()
        (
            _id,
            _hash,
            sponsor,
            shares_requested,
            loot_requested,
            yes_votes,
            no_votes,
            _max_shares,
            _data,
            details,
            voting_starts,
            voting_ends,
            grace_ends,
            expiration,
            status,
            self_sponsor,
        ) = data
        sponsored, processed, cancelled, action_failed, passed = flags
        lifecycle = _BAAL_STATUS.get(status, ProposalLifecycle.UNKNOWN)
        return ProposalState(
            proposal_id=str(pid),
            lifecycle=lifecycle,
            details=details,
            sponsor=sponsor,
            yes_votes=int(yes_votes),
            no_votes=int(no_votes),
            voting_starts=int(voting_starts),
            voting_ends=int(voting_ends),
            grace_ends=int(grace_ends),
            expiration=int(expiration),
            passed=bool(passed),
            action_failed=bool(action_failed),
            raw={
                "shares_requested": str(shares_requested),
                "loot_requested": str(loot_requested),
                "sponsored": bool(sponsored),
                "processed": bool(processed),
                "cancelled": bool(cancelled),
                "self_sponsor": bool(self_sponsor),
            },
        )

    def proposals(self) -> list[ProposalState]:
        total = int(self._baal.functions.totalProposals().call())
        return [self.proposal(str(i)) for i in range(total)]

    def member(self, wallet: str) -> MemberState:
        checksum = Web3.to_checksum_address(wallet)
        shares = int(self._baal.functions.sharesBalance(checksum).call())
        loot = int(self._baal.functions.lootBalance(checksum).call())
        delegate = self._baal.functions.delegates(checksum).call()
        return MemberState(
            wallet=checksum,
            shares=shares,
            loot=loot,
            delegate=delegate,
            raw={},
        )

    def config(self) -> GovernanceConfig:
        return GovernanceConfig(
            voting_period=int(self._baal.functions.votingPeriod().call()),
            grace_period=int(self._baal.functions.gracePeriod().call()),
            proposal_offering=int(self._baal.functions.proposalOffering().call()),
            quorum_percent=int(self._baal.functions.quorumPercent().call()),
            sponsor_threshold=int(self._baal.functions.sponsorThreshold().call()),
            min_retention_percent=int(self._baal.functions.minRetentionPercent().call()),
            raw={"baal_version": self._baal.functions.baalVersion().call()},
        )

    def shamans(self) -> list[dict[str, Any]]:
        """Return registered shamans and their permission level.

        Permission registry: 0 none, 1 admin, 2 manager, 4 governor,
        and additive combinations (3/5/6/7).
        """
        # Baal exposes shamans via public mapping; enumerate known addresses by
        # reading the GovernanceConfigSet/ShamanSet event history would be ideal,
        # but the contract only exposes the mapping. We surface the raw mapping
        # for any address the caller supplies; for discovery we rely on the
        # indexer-populated table. Here we return an empty list as a safe default
        # and let the CLI surface individual shaman lookups.
        return []

    def shaman_permission(self, shaman: str) -> int:
        return int(self._baal.functions.shamans(Web3.to_checksum_address(shaman)).call())

    def vote_choice(self, proposal_id: str, voter: str) -> VoteChoice | None:
        """Best-effort vote lookup; Baal does not store per-voter choice readly.

        Falls back to None when not discoverable from the read client.
        """
        return None
