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
import time
from datetime import datetime, timezone

from ..common.logging import get_logger
from .base import get_db, hash_payload, log_ingestion, post_clickhouse_rows, retry, update_indexer_status
from .clickhouse_outbox import OutboxEnqueueError, enqueue
from .eas_provider import (
    ATTESTATIONS_BY_RECIPIENT,
    EAS_ENDPOINTS,
    execute_eas_query,
)

logger = get_logger("ingestion.eas")


@retry(max_retries=3, backoff=2.0)
def query_eas(chain: str, query: str, variables: dict) -> dict:
    """Execute GraphQL query against EAS."""
    return execute_eas_query(chain, query, variables)


def insert_attestation(db, att: dict, chain: str) -> str:
    """Insert EAS attestation into PostgreSQL."""
    attestation_uid = att["id"]
    block_ts = datetime.fromtimestamp(int(att.get("time", 0)), tz=timezone.utc).isoformat()

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
                (schema_id, attestation_uid, subject_type,
                 claim_data, status, tx_hash, chain, attested_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (attestation_uid) DO NOTHING
            RETURNING id
            """,
            (
                schema_id,
                attestation_uid,
                "wallet",
                json.dumps(
                    {
                        "attester": att.get("attester"),
                        "recipient": att.get("recipient"),
                        "data": att.get("data"),
                        "revocable": att.get("revocable"),
                        "revoked": att.get("revoked"),
                        "expiration_time": att.get("expirationTime"),
                    }
                ),
                "rejected" if att.get("revoked") else "published",
                att.get("txid", ""),
                chain,
                block_ts,
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_clickhouse(chain: str, att: dict, status: str, conn=None) -> None:
    """Queue canonical attestation; direct writes are demo-only when conn is absent."""
    attestation_uid = att.get("id", "")
    schema_uid = att.get("schema", {}).get("id", "") if att.get("schema") else ""
    attester = att.get("attester", "")
    recipient = att.get("recipient", "")

    block_ts = datetime.fromtimestamp(int(att.get("time", 0)), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    columns = [
        "timestamp",
        "attestation_uid",
        "schema_uid",
        "chain",
        "attester",
        "recipient",
        "subject_type",
        "status",
        "revoked",
        "metadata",
    ]
    rows = [
        [
            block_ts,
            attestation_uid,
            schema_uid,
            chain,
            attester,
            recipient,
            "wallet",
            status,
            att.get("revoked", False),
            {},
        ]
    ]
    try:
        if conn is not None:
            payload_hash = hash_payload(att)
            enqueue(
                conn,
                event_key=f"attestation:attestation_events:{attestation_uid}",
                source_table="attestation_record",
                source_id=attestation_uid,
                target_table="attestation_events",
                columns=columns,
                rows=rows,
                payload_hash=payload_hash,
            )
            return
        # No PostgreSQL transaction means this is an explicit demo/maintenance path.
        post_clickhouse_rows(
            "attestation_events",
            columns,
            rows,
        )
    except Exception as e:
        if conn is not None:
            raise
        logger.warning("ClickHouse insert failed (%s)", type(e).__name__)


def get_last_attestation_time(db, chain: str, wallet_id: str) -> int:
    """Read or initialize the timestamp cursor for one tracked recipient."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO eas_indexer_cursor (chain, wallet_id, last_attestation_time)
            VALUES (%s, %s, 0)
            ON CONFLICT (chain, wallet_id) DO NOTHING
            """,
            (chain, wallet_id),
        )
        cur.execute(
            """
            SELECT last_attestation_time
              FROM eas_indexer_cursor
             WHERE chain = %s AND wallet_id = %s
             FOR UPDATE
            """,
            (chain, wallet_id),
        )
        row = cur.fetchone()
    return int(row[0]) if row and row[0] else 0


def advance_attestation_cursor(db, chain: str, wallet_id: str, last_attestation_time: int) -> None:
    """Advance one recipient cursor without allowing a regression."""
    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE eas_indexer_cursor
               SET last_attestation_time = GREATEST(last_attestation_time, %s),
                   updated_at = NOW()
             WHERE chain = %s AND wallet_id = %s
            """,
            (last_attestation_time, chain, wallet_id),
        )
        if cur.rowcount != 1:
            raise RuntimeError("EAS recipient cursor was not updated")


def get_chain_attestation_watermark(db, chain: str) -> int:
    """Return the highest recipient cursor for status display only."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(last_attestation_time), 0)
              FROM eas_indexer_cursor
             WHERE chain = %s
            """,
            (chain,),
        )
        row = cur.fetchone()
    return int(row[0]) if row else 0


