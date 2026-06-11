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
import json
import sys
import time
from datetime import datetime, timezone

from web3 import Web3

from .base import (
    get_db, log_ingestion, hash_payload, retry,
    update_indexer_status, get_last_synced_block, now_utc,
)
from .config import CHAIN_RPC_MAP, CH_HOST, CH_USER, CH_PASSWORD

# Block range per request (limits API usage)
BLOCK_BATCH = 100

# Activity type detection
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


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


def fetch_transactions(w3: Web3, address: str, from_block: int, to_block: int) -> list:
    """Fetch transactions for an address in a block range."""
    try:
        # Get normal transactions
        txs = []
        for tx_hash in w3.eth.get_transaction_by_block_range(from_block, to_block, address):
            txs.append(tx_hash)
        return txs
    except Exception:
        # Fallback: use filter for recent blocks
        try:
            tx_filter = w3.eth.filter({
                "fromBlock": hex(from_block),
                "toBlock": hex(to_block),
                "address": address,
            })
            return tx_filter.get_all_entries()
        except Exception as e:
            print(f"  [RPC] Failed to fetch transactions: {e}")
            return []


def fetch_balance(w3: Web3, address: str) -> int:
    """Fetch current ETH balance in wei."""
    return w3.eth.get_balance(Web3.to_checksum_address(address))


def fetch_latest_block(w3: Web3) -> int:
    """Get latest block number."""
    return w3.eth.block_number


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
    value_eth = value / 1e18 if value else 0

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


def insert_activity(db, record: dict) -> str:
    """Insert wallet activity into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wallet_activity_event
                (wallet_id, chain, tx_hash, block_number, block_timestamp,
                 from_address, to_address, value, token, gas_used, gas_price,
                 status, activity_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tx_hash) DO NOTHING
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


def insert_activity_clickhouse(records: list[dict]) -> None:
    """Insert wallet activity into ClickHouse wallet_events table."""
    try:
        import clickhouse_connect
        ch = clickhouse_connect.get_client(
            host=CH_HOST, port=8123, username=CH_USER, password=CH_PASSWORD,
        )
        rows = []
        for rec in records:
            rows.append([
                rec.get("chain", ""),
                rec.get("to_address", "") or rec.get("from_address", ""),
                rec.get("block_timestamp", ""),
                rec.get("activity_type", ""),
                rec.get("tx_hash", ""),
                rec.get("value", 0),
                rec.get("token", "ETH"),
                rec.get("status", "success"),
                json.dumps({}),
            ])
        if rows:
            ch.insert(
                "wallet_events",
                rows,
                column_names=[
                    "chain", "wallet_address", "timestamp", "event_type",
                    "tx_hash", "value", "token", "status", "metadata",
                ],
            )
    except Exception as e:
        print(f"  [RPC] ClickHouse insert failed: {e}")


def run(chain: str = None, wallet_address: str = None):
    """Main ingestion entry point."""
    db = get_db()
    wallets = get_wallets(db, chain)

    if wallet_address:
        wallets = [w for w in wallets if w[1].lower() == wallet_address.lower()]

    if not wallets:
        print("[RPC] No active wallets found.")
        return

    print(f"[RPC] Indexing {len(wallets)} wallets...")
    all_records = []

    for wallet_id, address, w_chain, role, label in wallets:
        try:
            w3 = get_web3(w_chain)
            checksum = Web3.to_checksum_address(address)

            # Get last synced block
            last_block = get_last_synced_block(w_chain, "rpc") or (fetch_latest_block(w3) - BLOCK_BATCH)
            current_block = fetch_latest_block(w3)

            if last_block >= current_block:
                print(f"  ⊙ {label or address[:10]}: already synced to block {last_block}")
                continue

            from_block = last_block + 1
            to_block = min(from_block + BLOCK_BATCH - 1, current_block)
            print(f"  → {label or address[:10]}: blocks {from_block}..{to_block}")

            txs = fetch_transactions(w3, checksum, from_block, to_block)
            success = 0

            for tx in txs:
                record = parse_activity(tx, wallet_id, w_chain)
                pg_id = insert_activity(db, record)
                if pg_id:
                    all_records.append(record)
                    success += 1

            log_ingestion(
                source_system="rpc",
                source_table=f"{w_chain}_transactions",
                source_id=address,
                target_table="wallet_activity_event",
                target_id=None,
                operation="batch_insert",
                payload_hash=hash_payload({"from": from_block, "to": to_block}),
                status="success",
                rows_affected=success,
            )

            # Update indexer status
            update_indexer_status(w_chain, "rpc", to_block, "healthy")
            print(f"    ✓ {success} transactions indexed")

        except Exception as e:
            update_indexer_status(w_chain, "rpc", None, "error", str(e))
            print(f"    ✗ Error: {e}")

    db.commit()

    # Insert into ClickHouse
    if all_records:
        insert_activity_clickhouse(all_records)

    db.close()
    print(f"\n[RPC] Done: {len(all_records)} total transactions indexed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPC wallet activity ingestion")
    parser.add_argument("--chain", choices=["ethereum", "optimism", "base", "arbitrum"])
    parser.add_argument("--wallet", help="Specific wallet address")
    args = parser.parse_args()
    run(chain=args.chain, wallet_address=args.wallet)
