"""SAFE-proposed attestation flow (KI-14 D2).

The server holds the SAFE delegate key (propose-only). It builds the EAS
``attest()`` call data, wraps it in a SAFE transaction, and proposes it to
the Core Team SAFE on Celo via the SAFE Transaction Service API. Humans
confirm in the Safe app; a reconciliation pass marks requests executed once
the SAFE reports the transaction as executed.

This removes the need for the local private key to *send* attestations —
even a full delegate-key leak can only propose, never execute.
"""

from __future__ import annotations

import json
import os

from services.treasury.propose import SafeProposeClient, SafeTxData

# Core Team SAFE (Celo deployment, verified 2026-08-30: nonce 65, active).
CORE_TEAM_SAFE = "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5"
DEFAULT_SAFE_CHAIN = "celo"


def _delegate_key() -> str | None:
    return os.environ.get("SAFE_DELEGATE_KEY") or os.environ.get(
        "ATTESTER_PRIVATE_KEY"
    )


def propose_attestation(
    conn,
    request_id: str,
    *,
    safe_address: str = CORE_TEAM_SAFE,
    safe_chain: str = DEFAULT_SAFE_CHAIN,
) -> dict:
    """Propose an EAS attestation call to the Core Team SAFE.

    Args:
        conn: DB connection (attestation_request row must already be pending)
        request_id: attestation_request.id
        safe_address: SAFE that will sign the attestation (Core Team SAFE)
        safe_chain: chain the SAFE lives on (celo)

    Returns:
        {"proposal_status": str, "safe_tx_hash": str, ...}
    """
    from services.attestation.config import KOKONUT_MULTISIG
    from services.attestation.eas_client import EASClient
    from services.attestation.publisher import _resolve_schema_uid
    from services.attestation.schemas import prepare_data_post_attestation_data

    request = conn.execute(
        conn.text(
            "SELECT id, subject_type, subject_id, schema_name, chain, metadata "
            "FROM attestation_request WHERE id = :rid"
        ),
        {"rid": request_id},
    ).mappings().first()

    if not request:
        raise ValueError(f"attestation_request not found: {request_id}")

    schema_uid = _resolve_schema_uid(request["schema_name"], safe_chain)
    subject_id = str(request["subject_id"])
    metadata = json.loads(request["metadata"]) if request["metadata"] else {}

    post = conn.execute(
        conn.text("SELECT * FROM data_stream_post WHERE id = :sid"),
        {"sid": subject_id},
    ).mappings().first()

    if not post:
        raise ValueError(f"data_stream_post not found: {subject_id}")

    data = prepare_data_post_attestation_data(
        location_id=str(post["location_id"]),
        post_type=post["post_type"],
        title=post["title"],
        content_hash=post.get("content_hash", ""),
        media_type=post.get("media_type") or "",
        timestamp=int(post["anchored_at"].timestamp()) if post.get("anchored_at") else 0,
        visibility=post.get("visibility", "internal"),
        evidence_hash=metadata.get("content_payload_hash", ""),
        payload_cid="",
    )

    # Build the EAS attest() call — encode only, no send.
    client = EASClient(safe_chain)
    tx = client.build_attest_call(
        schema_uid=schema_uid,
        recipient=KOKONUT_MULTISIG,
        data=data,
        revocable=True,
    )

    # Wrap in a SAFE proposal.
    proposer = SafeProposeClient(
        chain=safe_chain,
        safe_address=safe_address,
        delegate_key=_delegate_key(),
    )
    safe_tx = SafeTxData(
        to=tx["to"],
        value=int(tx.get("value") or 0),
        data=tx["data"],
        nonce=None,  # resolved from SAFE state by propose()
    )
    proposal = proposer.propose(safe_tx)

    conn.execute(
        conn.text(
            "UPDATE attestation_request "
            "SET proposal_status = 'proposed', safe_tx_hash = :h, safe_chain = :c, "
            "    execution_status = 'pending', updated_at = NOW() "
            "WHERE id = :rid"
        ),
        {
            "h": proposal.get("safeTxHash") or safe_tx.safe_tx_hash,
            "c": safe_chain,
            "rid": request_id,
        },
    )
    conn.commit()

    return {
        "request_id": request_id,
        "proposal_status": "proposed",
        "safe_tx_hash": proposal.get("safeTxHash") or safe_tx.safe_tx_hash,
        "safe_chain": safe_chain,
        "safe_address": safe_address,
    }


def reconcile_attestation_executions(conn, safe_chain: str = DEFAULT_SAFE_CHAIN,
                                     safe_address: str = CORE_TEAM_SAFE) -> dict:
    """Poll the SAFE Transaction Service for proposed attestations.

    Marks attestation_request rows 'executed' + captures the on-chain tx hash
    when the SAFE reports the transaction executed.

    Returns:
        {"checked": int, "executed": int, "results": list[dict]}
    """
    from services.treasury.safe import SafeReadClient

    reader = SafeReadClient(chain=safe_chain)

    pending = conn.execute(
        conn.text(
            "SELECT id, safe_tx_hash FROM attestation_request "
            "WHERE proposal_status = 'proposed' AND safe_tx_hash IS NOT NULL"
        )
    ).mappings().all()

    executed = 0
    results = []
    for row in pending:
        safe_tx_hash = row["safe_tx_hash"]
        try:
            txs = reader.multisig_transactions(safe_address, limit=50)
            target = next((t for t in txs if t.safe_tx_hash == safe_tx_hash), None)
            if target and target.executed:
                conn.execute(
                    conn.text(
                        "UPDATE attestation_request "
                        "SET proposal_status = 'executed', execution_status = 'confirmed', "
                        "    tx_hash = :txh, confirmed_at = NOW(), updated_at = NOW() "
                        "WHERE id = :rid"
                    ),
                    {"txh": target.execution_date or "", "rid": row["id"]},
                )
                executed += 1
                results.append({"request_id": row["id"], "status": "executed"})
        except Exception:  # noqa: BLE001 - one bad row shouldn't abort the pass
            results.append({"request_id": row["id"], "status": "error"})
    conn.commit()

    return {"checked": len(pending), "executed": executed, "results": results}


def process_pending_requests_via_safe(
    conn, limit: int = 10, safe_chain: str = DEFAULT_SAFE_CHAIN,
) -> dict:
    """Process pending attestation requests by proposing them to the SAFE.

    Returns:
        {"proposed": int, "failed": int, "results": list[dict]}
    """
    pending = conn.execute(
        conn.text(
            "SELECT id FROM attestation_request "
            "WHERE execution_status = 'pending' AND proposal_status = 'pending' "
            "ORDER BY created_at ASC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings().all()

    proposed = 0
    failed = 0
    results = []
    for row in pending:
        try:
            result = propose_attestation(conn, str(row["id"]), safe_chain=safe_chain)
            proposed += 1
            results.append(result)
        except Exception as exc:  # noqa: BLE001 - per-row isolation
            failed += 1
            conn.execute(
                conn.text(
                    "UPDATE attestation_request "
                    "SET proposal_status = 'failed', error_message = :e, updated_at = NOW() "
                    "WHERE id = :rid"
                ),
                {"e": str(exc)[:500], "rid": row["id"]},
            )
            conn.commit()
            results.append({"request_id": row["id"], "status": "failed", "error": str(exc)[:200]})

    return {"proposed": proposed, "failed": failed, "results": results}