def run(chain: str = None):
    """Main ingestion entry point."""
    if chain is not None and chain not in EAS_ENDPOINTS:
        raise ValueError(f"Unsupported EAS chain: {chain}")

    db = get_db()
    failed_chains = []
    try:
        chains = [chain] if chain else list(EAS_ENDPOINTS.keys())

        # Get wallet addresses to track
        with db.cursor() as cur:
            cur.execute("SELECT id, address, chain FROM wallet_profile WHERE is_active = true")
            wallets = cur.fetchall()

        wallet_map = {}
        for w_id, w_addr, w_chain in wallets:
            wallet_map.setdefault(w_chain.lower(), []).append((w_id, w_addr))

        for c in chains:
            logger.info("Indexing %s...", c)
            tracked_wallets = wallet_map.get(c, [])

            if not tracked_wallets:
                logger.info("  ⊙ No tracked wallets for %s", c)
                continue

            # Serialize chain scans so cursor and status writes from overlapping
            # runs cannot race each other.
            with db.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"kokonut:eas-indexer:{c}",),
                )

            chain_errors = []
            total_inserted = 0

            for w_id, w_addr in tracked_wallets:
                recipient_cursor = get_last_attestation_time(db, c, w_id)
                wallet_max_attestation_time = recipient_cursor
                wallet_inserted = 0
                with db.cursor() as cur:
                    cur.execute("SAVEPOINT eas_wallet_index")
                try:
                    offset = 0

                    while True:
                        data = query_eas(
                            c,
                            ATTESTATIONS_BY_RECIPIENT,
                            {
                                "recipient": w_addr,
                                "after": offset,
                            },
                        )

                        attestations = data.get("attestations", [])
                        if not attestations:
                            break

                        for att in attestations:
                            att_time = int(att.get("time", 0))
                            # Revisit the cursor's second on every run. Multiple
                            # attestations in one block share a timestamp, and a
                            # provider may index a peer after an earlier page.
                            # UID conflict suppression makes this boundary scan
                            # idempotent while catching newly visible peers.
                            if att_time < recipient_cursor:
                                continue

                            if insert_attestation(db, att, c):
                                wallet_inserted += 1
                                # Dual-write to ClickHouse
                                status = "rejected" if att.get("revoked") else "published"
                                insert_clickhouse(c, att, status, db)

                            if att_time > wallet_max_attestation_time:
                                wallet_max_attestation_time = att_time

                        offset += len(attestations)
                        if len(attestations) < 100:
                            break

                        time.sleep(0.5)

                    advance_attestation_cursor(db, c, w_id, wallet_max_attestation_time)
                    with db.cursor() as cur:
                        cur.execute("RELEASE SAVEPOINT eas_wallet_index")
                    total_inserted += wallet_inserted
                    logger.info("  ✓ Wallet %s...: indexed", w_addr[:10])

                except OutboxEnqueueError:
                    db.rollback()
                    raise OutboxEnqueueError("ClickHouse outbox enqueue failed") from None
                except Exception as e:
                    with db.cursor() as cur:
                        cur.execute("ROLLBACK TO SAVEPOINT eas_wallet_index")
                        cur.execute("RELEASE SAVEPOINT eas_wallet_index")
                    safe_error = f"{w_addr[:10]}: EAS recipient fetch failed ({type(e).__name__})"
                    chain_errors.append(safe_error)
                    logger.error("  ✗ Wallet %s... failed (%s)", w_addr[:10], type(e).__name__)

            chain_status = "error" if chain_errors else "healthy"
            watermark = get_chain_attestation_watermark(db, c)
            error_message = "; ".join(chain_errors[:3])[:500] or None
            update_indexer_status(
                c,
                "eas",
                status=chain_status,
                error_message=error_message,
                metadata={"last_attestation_time": watermark},
                db=db,
            )
            log_ingestion(
                source_system="eas_api",
                source_table=f"{c}_attestations",
                source_id=c,
                target_table="attestation_record",
                target_id=None,
                operation="batch_insert",
                payload_hash=hash_payload({"chain": c, "wallets": len(tracked_wallets)}),
                status="partial" if chain_errors else "success",
                error_message=error_message,
                rows_affected=total_inserted,
                db=db,
            )
            if chain_errors:
                failed_chains.append(c)
            logger.info("  Total: %d attestations", total_inserted)

        db.commit()
        if failed_chains:
            raise RuntimeError("EAS indexing incomplete for chain(s): " + ", ".join(failed_chains))
        logger.info("Done")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EAS attestation ingestion")
    parser.add_argument("--chain", choices=["optimism", "base", "celo"])
    args = parser.parse_args()
    run(chain=args.chain)
