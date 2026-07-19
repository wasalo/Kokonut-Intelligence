"""Unified governance CLI for Kokonut Intelligence.

Exposes the configurable Governance Framework abstraction through the ``kokonut``
meta-CLI. Read-only: it queries on-chain DAO state and the local framework
registry; it never submits transactions.

Examples:
    python3 -m services.governance.cli framework list
    python3 -m services.governance.cli baal config
    python3 -m services.governance.cli baal proposals
    python3 -m services.governance.cli baal proposal 3
    python3 -m services.governance.cli baal member 0x1234...
    python3 -m services.governance.cli baal shaman 0xabcd...
"""

from __future__ import annotations

import typer

from services.common.cli import get_connection, print_json, run
from services.governance.adapters import (  # registers adapters on import (side-effect)
    register as _register_adapters,  # noqa: F401
)
from services.governance.baal import BaalReadClient
from services.governance.registry import (
    get_framework,
    list_frameworks,
)

app = typer.Typer(name="governance", help="Governance framework queries (read-only)")


@app.command("framework")
def framework_list() -> None:
    """List configured governance frameworks (from the local registry/DB)."""
    rows = list_frameworks()
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT framework_key, is_active FROM governance_framework"
        )
        active = {r.framework_key: r.is_active for r in cur.fetchall()}
    for r in rows:
        r["configured_in_db"] = r["key"] in active
        r["is_active"] = bool(active.get(r["key"], False))
    print_json(rows)


@app.command("baal")
def baal_group(
    command: str = typer.Argument(..., help="config | proposals | proposal | member | shaman"),
    arg: str = typer.Argument(None, help="proposal id, wallet, or shaman address"),
) -> None:
    """Query the Kokonut DAO (Moloch v3 / Baal) on Gnosis Chain."""
    client = get_framework("moloch_v3_baal")
    if not isinstance(client, BaalReadClient):
        raise TypeError("moloch_v3_baal adapter is not a BaalReadClient")
    if command == "config":
        print_json(client.config().__dict__)
    elif command == "proposals":
        proposals = client.proposals()
        if not proposals:
            proposal_count = (client.config().raw or {}).get("proposal_count")
            print_json(
                {
                    "proposals": [],
                    "note": (
                        "The deployed Baal exposes proposalCount="
                        f"{proposal_count} but individual proposal structs could "
                        "not be decoded with the committed Baal ABI. Run the "
                        "indexer (services.ingestion.baal_indexer) to populate "
                        "governance_event, then query the DB."
                    ),
                }
            )
        else:
            print_json([p.__dict__ for p in proposals])
    elif command == "proposal":
        if not arg:
            raise ValueError("proposal id required")
        print_json(client.proposal(arg).__dict__)
    elif command == "member":
        if not arg:
            raise ValueError("wallet address required")
        print_json(client.member(arg).__dict__)
    elif command == "shaman":
        if not arg:
            raise ValueError("shaman address required")
        print_json(
            {
                "shaman": arg,
                "permission": client.shaman_permission(arg),
                "permission_note": "0 none,1 admin,2 manager,4 governor,additive combos 3/5/6/7",
            }
        )
    else:
        raise ValueError(
            f"Unknown baal command '{command}'. "
            "Use: config, proposals, proposal, member, shaman."
        )


def main() -> None:
    run(app())


if __name__ == "__main__":
    main()
