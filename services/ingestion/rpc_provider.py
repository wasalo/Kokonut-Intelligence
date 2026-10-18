"""Provider configuration shared by the legacy and isolated RPC indexers.

This module deliberately avoids importing database settings so it is safe to
load in a scheduled worker with an isolated database environment.
"""

from __future__ import annotations

import json
import os
from typing import Mapping
from urllib.parse import urlsplit

RPC_ENDPOINT_ENV = "KOKONUT_RPC_INDEXER_RPC_ENDPOINTS"

DEFAULT_RPC_ENDPOINTS = {
    "ethereum": "https://eth.llamarpc.com",
    "optimism": "https://mainnet.optimism.io",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "celo": "https://forno.celo.org",
    "celo-alfajores": "https://alfajores-forno.celo.org",
    "gnosis": "https://rpc.gnosischain.com",
}
RPC_CLI_CHAINS = tuple(DEFAULT_RPC_ENDPOINTS)


def _validate_endpoint(chain: str, endpoint: object) -> str:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError(f"RPC endpoint for {chain} must be a non-empty URL")
    try:
        parsed = urlsplit(endpoint)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.fragment == ""
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"RPC endpoint for {chain} must be an HTTP(S) URL without embedded credentials")
    return endpoint


def configured_rpc_endpoints(
    *, environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Return supported RPC endpoints, applying validated explicit overrides.

    Isolated workers receive overrides through one worker-specific JSON secret,
    so unrelated scheduled children never inherit RPC provider credentials.
    The legacy CLI retains its historical per-chain environment variables.
    """
    source = os.environ if environ is None else environ
    endpoints = dict(DEFAULT_RPC_ENDPOINTS)
    raw = source.get(RPC_ENDPOINT_ENV, "")
    if raw:
        try:
            overrides = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raise ValueError(f"{RPC_ENDPOINT_ENV} must contain a JSON object") from None
        if not isinstance(overrides, dict) or set(overrides) - set(DEFAULT_RPC_ENDPOINTS):
            raise ValueError(f"{RPC_ENDPOINT_ENV} contains unsupported chain names")
        for chain, endpoint in overrides.items():
            endpoints[chain] = _validate_endpoint(chain, endpoint)

    # Keep legacy manual configuration compatible. Isolated worker children
    # deliberately have these global variables filtered by the supervisor.
    for chain, variable in {
        "ethereum": "ETH_RPC_URL",
        "optimism": "OPTIMISM_RPC_URL",
        "base": "BASE_RPC_URL",
        "arbitrum": "ARBITRUM_RPC_URL",
        "celo": "CELO_RPC_URL",
        "celo-alfajores": "CELO_ALFAJORES_RPC_URL",
        "gnosis": "GNOSIS_RPC_URL",
    }.items():
        if variable in source:
            endpoints[chain] = _validate_endpoint(chain, source[variable])
    return endpoints
