#!/usr/bin/env python3
"""
RPC Ingestion — Ethereum/L2 Wallet Activity

Fetches wallet activity from Ethereum, Optimism, Base, and Arbitrum
using web3.py. Inserts into wallet_activity_event (PostgreSQL) and
wallet_events (ClickHouse). Updates chain_indexer_status.

Usage:
    python -m services.ingestion.rpc_indexer
    python -m services.ingestion.rpc_indexer --chain ethereum
    python -m services.ingestion.rpc_indexer --wallet <address>
"""

import argparse
import time
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from web3 import Web3

from ..common.logging import get_logger
from .base import (
    get_db,
    hash_payload,
    insert_clickhouse_rows,
    update_indexer_status,
)
from .clickhouse_outbox import OutboxEnqueueError
from .config import CHAIN_RPC_MAP
from .rpc_provider import fetch_rpc_block_anchor, normalize_rpc_block_hash

logger = get_logger("ingestion.rpc")
_ACTIVITY_VALUE_QUANTUM = Decimal("0.00000001")

# Chain names with a configured RPC URL and supported by the direct CLI.
RPC_CLI_CHAINS = (
    "ethereum",
    "optimism",
    "base",
    "arbitrum",
    "celo",
    "celo-alfajores",
    "gnosis",
)

# Block range per request (limits API usage)
BLOCK_BATCH = 100

# Activity type detection
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _safe_failure_message(exc: Exception) -> str:
    """Summarize RPC and outbox failures without retaining provider details."""
    if isinstance(exc, OutboxEnqueueError):
        return "ClickHouse outbox enqueue failed"
    return f"RPC indexer failed ({type(exc).__name__})"


def _wei_to_eth(value: int) -> Decimal:
    """Convert a Web3 integer amount to the database's exact ETH precision."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("RPC wei value is invalid")
    return (Decimal(value) / Decimal(10**18)).quantize(
        _ACTIVITY_VALUE_QUANTUM, rounding=ROUND_HALF_UP
    )


def _activity_value_decimal(value) -> Decimal:
    """Return an activity amount as a finite eight-decimal ClickHouse value."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("RPC activity value is invalid") from None
    if not amount.is_finite():
        raise ValueError("RPC activity value is invalid")
    return amount.quantize(_ACTIVITY_VALUE_QUANTUM, rounding=ROUND_HALF_UP)


def _validate_ch_value(value: str, pattern, name: str) -> str:
    """Validate a value against a regex pattern for ClickHouse SQL safety."""
    if not pattern.match(value):
        raise ValueError(f"Invalid {name} for ClickHouse insert: {value!r}")
    return value


def get_web3(chain: str) -> Web3:
    """Get Web3 instance for a chain."""
    url = CHAIN_RPC_MAP.get(chain)
    if not url:
        raise ValueError(f"No RPC URL configured for chain: {chain}")
    return Web3(Web3.HTTPProvider(url))


def get_wallets(db, chain: str = None) -> list:
    """Get tracked wallets from wallet_profile table."""
    with db.cursor() as cur:
        if chain:
            cur.execute(
                "SELECT id, address, chain, role, label FROM wallet_profile WHERE chain = %s AND is_active = true",
                (chain,),
            )
        else:
            cur.execute(
                "SELECT id, address, chain, role, label FROM wallet_profile WHERE is_active = true"
            )
        return cur.fetchall()


def fetch_balance(w3: Web3, address: str, block_identifier=None) -> int:
    """Fetch an ETH balance in wei, optionally at one selected block."""
    checksum = Web3.to_checksum_address(address)
    if block_identifier is None:
        return w3.eth.get_balance(checksum)
    return w3.eth.get_balance(checksum, block_identifier=block_identifier)


def fetch_latest_block(w3: Web3) -> int:
    """Get latest block number."""
    return w3.eth.block_number


def fetch_block_anchor(w3: Web3) -> tuple[int, int, str]:
    """Capture one block number, timestamp, and hash for a chain run."""
    return fetch_rpc_block_anchor(w3)


def parse_activity(tx: dict, wallet_id: str, chain: str) -> dict:
    """Parse a transaction into wallet_activity_event format."""
    to_addr = tx.get("to", "") or ""
    value = int(tx.get("value", 0)) if tx.get("value") else 0

    # Determine activity type
    if value > 0:
        activity_type = "transfer"
    elif tx.get("input") and len(tx["input"]) > 2:
        activity_type = "contract_interaction"
    else:
        activity_type = "transfer"

    # Convert value from wei to ether
    value_eth = _wei_to_eth(value)

    timestamp = datetime.fromtimestamp(
        tx.get("timestamp", time.time()), tz=timezone.utc
    ).isoformat()

    return {
        "wallet_id": wallet_id,
        "chain": chain,
        "tx_hash": tx.get("hash", ""),
        "block_number": tx.get("blockNumber", 0),
        "block_timestamp": timestamp,
        "from_address": tx.get("from", ""),
        "to_address": to_addr,
        "value": value_eth,
        "token": "ETH",
        "gas_used": tx.get("gas", 0),
        "gas_price": tx.get("gasPrice", 0),
        "status": "success" if tx.get("receipt", {}).get("status", 1) == 1 else "failed",
        "activity_type": activity_type,
    }


