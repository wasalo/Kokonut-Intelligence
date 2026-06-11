#!/usr/bin/env python3
"""
Subgraph Ingestion — EAS + Kokonut Contracts

Queries The Graph subgraphs for structured protocol data:
- EAS attestations and schemas
- Kokonut-specific contract events

Usage:
    python -m services.ingestion.subgraph_indexer
    python -m services.ingestion.subgraph_indexer --protocol eas
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import requests

from .base import get_db, log_ingestion, hash_payload, retry, update_indexer_status
from .config import EAS_GRAPHQL_URL

# Known subgraph endpoints (update as Kokonut deploys)
SUBGRAPH_ENDPOINTS = {
    "eas": "https://api.studio.thegraph.com/query/eas/attestations/v0.0.1",
    "eas_schema": "https://api.studio.thegraph.com/query/eas/schemas/v0.0.1",
}

# EAS GraphQL queries
ATTESTATIONS_QUERY = """
query GetAttestations($lastBlock: Int!, $first: Int!) {
    attestations(
        first: $first
        orderBy: blockNumber
        orderDirection: asc
        where: { blockNumber_gt: $lastBlock }
    ) {
        id
        txHash
        schema {
            id
        }
        attester
        recipient
        expirationTime
        revocationTime
        refUID
        data
        blockNumber
        blockTimestamp
        revocable
    }
}

SCHEMAS_QUERY = """
query GetSchemas($lastBlock: Int!, $first: Int!) {
    schemaRegistrations(
        first: $first
        orderBy: blockNumber
        orderDirection: asc
        where: { blockNumber_gt: $lastBlock }
    ) {
        id
        schema
        resolver
        revocable
        creator
        blockNumber
        blockTimestamp
        txHash
    }
}
"""


@retry(max_retries=3, backoff=2.0)
def query_subgraph(endpoint: str, query: str, variables: dict) -> dict:
    """Execute a GraphQL query against a subgraph."""
    resp = requests.post(
        endpoint,
        json={"query": query, "variables": variables},
        timeout=30,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


def insert_attestation(db, att: dict, schema_map: dict) -> str:
    """Insert attestation record into PostgreSQL."""
    schema_id = schema_map.get(att["schema"]["id"])
    attestation_uid = att["id"]
    block_ts = datetime.fromtimestamp(
        int(att["blockTimestamp"]), tz=timezone.utc
    ).isoformat()

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO attestation_record
                (schema_id, attestation_uid, subject_id, subject_type,
                 claim_data, status, attestation_tx, chain, reviewer_id, reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (attestation_uid) DO NOTHING
            RETURNING id
            """,
            (
                schema_id, attestation_uid,
                att.get("recipient", ""), "wallet",
                json.dumps({
                    "attester": att.get("attester"),
                    "data": att.get("data"),
                    "expiration_time": att.get("expirationTime"),
                    "revocation_time": att.get("revocationTime"),
                    "ref_uid": att.get("refUID"),
                    "revocable": att.get("revocable"),
                    "block_number": att.get("blockNumber"),
                }),
                "attested",
                att.get("txHash", ""),
                "ethereum",
                None, None,
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_schema(db, sch: dict) -> str:
    """Insert attestation schema into PostgreSQL."""
    schema_uid = sch["id"]
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO attestation_schema
                (schema_uid, name, schema_text, chain, resolver_address, active)
            VALUES (%s, %s, %s, %s, %s, true)
            ON CONFLICT (schema_uid) DO NOTHING
            RETURNING id
            """,
            (
                schema_uid,
                f"Schema {schema_uid[:10]}",
                sch.get("schema", ""),
                "ethereum",
                sch.get("resolver", ""),
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def run(protocol: str = None):
    """Main ingestion entry point."""
    db = get_db()
    protocols = [protocol] if protocol else list(SUBGRAPH_ENDPOINTS.keys())

    for proto in protocols:
        endpoint = SUBGRAPH_ENDPOINTS.get(proto)
        if not endpoint:
            print(f"[Subgraph] Unknown protocol: {proto}")
            continue

        print(f"[Subgraph] Indexing {proto}...")
        last_block = 0

        # Get last synced block
        with db.cursor() as cur:
            cur.execute(
                "SELECT last_synced_block FROM chain_indexer_status WHERE chain = 'ethereum' AND indexer_type = 'subgraph' AND metadata->>'protocol' = %s",
                (proto,),
            )
            row = cur.fetchone()
            if row:
                last_block = row[0] or 0

        try:
            start = time.time()

            if proto in ("eas",):
                # Fetch schemas first
                data = query_subgraph(endpoint, SCHEMAS_QUERY, {
                    "lastBlock": last_block, "first": 100
                })
                schemas = data.get("schemaRegistrations", [])
                schema_map = {}

                for sch in schemas:
                    sch_id = insert_schema(db, sch)
                    schema_map[sch["id"]] = sch_id

                # Fetch attestations
                data = query_subgraph(endpoint, ATTESTATIONS_QUERY, {
                    "lastBlock": last_block, "first": 100
                })
                attestations = data.get("attestations", [])

                success = 0
                max_block = last_block
                for att in attestations:
                    insert_attestation(db, att, schema_map)
                    block_num = int(att.get("blockNumber", 0))
                    if block_num > max_block:
                        max_block = block_num
                    success += 1

                elapsed_ms = int((time.time() - start) * 1000)
                log_ingestion(
                    source_system="subgraph",
                    source_table=f"{proto}_attestations",
                    source_id=proto,
                    target_table="attestation_record",
                    target_id=None,
                    operation="batch_insert",
                    payload_hash=hash_payload(attestations),
                    status="success",
                    rows_affected=success,
                    processing_time_ms=elapsed_ms,
                )
                update_indexer_status("ethereum", "subgraph", max_block, "healthy")
                print(f"  ✓ {success} attestations indexed (blocks {last_block}..{max_block})")

            elif proto == "eas_schema":
                # Schemas handled above
                print(f"  ⊙ Schemas handled with eas protocol")

        except Exception as e:
            update_indexer_status("ethereum", "subgraph", last_block, "error", str(e))
            log_ingestion(
                source_system="subgraph",
                source_table=f"{proto}_data",
                source_id=proto,
                target_table="attestation_record",
                target_id=None,
                operation="batch_insert",
                payload_hash="",
                status="failed",
                error_message=str(e),
            )
            print(f"  ✗ Error: {e}")

    db.commit()
    db.close()
    print(f"\n[Subgraph] Done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Subgraph ingestion")
    parser.add_argument("--protocol", choices=["eas", "eas_schema", "kokonut"])
    args = parser.parse_args()
    run(protocol=args.protocol)
