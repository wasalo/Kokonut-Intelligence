#!/usr/bin/env python3
"""
Gnosis Chain Ingestion — Kokonut Moloch DAO Events

Indexes Moloch v2 contract events from Gnosis Chain:
- SubmitProposal, ProcessProposal, VoteProposal
- Ragequit, Trade, UpdateDelegate, Withdraw, CancelProposal

Stores events in governance_event and treasury_event (PostgreSQL).
Updates chain_indexer_status.

Usage:
    python3 -m services.ingestion.gnosis_indexer
    python3 -m services.ingestion.gnosis_indexer --from-block 35000000
    python3 -m services.ingestion.gnosis_indexer --from-block 35000000 --to-block 35010000
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from web3 import Web3

from ..common.logging import get_logger
from .base import (
    get_db, log_ingestion, hash_payload, retry,
    update_indexer_status, get_last_synced_block, now_utc,
)
from .config import (
    GNOSIS_RPC_URL, KOKONUT_DAO_CHAIN, KOKONUT_MOLOCH_ADDRESSES,
    CH_HOST, CH_PORT, CH_USER, CH_PASSWORD,
)

logger = get_logger("ingestion.gnosis")

# Validation patterns for ClickHouse SQL interpolation
_STR_RE = re.compile(r'^[a-zA-Z0-9_\-\. ]+$')
_STR_LOOSE_RE = re.compile(r'^[a-zA-Z0-9_\-\.:/ ]+$')

# Block range per request (Gnosis produces ~5s blocks)
BLOCK_BATCH = 500

# Moloch v2 event topic hashes (keccak256 of event signature)
EVENT_TOPICS = {
    "0xf947ed47cdf2861193802b34d5ee0e59be9c9ef5eb20b1210c69205ebe0c6371": "SubmitProposal",
    "0x36bb81bc23e1666e90ce29b613dfccad1f8bf01c6793afa329d1a1bef0e7d88a": "ProcessProposal",
    "0xb3af8d0ccb8c5065b2daf8bb24b7a0ac9a8822fac445978a1524fb9a6f560e1f": "VoteProposal",
    "0xcad1a1c68982832d9abc314de8a1e5d5e8c81b0588961e360766736d10c3be1a": "Ragequit",
    "0x4b5796113f074ebf8f11d5bcdeb6349b2fbe47abed78419cdcdbbc15c6fcf845": "Trade",
    "0x53be197ae241b2f77a83eb69d1fe33148f114319ee40c630651b9974673e39cf": "UpdateDelegate",
    "0x9b1bfa7fa9ee420a16e124f794c35ac9f90472acc99140eb2f6447c714cad8eb": "Withdraw",
    "0x100793ceffc8a85253b319a0c8021baa6c6f289b4d548dbcc21abf086b44283c": "CancelProposal",
}

# Vote choices
VOTE_CHOICES = {0: "no", 1: "yes", 2: "block"}


def _validate_ch_value(value: str, pattern: re.Pattern, name: str) -> str:
    """Validate a value against a regex pattern for ClickHouse SQL safety."""
    if not pattern.match(value):
        raise ValueError(f"Invalid {name} for ClickHouse insert: {value!r}")
    return value


def load_abi() -> list:
    """Load Moloch v2 ABI from contracts/abis/."""
    abi_path = Path(__file__).parent.parent.parent / "contracts" / "abis" / "MolochV2.json"
    if not abi_path.exists():
        raise FileNotFoundError(f"Moloch v2 ABI not found: {abi_path}")
    with open(abi_path) as f:
        return json.load(f)


def get_web3() -> Web3:
    """Get Web3 instance for Gnosis Chain."""
    return Web3(Web3.HTTPProvider(GNOSIS_RPC_URL))


def get_moloch_contract(w3: Web3):
    """Get Moloch v2 contract instance (Token Manager)."""
    abi = load_abi()
    address = Web3.to_checksum_address(KOKONUT_MOLOCH_ADDRESSES["token_manager"])
    return w3.eth.contract(address=address, abi=abi)


def get_treasury_contract(w3: Web3):
    """Get Treasury SAFE contract instance."""
    abi = load_abi()
    address = Web3.to_checksum_address(KOKONUT_MOLOCH_ADDRESSES["treasury"])
    return w3.eth.contract(address=address, abi=abi)


def fetch_block_timestamp(w3: Web3, block_number: int) -> datetime:
    """Fetch block timestamp and convert to UTC datetime."""
    block = w3.eth.get_block(block_number)
    return datetime.fromtimestamp(block["timestamp"], tz=timezone.utc)


def get_wallet_id(db, address: str, chain: str) -> Optional[str]:
    """Look up wallet_id from wallet_profile by address and chain."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM wallet_profile WHERE LOWER(address) = LOWER(%s) AND chain = %s",
            (address, chain),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_governance_event(db, record: dict) -> Optional[str]:
    """Insert governance event into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO governance_event
                (wallet_id, protocol_id, chain, event_type, proposal_id,
                 proposal_title, vote_choice, amount, token, tx_hash,
                 block_number, block_timestamp, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                record.get("wallet_id"),
                record.get("protocol_id"),
                record["chain"],
                record["event_type"],
                record.get("proposal_id"),
                record.get("proposal_title"),
                record.get("vote_choice"),
                record.get("amount"),
                record.get("token"),
                record["tx_hash"],
                record["block_number"],
                record["block_timestamp"],
                json.dumps(record.get("metadata", {})),
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_treasury_event(db, record: dict) -> Optional[str]:
    """Insert treasury event into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO treasury_event
                (location_id, wallet_id, chain, event_date, flow_direction,
                 amount, token, usd_value, source, tx_hash, block_number,
                 verified, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                record.get("location_id"),
                record.get("wallet_id"),
                record["chain"],
                record.get("event_date", now_utc().date()),
                record["flow_direction"],
                record["amount"],
                record.get("token", ""),
                record.get("usd_value"),
                record.get("source", "moloch_dao"),
                record["tx_hash"],
                record["block_number"],
                record.get("verified", True),
                json.dumps(record.get("metadata", {})),
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def decode_submit_proposal(args: dict, tx_hash: str, block_number: int,
                           block_timestamp: datetime, w3: Web3) -> dict:
    """Decode SubmitProposal event into governance_event record."""
    return {
        "chain": KOKONUT_DAO_CHAIN,
        "event_type": "proposal_created",
        "proposal_id": str(args.get("proposalIndex", "")),
        "proposal_title": args.get("details", "")[:500],
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "amount": float(args.get("tributeOffered", 0)) / 1e18 if args.get("tributeOffered") else 0,
        "token": args.get("tributeToken", ""),
        "metadata": {
            "proposer": args.get("proposer", ""),
            "shares_requested": str(args.get("sharesRequested", 0)),
            "loot_requested": str(args.get("lootRequested", 0)),
            "payment_requested": str(args.get("paymentRequested", 0)),
            "payment_token": args.get("paymentToken", ""),
        },
    }


def decode_vote_proposal(args: dict, tx_hash: str, block_number: int,
                         block_timestamp: datetime) -> dict:
    """Decode VoteProposal event into governance_event record."""
    vote = args.get("vote", 0)
    return {
        "chain": KOKONUT_DAO_CHAIN,
        "event_type": "vote_cast",
        "proposal_id": str(args.get("proposalIndex", "")),
        "vote_choice": VOTE_CHOICES.get(vote, str(vote)),
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "metadata": {
            "voter": args.get("memberAddress", ""),
            "vote_raw": vote,
        },
    }


def decode_process_proposal(args: dict, tx_hash: str, block_number: int,
                            block_timestamp: datetime) -> dict:
    """Decode ProcessProposal event into governance_event record."""
    did_pass = args.get("didPass", False)
    return {
        "chain": KOKONUT_DAO_CHAIN,
        "event_type": "proposal_executed" if did_pass else "proposal_failed",
        "proposal_id": str(args.get("proposalIndex", "")),
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "metadata": {"did_pass": did_pass},
    }


def decode_ragequit(args: dict, tx_hash: str, block_number: int,
                    block_timestamp: datetime) -> dict:
    """Decode Ragequit event into governance_event record."""
    shares = int(args.get("sharesToBurn", 0))
    loot = int(args.get("lootToBurn", 0))
    return {
        "chain": KOKONUT_DAO_CHAIN,
        "event_type": "ragequit",
        "amount": float(shares + loot) / 1e18 if (shares + loot) > 0 else 0,
        "token": "vKKN/LOOT",
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "metadata": {
            "member_address": args.get("memberAddress", ""),
            "shares_to_burn": str(shares),
            "loot_to_burn": str(loot),
        },
    }


def decode_trade(args: dict, tx_hash: str, block_number: int,
                 block_timestamp: datetime) -> dict:
    """Decode Trade event into governance_event record."""
    return {
        "chain": KOKONUT_DAO_CHAIN,
        "event_type": "tribute",
        "amount": float(args.get("tributeAmount", 0)) / 1e18 if args.get("tributeAmount") else 0,
        "token": args.get("tributeToken", ""),
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "metadata": {
            "trade_token": args.get("tradeToken", ""),
            "trade_amount": str(args.get("tradeAmount", 0)),
        },
    }


def decode_update_delegate(args: dict, tx_hash: str, block_number: int,
                           block_timestamp: datetime) -> dict:
    """Decode UpdateDelegate event into governance_event record."""
    return {
        "chain": KOKONUT_DAO_CHAIN,
        "event_type": "delegate_changed",
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "metadata": {
            "member_address": args.get("memberAddress", ""),
            "new_delegate_key": args.get("newDelegateKey", ""),
        },
    }


def decode_withdraw(args: dict, tx_hash: str, block_number: int,
                    block_timestamp: datetime) -> dict:
    """Decode Withdraw event into treasury_event record."""
    return {
        "chain": KOKONUT_DAO_CHAIN,
        "flow_direction": "outflow",
        "amount": float(args.get("amount", 0)) / 1e18 if args.get("amount") else 0,
        "token": args.get("tokenAddress", ""),
        "tx_hash": tx_hash,
        "block_number": block_number,
        "event_date": block_timestamp.date(),
        "metadata": {
            "member_address": args.get("memberAddress", ""),
        },
    }


def event_to_action_type(event_name: str) -> str:
    """Map Moloch v2 event name to digital_lego_usage.action_type."""
    mapping = {
        "SubmitProposal": "vote",
        "VoteProposal": "vote",
        "ProcessProposal": "vote",
        "Trade": "swap",
        "Ragequit": "withdraw",
        "Withdraw": "withdraw",
        "UpdateDelegate": "other",
        "CancelProposal": "vote",
    }
    return mapping.get(event_name, "other")


def get_location_from_wallet(db, wallet_id: str) -> Optional[str]:
    """Resolve location_id from wallet_profile.owner_id where owner_type = 'farm'."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT owner_id FROM wallet_profile WHERE id = %s AND owner_type = 'farm' LIMIT 1",
            (wallet_id,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_dlego_usage(db, record: dict) -> Optional[str]:
    """Insert digital lego usage event into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO digital_lego_usage
                (wallet_id, protocol_id, location_id, usage_date,
                 action_type, amount, token, tx_hash, chain,
                 block_number, verified, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                record.get("wallet_id"),
                record.get("protocol_id"),
                record.get("location_id"),
                record["usage_date"],
                record["action_type"],
                record.get("amount"),
                record.get("token"),
                record.get("tx_hash"),
                record["chain"],
                record.get("block_number"),
                record.get("verified", True),
                record.get("notes"),
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_dlego_clickhouse(record: dict) -> None:
    """Insert digital lego usage event into ClickHouse dlego_events table."""
    import requests as req
    ch_url = f"http://{CH_HOST}:{CH_PORT}"

    usage_date = record.get("usage_date", "")
    if hasattr(usage_date, "strftime"):
        ch_timestamp = usage_date.strftime("%Y-%m-%d 00:00:00.000")
    else:
        ch_timestamp = f"{usage_date} 00:00:00.000"

    chain = record.get("chain", "")
    if chain:
        _validate_ch_value(chain, _STR_RE, "chain")

    tx_hash = record.get("tx_hash", "")
    if tx_hash:
        _validate_ch_value(tx_hash, _STR_LOOSE_RE, "tx_hash")

    action_type = record.get("action_type", "")
    if action_type:
        _validate_ch_value(action_type, _STR_RE, "action_type")

    def _safe(val):
        if val is None:
            return "NULL"
        return str(val)

    query = f"""INSERT INTO dlego_events
        (timestamp, wallet_id, protocol_id, location_id, action_type,
         amount, token, chain, tx_hash, metadata)
        VALUES (
            '{ch_timestamp}',
            '{_safe(record.get('wallet_id', ''))}',
            '{record.get('protocol_id', '')}',
            '{_safe(record.get('location_id', ''))}',
            '{action_type}',
            {_safe(record.get('amount'))},
            '{record.get('token', '')}',
            '{chain}',
            '{tx_hash}',
            map()
        )"""

    try:
        resp = req.post(
            ch_url,
            data=query.encode("utf-8"),
            auth=(CH_USER, CH_PASSWORD),
            headers={"Content-Type": "text/plain"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("ClickHouse dlego insert failed: %s", e)


def insert_activity_clickhouse(record: dict) -> None:
    """Insert governance event into ClickHouse wallet_events table."""
    import requests as req
    ch_url = f"http://{CH_HOST}:{CH_PORT}"

    timestamp = record.get("block_timestamp", "")
    if isinstance(timestamp, datetime):
        ch_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    else:
        try:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            ch_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except Exception:
            ch_timestamp = str(timestamp)

    chain = record.get("chain", "")
    if chain:
        _validate_ch_value(chain, _STR_RE, "chain")

    tx_hash = record.get("tx_hash", "")
    if tx_hash:
        _validate_ch_value(tx_hash, _STR_LOOSE_RE, "tx_hash")

    event_type = record.get("event_type", "")
    if event_type:
        _validate_ch_value(event_type, _STR_RE, "event_type")

    query = f"""INSERT INTO wallet_events
        (timestamp, wallet_address, chain, tx_hash, block_number,
         event_type, value, token, status, metadata)
        VALUES (
            '{ch_timestamp}',
            '{record.get("metadata", {}).get("proposer", record.get("metadata", {}).get("member_address", ""))}',
            '{chain}',
            '{tx_hash}',
            {record.get("block_number", 0)},
            '{event_type}',
            {record.get("amount", 0)},
            '{record.get("token", "")}',
            'success',
            map()
        )"""

    try:
        resp = req.post(
            ch_url,
            data=query.encode("utf-8"),
            auth=(CH_USER, CH_PASSWORD),
            headers={"Content-Type": "text/plain"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("ClickHouse insert failed: %s", e)


DECODE_MAP = {
    "SubmitProposal": decode_submit_proposal,
    "VoteProposal": decode_vote_proposal,
    "ProcessProposal": decode_process_proposal,
    "Ragequit": decode_ragequit,
    "Trade": decode_trade,
    "UpdateDelegate": decode_update_delegate,
    "Withdraw": decode_withdraw,
}


def run(from_block: Optional[int] = None, to_block: Optional[int] = None):
    """Main ingestion entry point."""
    db = get_db()
    w3 = get_web3()

    # Determine sync range
    chain = KOKONUT_DAO_CHAIN
    last_synced = get_last_synced_block(chain, "rpc") if from_block is None else None
    start_block = from_block or (last_synced + 1 if last_synced else None)

    if start_block is None:
        # First run — start from a recent block (Gnosis is ~38M blocks as of 2026)
        start_block = max(0, w3.eth.block_number - 10000)
        logger.info("First run — starting from block %d", start_block)

    end_block = to_block or w3.eth.block_number
    if start_block > end_block:
        logger.info("Already synced to block %d", end_block)
        db.close()
        return

    logger.info("Indexing blocks %d → %d (%d blocks)", start_block, end_block, end_block - start_block + 1)

    # Get contract instances
    moloch = get_moloch_contract(w3)
    treasury = get_treasury_contract(w3)

    # Build topic filter for all Moloch events
    topic_list = list(EVENT_TOPICS.keys())

    total_events = 0
    batch_start = start_block

    while batch_start <= end_block:
        batch_end = min(batch_start + BLOCK_BATCH - 1, end_block)
        logger.info("  Scanning blocks %d → %d...", batch_start, batch_end)

        try:
            # Query logs for Moloch contract events
            logs = w3.eth.get_logs({
                "fromBlock": batch_start,
                "toBlock": batch_end,
                "address": Web3.to_checksum_address(KOKONUT_MOLOCH_ADDRESSES["token_manager"]),
                "topics": [topic_list],
            })

            for log_entry in logs:
                topic_hash = log_entry["topics"][0].hex()
                event_name = EVENT_TOPICS.get(topic_hash)

                if not event_name:
                    continue

                # Decode event args
                try:
                    event_abi = moloch.events[event_name]().abi
                    decoded = moloch.events[event_name]().process_log(log_entry)
                    args = dict(decoded["args"])
                except Exception:
                    # Fallback: raw topic decoding
                    args = {}

                tx_hash = log_entry["transactionHash"].hex()
                block_number = log_entry["blockNumber"]
                block_timestamp = fetch_block_timestamp(w3, block_number)

                # Decode based on event type
                decoder = DECODE_MAP.get(event_name)
                if not decoder:
                    continue

                if event_name in ("SubmitProposal", "VoteProposal"):
                    record = decoder(args, tx_hash, block_number, block_timestamp, w3)
                elif event_name == "Withdraw":
                    record = decoder(args, tx_hash, block_number, block_timestamp)
                    # Withdraw goes to treasury_event
                    insert_treasury_event(db, record)
                    insert_activity_clickhouse(record)
                    total_events += 1

                    # Also insert as digital_lego_usage
                    dlego_location = None
                    if record.get("wallet_id"):
                        dlego_location = get_location_from_wallet(db, record["wallet_id"])

                    dlego_record = {
                        "wallet_id": record.get("wallet_id"),
                        "protocol_id": record.get("protocol_id"),
                        "location_id": dlego_location,
                        "usage_date": block_timestamp.date(),
                        "action_type": "withdraw",
                        "amount": record.get("amount"),
                        "token": record.get("token"),
                        "tx_hash": tx_hash,
                        "chain": KOKONUT_DAO_CHAIN,
                        "block_number": block_number,
                        "verified": True,
                    }
                    insert_dlego_usage(db, dlego_record)
                    insert_dlego_clickhouse(dlego_record)
                    continue
                else:
                    record = decoder(args, tx_hash, block_number, block_timestamp)

                # Resolve wallet_id from metadata
                proposer = record.get("metadata", {}).get("proposer", "") or \
                           record.get("metadata", {}).get("member_address", "") or \
                           record.get("metadata", {}).get("voter", "")
                if proposer:
                    wallet_id = get_wallet_id(db, proposer, chain)
                    if wallet_id:
                        record["wallet_id"] = wallet_id

                # Resolve protocol_id (Kokonut Treasury)
                with db.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM protocol WHERE slug = 'kokonut-treasury' LIMIT 1"
                    )
                    row = cur.fetchone()
                    if row:
                        record["protocol_id"] = str(row[0])

                insert_governance_event(db, record)
                insert_activity_clickhouse(record)
                total_events += 1

                # Also insert as digital_lego_usage (protocol interaction)
                dlego_location = None
                if record.get("wallet_id"):
                    dlego_location = get_location_from_wallet(db, record["wallet_id"])

                dlego_record = {
                    "wallet_id": record.get("wallet_id"),
                    "protocol_id": record.get("protocol_id"),
                    "location_id": dlego_location,
                    "usage_date": block_timestamp.date(),
                    "action_type": event_to_action_type(event_name),
                    "amount": record.get("amount"),
                    "token": record.get("token"),
                    "tx_hash": tx_hash,
                    "chain": KOKONUT_DAO_CHAIN,
                    "block_number": block_number,
                    "verified": True,
                }
                insert_dlego_usage(db, dlego_record)
                insert_dlego_clickhouse(dlego_record)

        except Exception as e:
            logger.error("  Block range %d-%d failed: %s", batch_start, batch_end, e)
            update_indexer_status(chain, "rpc", batch_start, "error", str(e))

        batch_start = batch_end + 1

    # Update indexer status
    update_indexer_status(chain, "rpc", end_block, "healthy")
    db.commit()
    db.close()

    logger.info("Done: %d events indexed from blocks %d → %d", total_events, start_block, end_block)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gnosis Chain Moloch DAO event ingestion")
    parser.add_argument("--from-block", type=int, help="Start block number")
    parser.add_argument("--to-block", type=int, help="End block number")
    args = parser.parse_args()
    run(from_block=args.from_block, to_block=args.to_block)
