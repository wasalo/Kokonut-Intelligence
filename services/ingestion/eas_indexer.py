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

from .base import get_db, log_ingestion, hash_payload, retry, update_indexer_status

# EAS GraphQL endpoints per chain
EAS_ENDPOINTS = {
    "ethereum": "https://attest.sh",
    "optimism": "https://optimism.easscan.org",
    "base": "https://base.easscan.org",
}

# GraphQL queries
ATTESTATIONS_BY_RECIPIENT = """
query GetAttestations($recipient: String!, $after: Int!) {
    attestations(
        where: { recipient: $recipient }
        order: { blockNumber: desc }
        take: 100
        skip: $after
    ) {
        id
        txHash
        schema { id schema }
        attester
        recipient
        data
        blockNumber
        blockTimestamp
        revocable
        revoked
        expirationTime
    }
}

SCHEMAS_BY_CREATOR = """
query GetSchemas($creator: String!, $after: Int!) {
    schemaRegistrations(
        where: { creator: $creator }
        order: { blockNumber: desc }
        take: 100
        skip: $after
    ) {
        id
        schema
        creator
        resolver
        revocable
        blockNumber
        blockTimestamp
        txHash
    }
}
"""


@retry(max_retries=3, backoff=2.0)
def query_eas(chain: str, query: str, variables: dict) -> dict:
    """Execute GraphQL query against EAS."""
    endpoint = EAS_ENDPOINTS.get(chain, EAS_ENDPOINTS["ethereum"])
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
        int(att.get("blockTimestamp", 0)), tz=timezone.utc
    ).isoformat()

    with db.cursor() as cur:
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
                (schema_id, attestation_uid, subject_id, subject_type,
                 claim_data, status, attestation_tx, chain)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (attestation_uid) DO NOTHING
            RETURNING id
            """,
            (
                schema_id, attestation_uid,
                att.get("recipient", ""), "wallet",
                json.dumps({
                    "attester": att.get("attester"),
                    "data": att.get("data"),
                    "block_number": att.get("blockNumber"),
                    "revocable": att.get("revocable"),
                    "revoked": att.get("revoked"),
                    "expiration_time": att.get("expirationTime"),
                }),
                "revoked" if att.get("revoked") else "attested",
                att.get("txHash", ""),
                chain,
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


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
        wallet_map.setdefault(w_chain.lower(), []).append((w_id, w_addr.lower()))

    for c in chains:
        print(f"[EAS] Indexing {c}...")
        tracked_wallets = wallet_map.get(c, [])

        if not tracked_wallets:
            print(f"  ⊙ No tracked wallets for {c}")
            continue

        last_block = 0
        with db.cursor() as cur:
            cur.execute(
                "SELECT last_synced_block FROM chain_indexer_status WHERE chain = %s AND indexer_type = 'eas'",
                (c,),
            )
            row = cur.fetchone()
            if row:
                last_block = row[0] or 0

        total_inserted = 0

        for w_id, w_addr in tracked_wallets:
            try:
                offset = 0
                max_block = last_block

                while True:
                    data = query_eas(c, ATTESTATIONS_BY_RECIPIENT, {
                        "recipient": w_addr,
                        "after": offset,
                    })

                    attestations = data.get("attestations", [])
                    if not attestations:
                        break

                    for att in attestations:
                        block_num = int(att.get("blockNumber", 0))
                        if block_num <= last_block:
                            continue

                        insert_attestation(db, att, c)
                        total_inserted += 1

                        if block_num > max_block:
                            max_block = block_num

                    offset += len(attestations)
                    if len(attestations) < 100:
                        break

                    time.sleep(0.5)

                update_indexer_status(c, "eas", max_block, "healthy")
                print(f"  ✓ Wallet {w_addr[:10]}...: indexed")

            except Exception as e:
                update_indexer_status(c, "eas", last_block, "error", str(e))
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
    parser.add_argument("--chain", choices=["ethereum", "optimism", "base"])
    args = parser.parse_args()
    run(chain=args.chain)
