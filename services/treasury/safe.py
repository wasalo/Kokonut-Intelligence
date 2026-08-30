"""Chain-agnostic SAFE treasury read client.

Mirrors the read-first pattern of ``services/governance/``: KI reads SAFE
state (owners, threshold, modules, balances, transactions) via the SAFE
Transaction Service REST API. NO transaction submission here — agents may
propose (Phase C+), humans approve/sign via SAFE app/API.

Chain-agnostic by design: config maps chain_id -> SAFE API base URL, exactly
like the governance adapters map framework -> chain. A farm may be inside the
Kokonut DAO (Gnosis) or standalone with its own SAFE on any SAFE-supported
chain; the same client serves both.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests

# SAFE Transaction Service API base URLs (official, per chain)
SAFE_API_BASE = {
    "gnosis": "https://safe-transaction-gnosis-chain.safe.global/api/v1",
    "mainnet": "https://safe-transaction-mainnet.safe.global/api/v1",
    "celo": "https://safe-transaction-celo.safe.global/api/v1",
    "sepolia": "https://safe-transaction-sepolia.safe.global/api/v1",
    "polygon": "https://safe-transaction-polygon.safe.global/api/v1",
    "arbitrum": "https://safe-transaction-arbitrum.safe.global/api/v1",
    "optimism": "https://safe-transaction-optimism.safe.global/api/v1",
    "base": "https://safe-transaction-base.safe.global/api/v1",
}

# Canonical Kokonut SAFEs (Gnosis Chain, verified 2026-08-29)
KOKONUT_SAFES = {
    "core_team": "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5",
    "dao_treasury": "0xeB55b75328a8dFfd45Bbf34B7e7efC431A179085",
}
KOKONUT_BAAL = "0x8977c56e979f0D8B76aFB5aD85549aCd2e96422d"


@dataclass
class SafeState:
    """Snapshot of a SAFE's configuration."""

    address: str
    threshold: int
    owners: list[str]
    version: str | None
    modules: list[str] = field(default_factory=list)
    guard: str | None = None
    fallback_handler: str | None = None
    nonce: int | None = None
    chain: str = "gnosis"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SafeTransaction:
    """A proposed or executed multisig transaction."""

    safe_tx_hash: str
    nonce: int | None
    to: str
    value: str
    data: str | None = None
    proposer: str | None = None
    confirmations: int = 0
    confirmations_required: int | None = None
    executed: bool | None = None
    submission_date: str | None = None
    execution_date: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SafeBalance:
    """Token balance held by a SAFE."""

    token_address: str | None
    token_symbol: str | None
    balance: str
    fiat_balance: str | None = None
    chain: str = "gnosis"


class SafeReadClient:
    """Read-only client for SAFE smart accounts (Transaction Service API)."""

    key = "safe"
    name = "SAFE (safe.global) smart account treasury"

    def __init__(self, chain: str = "gnosis", api_key: str | None = None,
                 base_url: str | None = None):
        if chain not in SAFE_API_BASE:
            raise ValueError(
                f"Unsupported chain '{chain}'. Supported: {sorted(SAFE_API_BASE)}"
            )
        self.chain = chain
        self.base_url = base_url or SAFE_API_BASE[chain]
        self._session = requests.Session()
        self._session.headers.update(
            {"Accept": "application/json"}
        )
        # Optional hosted-API key (free Builder tier). Unauthenticated works
        # for low-volume reads; key lifts rate limits.
        api_key = api_key or os.environ.get("SAFE_API_KEY")
        if api_key:
            self._session.headers.update({"Authorization": f"Bearer {api_key}"})

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def safe_state(self, address: str) -> SafeState:
        """Fetch SAFE configuration (owners, threshold, modules, nonce)."""
        d = self._get(f"/safes/{address}")
        return SafeState(
            address=d.get("address", address),
            threshold=int(d.get("threshold") or 0),
            owners=d.get("owners") or [],
            version=d.get("version"),
            modules=d.get("modules") or [],
            guard=d.get("guard") or None,
            fallback_handler=d.get("fallbackHandler") or None,
            nonce=int(d.get("nonce")) if d.get("nonce") is not None else None,
            chain=self.chain,
            raw=d,
        )

    def balances(self, address: str) -> list[SafeBalance]:
        """Fetch token balances (native + ERC-20) held by a SAFE."""
        resp = self._get(f"/safes/{address}/balances", params={"trusted": "true"})
        items = resp.get("results") if isinstance(resp, dict) and "results" in resp else resp
        if isinstance(items, dict):
            items = items.get("items") or []
        out: list[SafeBalance] = []
        for item in (items or []):
            if not isinstance(item, dict):
                continue
            out.append(SafeBalance(
                token_address=item.get("tokenAddress"),
                token_symbol=item.get("token") or item.get("tokenSymbol"),
                balance=str(item.get("balance", "0")),
                fiat_balance=str(item.get("fiatBalance")) if item.get("fiatBalance") is not None else None,
                chain=self.chain,
            ))
        return out

    def multisig_transactions(self, address: str, limit: int = 20
                              ) -> list[SafeTransaction]:
        """Fetch proposed/executed multisig transactions."""
        d = self._get(f"/safes/{address}/multisig-transactions/",
                      params={"limit": limit})
        out: list[SafeTransaction] = []
        for t in d.get("results", []):
            out.append(SafeTransaction(
                safe_tx_hash=t.get("safeTxHash", ""),
                nonce=int(t.get("nonce")) if t.get("nonce") is not None else None,
                to=t.get("to", ""),
                value=t.get("value", "0"),
                data=t.get("data"),
                proposer=t.get("proposer"),
                confirmations=len(t.get("confirmations") or []),
                confirmations_required=t.get("confirmationsRequired"),
                executed=t.get("executed"),
                submission_date=t.get("submissionDate"),
                execution_date=t.get("executionDate"),
                raw=t,
            ))
        return out

    # ── Kokonut shortcuts ────────────────────────────────────────────────
    def core_team_safe(self) -> SafeState:
        return self.safe_state(KOKONUT_SAFES["core_team"])

    def dao_treasury(self) -> SafeState:
        return self.safe_state(KOKONUT_SAFES["dao_treasury"])


def get_client(chain: str = "gnosis") -> SafeReadClient:
    """Convenience factory for the CLI."""
    return SafeReadClient(chain=chain)
