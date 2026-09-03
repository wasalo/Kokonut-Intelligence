"""Farm SAFE provisioning — agent proposes, human approves, SAFE Factory deploys.

Phase C of KI-12: every farm registered in the Kokonut Farms Registry can get
its own SAFE sidecar. The agent proposes a configuration (steward addresses,
threshold, chain) — a human reviews and approves — then the SAFE is deployed
via the official SAFE Factory (separate on-chain action).

The SAFE "propose function role" gives the agent the ability to propose
transactions on the deployed SAFE, but only humans sign/execute.

Chain-agnostic: farms on any SAFE-supported chain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _db():
    """Lazy-import the DB connection (avoids SOPS load at import time)."""
    from services.common.cli import get_connection

    return get_connection()


def _print_json(data: Any) -> None:
    from services.common.cli import print_json

    print_json(data)


@dataclass
class SafeProvisioningRequest:
    """Agent's proposal for a new farm SAFE."""

    location_id: str
    chain: str = "gnosis"
    stewards: list[str] = field(default_factory=list)
    threshold: int = 1
    name: str | None = None
    notes: str | None = None


def propose_farm_safe(req: SafeProvisioningRequest) -> dict[str, Any]:
    """Agent proposes a new SAFE for a farm (inserts draft ``safe_account``).

    The agent provides the farm location, chain, steward addresses, and
    signature threshold. The record is created with ``provisioning_status='proposed'``
    and ``status='draft'`` — a human must verify and approve before the SAFE
    Factory deployment can proceed.
    """
    if not req.stewards:
        raise ValueError("At least one steward address is required")
    if req.threshold < 1:
        raise ValueError("Threshold must be >= 1")
    if req.threshold > len(req.stewards):
        raise ValueError(
            f"Threshold ({req.threshold}) exceeds steward count ({len(req.stewards)})"
        )

    safe_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Validate location exists (quick check via DB) and insert the draft
    # safe_account in the same transaction so a rollback on error cleans up.
    with _db() as conn:
        loc = conn.execute(
            "SELECT id, name FROM location WHERE id = %s", (req.location_id,)
        ).fetchone()
        if not loc:
            raise ValueError(f"Location not found: {req.location_id}")

        name = req.name or f"{loc.name} Farm SAFE"
        conn.execute(
            """
                INSERT INTO safe_account
                    (id, address, chain, account_role, location_id, name,
                     threshold, owners, provisioning_status, status)
                VALUES (%s, %s, %s, 'farm', %s, %s, %s, %s, 'proposed', 'draft')
            """,
            (
                safe_id,
                f"pending-{safe_id[:8]}",  # placeholder until deployed
                req.chain,
                req.location_id,
                name,
                req.threshold,
                req.stewards,
            ),
        )

    return {
        "safe_id": safe_id,
        "location_id": req.location_id,
        "chain": req.chain,
        "name": name,
        "threshold": req.threshold,
        "stewards": req.stewards,
        "provisioning_status": "proposed",
        "status": "draft",
        "note": "Human approval required before SAFE Factory deployment.",
    }


def approve_farm_safe(safe_id: str, safe_address: str | None = None) -> dict[str, Any]:
    """Human approves a proposed farm SAFE.

    If ``safe_address`` is provided, the SAFE has been deployed on-chain and
    the record is updated with the real address and ``provisioning_status='active'``.
    If ``safe_address`` is None, only the provisioning state advances to
    ``'approved'`` (ready for Factory deployment).
    """
    with _db() as conn:
        row = conn.execute(
            "SELECT id, provisioning_status, status FROM safe_account WHERE id = %s",
            (safe_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"safe_account not found: {safe_id}")
        if row.provisioning_status != "proposed":
            raise ValueError(
                f"Cannot approve: current provisioning_status is "
                f"'{row.provisioning_status}', expected 'proposed'"
            )

        if safe_address:
            conn.execute(
                """
                UPDATE safe_account
                SET address = %s, provisioning_status = 'active', status = 'published',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (safe_address.lower(), safe_id),
            )
            status = "active"
        else:
            conn.execute(
                """
                UPDATE safe_account
                SET provisioning_status = 'approved', status = 'verified', updated_at = NOW()
                WHERE id = %s
                """,
                (safe_id,),
            )
            status = "approved"

    return {"safe_id": safe_id, "provisioning_status": status}


def list_farm_safes(location_id: str | None = None) -> list[dict[str, Any]]:
    """List all SAFE accounts (filter by location if provided)."""
    with _db() as conn:
        if location_id:
            rows = conn.execute(
                "SELECT id, address, chain, account_role, name, threshold, owners, "
                "provisioning_status, status, created_at "
                "FROM safe_account WHERE location_id = %s ORDER BY created_at DESC",
                (location_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, address, chain, account_role, name, threshold, owners, "
                "provisioning_status, status, created_at "
                "FROM safe_account WHERE account_role = 'farm' ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r._mapping) for r in rows]


def cli_propose(
    location_id: str,
    chain: str = "gnosis",
    stewards: list[str] | None = None,
    threshold: int = 1,
    name: str | None = None,
) -> None:
    """CLI: agent proposes a new farm SAFE."""
    req = SafeProvisioningRequest(
        location_id=location_id,
        chain=chain,
        stewards=stewards or [],
        threshold=threshold,
        name=name,
    )
    result = propose_farm_safe(req)
    _print_json(result)


def cli_approve(safe_id: str, safe_address: str | None = None) -> None:
    """CLI: human approves a proposed farm SAFE."""
    result = approve_farm_safe(safe_id, safe_address)
    _print_json(result)


def cli_list(location_id: str | None = None) -> None:
    """CLI: list farm SAFEs."""
    safes = list_farm_safes(location_id)
    _print_json(safes)