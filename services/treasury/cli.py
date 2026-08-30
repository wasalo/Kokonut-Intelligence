"""Treasury (SAFE) CLI — read-only views of Kokonut SAFE accounts.

Exposes SAFE smart-account queries through the ``kokonut`` meta-CLI, mirroring
the read-first pattern of the governance CLI. It reads owners, threshold,
modules, balances, and transactions from the SAFE Transaction Service API. It
never submits or signs transactions.

Examples:
    python3 -m services.treasury.cli status
    python3 -m services.treasury.cli status --address 0x...
    python3 -m services.treasury.cli balances
    python3 -m services.treasury.cli transactions --limit 10
"""

from __future__ import annotations

import typer

from services.treasury.safe import (
    KOKONUT_SAFES,
    SafeReadClient,
)

app = typer.Typer(name="treasury", help="SAFE smart account queries (read-only)")


def _client(chain: str) -> SafeReadClient:
    return SafeReadClient(chain=chain)


@app.command("status")
def safe_status(
    chain: str = typer.Option("gnosis", help="Chain: gnosis, mainnet, celo, ..."),
    address: str | None = typer.Option(None, help="SAFE address (default: both Kokonut SAFEs)"),
) -> None:
    """Show SAFE configuration: owners, threshold, modules, nonce."""
    import json

    client = _client(chain)
    targets = [address] if address else list(KOKONUT_SAFES.values())
    for addr in targets:
        s = client.safe_state(addr)
        print(json.dumps({
            "address": s.address,
            "chain": s.chain,
            "threshold": f"{s.threshold} of {len(s.owners)}",
            "owners": s.owners,
            "modules": s.modules,
            "guard": s.guard,
            "version": s.version,
            "nonce": s.nonce,
        }, indent=2))


@app.command("balances")
def safe_balances(
    chain: str = typer.Option("gnosis", help="Chain: gnosis, mainnet, celo, ..."),
    address: str | None = typer.Option(None, help="SAFE address (default: both Kokonut SAFEs)"),
) -> None:
    """Show token balances held by a SAFE."""
    import json

    client = _client(chain)
    targets = [address] if address else list(KOKONUT_SAFES.values())
    for addr in targets:
        print(json.dumps({
            "safe": addr,
            "chain": chain,
            "balances": [b.__dict__ for b in client.balances(addr)],
        }, indent=2, default=str))


@app.command("transactions")
def safe_transactions(
    chain: str = typer.Option("gnosis", help="Chain: gnosis, mainnet, celo, ..."),
    address: str | None = typer.Option(
        None, help="SAFE address (default: DAO treasury SAFE)"),
    limit: int = typer.Option(10, help="Max transactions to return"),
) -> None:
    """Show proposed/executed multisig transactions."""
    import json

    client = _client(chain)
    targets = [address] if address else [KOKONUT_SAFES["dao_treasury"]]
    for addr in targets:
        txs = client.multisig_transactions(addr, limit=limit)
        print(json.dumps({
            "safe": addr,
            "chain": chain,
            "count": len(txs),
            "transactions": [t.__dict__ for t in txs],
        }, indent=2, default=str))


if __name__ == "__main__":
    app()
