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


@app.command("propose")
def safe_propose(
    location_id: str = typer.Argument(..., help="Farm location UUID"),
    chain: str = typer.Option("gnosis", help="Chain: gnosis, celo, mainnet, ..."),
    stewards: str = typer.Option("", help="Comma-separated steward addresses"),
    threshold: int = typer.Option(1, help="Signature threshold"),
    name: str | None = typer.Option(None, help="SAFE name"),
) -> None:
    """Agent proposes a new farm SAFE (draft record, human approval required)."""
    from services.treasury.provisioning import cli_propose

    cli_propose(
        location_id=location_id,
        chain=chain,
        stewards=[s.strip() for s in stewards.split(",") if s.strip()],
        threshold=threshold,
        name=name,
    )


@app.command("approve")
def safe_approve(
    safe_id: str = typer.Argument(..., help="safe_account id"),
    safe_address: str | None = typer.Option(
        None, help="Deployed SAFE address (human enters after Factory deploy)"),
) -> None:
    """Human approves a proposed farm SAFE (optionally with deployed address)."""
    from services.treasury.provisioning import cli_approve

    cli_approve(safe_id, safe_address)


@app.command("farms")
def safe_farms(
    location_id: str | None = typer.Option(None, help="Filter by location UUID"),
) -> None:
    """List farm SAFEs (proposed, approved, active)."""
    from services.treasury.provisioning import cli_list

    cli_list(location_id)


if __name__ == "__main__":
    app()