def insert_activity(db, record: dict) -> str | None:
    """Insert wallet activity, suppressing exact identity replays safely."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, block_number, from_address, to_address, value, token,
                   gas_used, gas_price, status, activity_type
              FROM wallet_activity_event
             WHERE wallet_id = %s AND chain = %s AND tx_hash = %s
             ORDER BY id
             LIMIT 1
             FOR UPDATE
            """,
            (record["wallet_id"], record["chain"], record["tx_hash"]),
        )
        existing = cur.fetchone()
        if existing:
            try:
                stored_value = Decimal(str(existing[4])).quantize(
                    _ACTIVITY_VALUE_QUANTUM, rounding=ROUND_HALF_UP
                )
                requested_value = Decimal(str(record["value"])).quantize(
                    _ACTIVITY_VALUE_QUANTUM, rounding=ROUND_HALF_UP
                )
                same_value = stored_value == requested_value
            except (InvalidOperation, TypeError, ValueError):
                same_value = False
            same_record = (
                existing[1] == record["block_number"]
                and existing[2] == record["from_address"]
                and (existing[3] or "").lower() == (record["to_address"] or "").lower()
                and same_value
                and existing[5] == record["token"]
                and Decimal(str(existing[6])) == Decimal(str(record["gas_used"]))
                and Decimal(str(existing[7])) == Decimal(str(record["gas_price"]))
                and existing[8] == record["status"]
                and existing[9] == record["activity_type"]
            )
            if not same_record:
                raise ValueError("RPC activity identity conflicts with stored record")
            return None
        cur.execute(
            """
            INSERT INTO wallet_activity_event
                (wallet_id, chain, tx_hash, block_number, block_timestamp,
                 from_address, to_address, value, token, gas_used, gas_price,
                 status, activity_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                record["wallet_id"], record["chain"], record["tx_hash"],
                record["block_number"], record["block_timestamp"],
                record["from_address"], record["to_address"],
                record["value"], record["token"],
                record["gas_used"], record["gas_price"],
                record["status"], record["activity_type"],
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_activity_clickhouse(records: list[dict], conn=None) -> None:
    """Queue wallet activity durably when the PostgreSQL transaction is available."""
    rows = []
    for rec in records:
        timestamp = rec.get("block_timestamp", "")
        if isinstance(timestamp, datetime):
            ts = timestamp
        else:
            try:
                ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(timezone.utc)

        wallet_address = rec.get("to_address", "") or rec.get("from_address", "")
        rows.append([
            ts,
            str(wallet_address),
            str(rec.get("chain", "")),
            str(rec.get("tx_hash", "")),
            int(rec.get("block_number", 0)),
            str(rec.get("activity_type", "")),
            _activity_value_decimal(rec.get("value", 0)),
            str(rec.get("token", "ETH")),
            str(rec.get("status", "success")),
            {},
        ])

    if not rows:
        return

    try:
        if conn is not None:
            from .clickhouse_outbox import enqueue

            event_key = "rpc:wallet_events:" + hash_payload(records)
            enqueue(
                conn,
                event_key=event_key,
                source_table="wallet_activity_event",
                source_id=event_key,
                target_table="wallet_events",
                columns=[
                    "timestamp", "wallet_address", "chain", "tx_hash",
                    "block_number", "event_type", "value", "token", "status", "metadata",
                ],
                rows=rows,
                payload_hash=hash_payload(records),
            )
            return
        insert_clickhouse_rows(
            "wallet_events",
            [
                "timestamp", "wallet_address", "chain", "tx_hash",
                "block_number", "event_type", "value", "token", "status", "metadata",
            ],
            rows,
        )
    except OutboxEnqueueError:
        raise OutboxEnqueueError("ClickHouse outbox enqueue failed") from None
    except Exception as e:
        if conn is not None:
            raise OutboxEnqueueError("Could not enqueue the canonical ClickHouse projection") from None
        logger.warning("ClickHouse insert failed (%s)", type(e).__name__)


def run(chain: str = None, wallet_address: str = None):
    """Main ingestion entry point."""
    db = get_db()
    attempted_chains = set()
    try:
        wallets = get_wallets(db, chain)

        if wallet_address:
            wallets = [w for w in wallets if w[1].lower() == wallet_address.lower()]

        if not wallets:
            logger.info("No active wallets found.")
            return

        # Coordinate the manual compatibility CLI with the isolated scheduled
        # worker. The worker uses the session-level form of this same lock key.
        for w_chain in sorted({wallet[2] for wallet in wallets}):
            with db.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"kokonut:rpc-indexer:{w_chain}",),
                )

        logger.info("Indexing %d wallets...", len(wallets))
        all_records = []
        anchors = {}
        observed_blocks = {}
        failed_chains = {}

        for wallet_id, address, w_chain, role, label in wallets:
            attempted_chains.add(w_chain)
            if w_chain in failed_chains and w_chain not in anchors:
                continue
            with db.cursor() as cur:
                cur.execute("SAVEPOINT rpc_wallet_activity")
            try:
                if w_chain not in anchors:
                    w3 = get_web3(w_chain)
                    anchors[w_chain] = (w3, *fetch_block_anchor(w3))
                w3, current_block, block_timestamp, _block_hash = anchors[w_chain]
                checksum = Web3.to_checksum_address(address)

                balance_wei = fetch_balance(
                    w3, checksum, block_identifier=current_block
                )
                balance_eth = _wei_to_eth(balance_wei)

                # Record a summary activity event
                record = {
                    "wallet_id": wallet_id,
                    "chain": w_chain,
                    "tx_hash": f"balance-check-{w_chain}-{str(wallet_id)}-{current_block}",
                    "block_number": current_block,
                    "block_timestamp": datetime.fromtimestamp(
                        block_timestamp, tz=timezone.utc
                    ).isoformat(),
                    "from_address": "",
                    "to_address": checksum,
                    "value": balance_eth,
                    "token": "ETH",
                    "gas_used": 0,
                    "gas_price": 0,
                    "status": "success",
                    "activity_type": "balance_check",
                }

                pg_id = insert_activity(db, record)
                with db.cursor() as cur:
                    cur.execute("RELEASE SAVEPOINT rpc_wallet_activity")
                if pg_id:
                    all_records.append(record)
                observed_blocks[w_chain] = max(
                    current_block, observed_blocks.get(w_chain, current_block)
                )
                logger.info("  ✓ %s: block %d, balance %.4f ETH", label or address[:10], current_block, balance_eth)

            except Exception as e:
                with db.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT rpc_wallet_activity")
                    cur.execute("RELEASE SAVEPOINT rpc_wallet_activity")
                failure = f"RPC wallet request failed ({type(e).__name__})"
                failed_chains[w_chain] = failure
                logger.error("  ✗ %s failed (%s)", label or address[:10], type(e).__name__)

        for w_chain, (w3, block_number, _timestamp, block_hash) in anchors.items():
            if normalize_rpc_block_hash(w3.eth.get_block(block_number)) != block_hash:
                raise RuntimeError("RPC block changed during wallet snapshot run")

        # Keep each chain's status in the same transaction as its wallet rows
        # and any ClickHouse outbox intent. A partial chain failure is never
        # reported as healthy.
        for w_chain in sorted(attempted_chains):
            if w_chain in failed_chains:
                update_indexer_status(
                    w_chain, "rpc", None, "error", failed_chains[w_chain], db=db
                )
            else:
                update_indexer_status(
                    w_chain,
                    "rpc",
                    observed_blocks.get(w_chain),
                    "healthy",
                    db=db,
                )

        # Commit PostgreSQL records and their ClickHouse outbox entry atomically.
        if all_records:
            insert_activity_clickhouse(all_records, db)
        db.commit()
    except Exception as exc:
        db.rollback()
        safe_error = _safe_failure_message(exc)
        if attempted_chains:
            try:
                for w_chain in sorted(attempted_chains):
                    update_indexer_status(
                        w_chain, "rpc", None, "error", safe_error, db=db
                    )
                db.commit()
            except Exception as status_exc:
                db.rollback()
                logger.error(
                    "Could not persist RPC indexer failure status (%s)",
                    type(status_exc).__name__,
                )
        if isinstance(exc, OutboxEnqueueError):
            raise OutboxEnqueueError(safe_error) from None
        raise RuntimeError(safe_error) from None
    finally:
        db.close()
    logger.info("Done: %d wallets indexed", len(all_records))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPC wallet activity ingestion")
    parser.add_argument(
        "--chain",
        choices=RPC_CLI_CHAINS,
    )
    parser.add_argument("--wallet", help="Specific wallet address")
    args = parser.parse_args()
    run(chain=args.chain, wallet_address=args.wallet)
