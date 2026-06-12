#!/usr/bin/env python3
"""
EAS Attestation Ingestion — Direct EAS API

Fetches attestation records directly from the EAS GraphQL API
(not via subgraph). Supports multiple chains (Ethereum, Optimism, Base).

Usage:
    python -m services.ingestion.eas_indexer
    python -m services.ingestion.eas_indexer --chain ethereum
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import requests

from .base import get_db, log_ingestion, hash_payload, retry

# EAS GraphQL endpoints per chain
EAS_ENDPOINTS = {
    "optimism": "https://optimism.easscan.org",
    "base": "https://base.easscan.org",
    "celo": "https://celo.easscan.org",
}

# GraphQL queries
ATTESTATIONS_BY_RECIPIENT = """
query GetAttestations($recipient: String!, $after: Int!) {
    attestations(
        where: { recipient: { equals: $recipient } }
        orderBy: { time: desc }
        take: 100
        skip: $after
    ) {
        id
        txid
        schema { id schema }
        attester
        recipient
        data
        time
        timeCreated
        revocable
        revoked
        expirationTime
    }
}
"""

SCHEMAS_BY_CREATOR = """
query GetSchemas($creator: String!, $after: Int!) {
    schemata(
        where: { creator: { equals: $creator } }
        orderBy: { time: desc }
        take: 100
        skip: $after
    ) {
        id
        schema
        creator
        resolver
        revocable
        time
        txid
    }
}
"""


@retry(max_retries=3, backoff=2.0)
def query_eas(chain: str, query: str, variables: dict) -> dict:
    """Execute GraphQL query against EAS."""
    endpoint = EAS_ENDPOINTS.get(chain)
    if not endpoint:
        raise ValueError(f"No EAS endpoint configured for chain: {chain}")
    resp = requests.post(
        f"{endpoint}/graphql",
        json={"query": query, "variables": variables},
        timeout=30,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


def insert_attestation(db, att: dict, chain: str) -> str:
    """Insert EAS attestation into PostgreSQL."""
    attestation_uid = att["id"]
    block_ts = datetime.fromtimestamp(
        int(att.get("time", 0)), tz=timezone.utc
    ).isoformat()

    with db.cursor() as cur:
        # Check if already exists
        cur.execute(
            "SELECT id FROM attestation_record WHERE attestation_uid = %s",
            (attestation_uid,),
        )
        if cur.fetchone():
            return None

        # Check if schema exists, create if not
        schema_uid = att.get("schema", {}).get("id", "") if att.get("schema") else ""
        schema_text = att.get("schema", {}).get("schema", "") if att.get("schema") else ""

        schema_id = None
        if schema_uid:
            cur.execute(
                "SELECT id FROM attestation_schema WHERE schema_uid = %s",
                (schema_uid,),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    """
                    INSERT INTO attestation_schema (schema_uid, name, schema_text, chain, active)
                    VALUES (%s, %s, %s, %s, true)
                    RETURNING id
                    """,
                    (schema_uid, f"Schema {schema_uid[:10]}", schema_text, chain),
                )
                schema_id = str(cur.fetchone()[0])
            else:
                schema_id = str(row[0])

        cur.execute(
            """
            INSERT INTO attestation_record
                (schema_id, attestation_uid, subject_type,
                 claim_data, status, tx_hash, chain, attested_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                schema_id, attestation_uid,
                "wallet",
                json.dumps({
                    "attester": att.get("attester"),
                    "recipient": att.get("recipient"),
                    "data": att.get("data"),
                    "revocable": att.get("revocable"),
                    "revoked": att.get("revoked"),
                    "expiration_time": att.get("expirationTime"),
                }),
                "rejected" if att.get("revoked") else "published",
                att.get("txid", ""),
                chain,
                block_ts,
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def get_last_attestation_time(db, chain: str) -> int:
    """Get the last indexed EAS attestation timestamp for a chain."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT metadata->>'last_attestation_time'
            FROM chain_indexer_status
            WHERE chain = %s AND indexer_type = 'eas'
            """,
            (chain,),
        )
        row = cur.fetchone()
    return int(row[0]) if row and row[0] else 0


def update_eas_indexer_status(chain: str, last_attestation_time: int, status: str, error_message: str = None) -> None:
    """Update EAS sync status without treating timestamps as block numbers."""
    status_db = get_db()
    try:
        with status_db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chain_indexer_status
                    (chain, indexer_type, last_synced_block, last_synced_at, status, error_message, metadata)
                VALUES (%s, 'eas', NULL, NOW(), %s, %s, %s::jsonb)
                ON CONFLICT (chain, indexer_type) DO UPDATE SET
                    last_synced_block = NULL,
                    last_synced_at = NOW(),
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    metadata = COALESCE(chain_indexer_status.metadata, '{}'::jsonb) || EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                (
                    chain,
                    status,
                    error_message,
                    json.dumps({"last_attestation_time": last_attestation_time}),
                ),
            )
        status_db.commit()
    finally:
        status_db.close()


def run(chain: str = None):
    """Main ingestion entry point."""
    db = get_db()
    chains = [chain] if chain else list(EAS_ENDPOINTS.keys())

    # Get wallet addresses to track
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, address, chain FROM wallet_profile WHERE is_active = true"
        )
        wallets = cur.fetchall()

    wallet_map = {}
    for w_id, w_addr, w_chain in wallets:
        wallet_map.setdefault(w_chain.lower(), []).append((w_id, w_addr))

    for c in chains:
        print(f"[EAS] Indexing {c}...")
        tracked_wallets = wallet_map.get(c, [])

        if not tracked_wallets:
            print(f"  ⊙ No tracked wallets for {c}")
            continue

        last_attestation_time = get_last_attestation_time(db, c)

        total_inserted = 0

        for w_id, w_addr in tracked_wallets:
            try:
                offset = 0
                max_attestation_time = last_attestation_time

                while True:
                    data = query_eas(c, ATTESTATIONS_BY_RECIPIENT, {
                        "recipient": w_addr,
                        "after": offset,
                    })

                    attestations = data.get("attestations", [])
                    if not attestations:
                        break

                    for att in attestations:
                        att_time = int(att.get("time", 0))
                        if att_time <= last_attestation_time:
                            continue

                        if insert_attestation(db, att, c):
                            total_inserted += 1

                        if att_time > max_attestation_time:
                            max_attestation_time = att_time

                    offset += len(attestations)
                    if len(attestations) < 100:
                        break

                    time.sleep(0.5)

                update_eas_indexer_status(c, max_attestation_time, "healthy")
                print(f"  ✓ Wallet {w_addr[:10]}...: indexed")

            except Exception as e:
                update_eas_indexer_status(c, last_attestation_time, "error", str(e))
                print(f"  ✗ Wallet {w_addr[:10]}...: {e}")

        log_ingestion(
            source_system="eas_api",
            source_table=f"{c}_attestations",
            source_id=c,
            target_table="attestation_record",
            target_id=None,
            operation="batch_insert",
            payload_hash=hash_payload({"chain": c, "wallets": len(tracked_wallets)}),
            status="success",
            rows_affected=total_inserted,
        )
        print(f"  Total: {total_inserted} attestations")

    db.commit()
    db.close()
    print(f"\n[EAS] Done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EAS attestation ingestion")
    parser.add_argument("--chain", choices=["optimism", "base"])
    args = parser.parse_args()
    run(chain=args.chain)
