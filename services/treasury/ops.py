"""Farm treasury operations (KI-14 D4).

The agent proposes operations on a deployed farm SAFE (payroll, inputs,
expenses) as a SAFE delegate; farm stewards confirm in the Safe app.

Builds on the farm SAFE provisioning flow (KI-12 Phase C): the ``safe_account``
row carries the farm SAFE's address, chain, stewards, and threshold.
"""

from __future__ import annotations

import os
from decimal import Decimal

from services.treasury.propose import SafeProposeClient, SafeTxData


def _db():
    """Lazy-import the DB connection (avoids SOPS load at import time)."""
    from services.common.cli import get_connection

    return get_connection()


def _print_json(data) -> None:
    from services.common.cli import print_json

    print_json(data)


def _delegate_key() -> str | None:
    return os.environ.get("SAFE_DELEGATE_KEY") or os.environ.get(
        "ATTESTER_PRIVATE_KEY"
    )


def propose_farm_op(
    safe_id: str,
    to: str,
    value: int | str | Decimal = 0,
    data: str = "0x",
    memo: str = "",
    *,
    safe_address: str | None = None,
    safe_chain: str | None = None,
) -> dict:
    """Propose an operation on a farm SAFE (payroll, inputs, expenses).

    If ``safe_address``/``safe_chain`` are omitted, they are resolved from the
    ``safe_account`` table (Phase C provisioning record).

    Returns:
        {"proposal_status": str, "safe_tx_hash": str, "safe_id": str, "memo": str}
    """
    if safe_address is None or safe_chain is None:
        with _db() as conn:
            row = conn.execute(
                "SELECT address, chain FROM safe_account WHERE id = %s",
                (safe_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"safe_account not found: {safe_id}")
            safe_address = safe_address or row.address
            safe_chain = safe_chain or row.chain

    proposer = SafeProposeClient(
        chain=safe_chain,
        safe_address=safe_address,
        delegate_key=_delegate_key(),
    )
    wei_value = int(value) if isinstance(value, int) else (
        int(Decimal(value) * 10**18) if isinstance(value, Decimal) else int(value)
    )
    safe_tx = SafeTxData(
        to=to,
        value=wei_value,
        data=data,
        nonce=None,
    )
    proposal = proposer.propose(safe_tx)

    return {
        "safe_id": safe_id,
        "memo": memo,
        "proposal_status": "proposed",
        "safe_tx_hash": proposal.get("safeTxHash") or safe_tx.safe_tx_hash,
        "safe_chain": safe_chain,
        "safe_address": safe_address,
    }


def cli_propose(
    safe_id: str,
    to: str,
    value: str,
    memo: str = "",
    data: str = "0x",
    safe_address: str | None = None,
    safe_chain: str | None = None,
) -> None:
    """CLI wrapper for propose_farm_op."""
    result = propose_farm_op(
        safe_id=safe_id,
        to=to,
        value=value,
        memo=memo,
        data=data,
        safe_address=safe_address,
        safe_chain=safe_chain,
    )
    _print_json(result)
