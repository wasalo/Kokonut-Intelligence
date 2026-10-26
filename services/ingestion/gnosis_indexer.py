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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from web3 import Web3

from ..common.logging import get_logger
from .base import (
    batch_ranges,
    get_db,
    hash_payload,
    now_utc,
    post_clickhouse_rows,
    update_indexer_status,
)
from .clickhouse_outbox import OutboxEnqueueError, enqueue
from .config import (
    GNOSIS_RPC_URL,
    KOKONUT_DAO_CHAIN,
    KOKONUT_MOLOCH_ADDRESSES,
)

logger = get_logger("ingestion.gnosis")

# Validation patterns for ClickHouse SQL interpolation
_STR_RE = re.compile(r'^[a-zA-Z0-9_\-\. ]+$')
_STR_LOOSE_RE = re.compile(r'^[a-zA-Z0-9_\-\.:/ ]+$')

# Block range per request (Gnosis produces ~5s blocks)
BLOCK_BATCH = 500
MAX_BLOCKS_PER_RUN = 10_000
INDEXER_TYPE = "gnosis_moloch"

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


class GnosisEventReorgError(RuntimeError):
    """A previously claimed event identity now points at a different block."""


def _safe_indexer_failure(exc: Exception) -> str:
    """Return an operator-useful error label without provider or query details."""
    if isinstance(exc, GnosisEventReorgError):
        return "Gnosis canonical event identity changed"
    if isinstance(exc, OutboxEnqueueError):
        return "ClickHouse outbox enqueue failed"
    return f"{type(exc).__name__} during Gnosis block processing"


def _normalize_hash(value, name: str) -> str:
    """Normalize a Web3 hash to lowercase 0x-prefixed 32-byte hex."""
    if hasattr(value, "hex"):
        value = value.hex()
    if not isinstance(value, str):
        raise ValueError(f"Gnosis log is missing a valid {name}")
    normalized = value.lower()
    if not normalized.startswith("0x"):
        normalized = f"0x{normalized}"
    if not re.fullmatch(r"0x[0-9a-f]{64}", normalized):
        raise ValueError(f"Gnosis log has an invalid {name}")
    return normalized


def claim_gnosis_event_log(
    db, chain: str, log_entry: dict, event_name: str, *, persistence=None
) -> bool:
    """Claim a log identity or reject a same-identity block-hash mismatch.

    The caller must keep the receipt and all event/outbox projections in the
    same transaction. Returns False for an already-recorded canonical log.
    """
    tx_hash = _normalize_hash(log_entry.get("transactionHash"), "transaction hash")
    block_hash = _normalize_hash(log_entry.get("blockHash"), "block hash")
    try:
        log_index = int(log_entry["logIndex"])
        block_number = int(log_entry["blockNumber"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Gnosis log is missing its block number or log index") from exc
    if log_index < 0 or block_number < 0:
        raise ValueError("Gnosis log block number and log index must be non-negative")

    if persistence is not None:
        return persistence.claim_event(
            db, chain, tx_hash, log_index, block_number, block_hash, event_name
        )

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.gnosis_event_log_receipt (
                chain, transaction_hash, log_index, block_number, block_hash, event_name
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (chain, transaction_hash, log_index) DO NOTHING
            RETURNING block_hash, block_number, event_name
            """,
            (chain, tx_hash, log_index, block_number, block_hash, event_name),
        )
        inserted = cur.fetchone()
        if inserted:
            return True

        cur.execute(
            """
            SELECT block_hash, block_number, event_name
              FROM public.gnosis_event_log_receipt
             WHERE chain = %s AND transaction_hash = %s AND log_index = %s
             FOR KEY SHARE
            """,
            (chain, tx_hash, log_index),
        )
        existing = cur.fetchone()

    expected = (block_hash, block_number, event_name)
    if existing != expected:
        raise GnosisEventReorgError(
            f"Gnosis event identity {tx_hash}:{log_index} changed canonical block data"
        )
    return False


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


def get_web3(rpc_url: Optional[str] = None) -> Web3:
    """Get Web3 instance for Gnosis Chain."""
    return Web3(Web3.HTTPProvider(rpc_url or GNOSIS_RPC_URL))


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


def get_wallet_id(db, address: str, chain: str, *, persistence=None) -> Optional[str]:
    """Look up wallet_id from wallet_profile by address and chain."""
    if persistence is not None:
        return persistence.resolve_wallet(db, address, chain)
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM wallet_profile WHERE LOWER(address) = LOWER(%s) AND chain = %s",
            (address, chain),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_governance_event(db, record: dict, *, persistence=None) -> Optional[str]:
    """Insert governance event into PostgreSQL. Returns record ID."""
    if persistence is not None:
        return persistence.store_governance_event(db, record)
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


def insert_treasury_event(db, record: dict, *, persistence=None) -> Optional[str]:
    """Insert treasury event into PostgreSQL. Returns record ID."""
    if persistence is not None:
        return persistence.store_treasury_event(db, record)
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


def get_location_from_wallet(db, wallet_id: str, *, persistence=None) -> Optional[str]:
    """Resolve location_id from wallet_profile.owner_id where owner_type = 'farm'."""
    if persistence is not None:
        return persistence.resolve_wallet_location(db, wallet_id)
    with db.cursor() as cur:
        cur.execute(
            "SELECT owner_id FROM wallet_profile WHERE id = %s AND owner_type = 'farm' LIMIT 1",
            (wallet_id,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def insert_dlego_usage(db, record: dict, *, persistence=None) -> Optional[str]:
    """Insert digital lego usage event into PostgreSQL. Returns record ID."""
    if persistence is not None:
        return persistence.store_digital_lego_usage(db, record)
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


def insert_dlego_clickhouse(record: dict, conn=None, *, persistence=None) -> None:
    """Queue canonical usage; direct writes are demo-only when conn is absent."""
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

    columns = ["timestamp", "wallet_id", "protocol_id", "location_id", "action_type",
               "amount", "token", "chain", "tx_hash", "metadata"]
    rows = [[ch_timestamp, record.get("wallet_id", ""), record.get("protocol_id", ""),
             record.get("location_id", ""), action_type, record.get("amount"),
             record.get("token", ""), chain, tx_hash, {}]]
    try:
        if conn is not None:
            payload_hash = hash_payload(record)
            enqueue_values = {
                "event_key": f"governance:dlego_events:{record.get('tx_hash')}:{record.get('action_type')}",
                "source_table": "digital_lego_usage",
                "source_id": str(record.get("tx_hash", "")),
                "target_table": "dlego_events",
                "columns": columns,
                "rows": rows,
                "payload_hash": payload_hash,
            }
            if persistence is None:
                enqueue(conn, **enqueue_values)
            else:
                persistence.enqueue_projection(conn, **enqueue_values)
            return
        # No PostgreSQL transaction means this is an explicit demo/maintenance path.
        post_clickhouse_rows(
            "dlego_events",
            columns, rows,
        )
    except Exception as e:
        if conn is not None:
            raise
        logger.warning("ClickHouse dlego insert failed (%s)", type(e).__name__)


def insert_activity_clickhouse(record: dict, conn=None, *, persistence=None) -> None:
    """Queue canonical governance activity; direct writes are demo-only without conn."""
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

    metadata = record.get("metadata", {})
    columns = ["timestamp", "wallet_address", "chain", "tx_hash", "block_number",
               "event_type", "value", "token", "status", "metadata"]
    rows = [[ch_timestamp, metadata.get("proposer", metadata.get("member_address", "")),
             chain, tx_hash, record.get("block_number", 0), event_type,
             record.get("amount", 0), record.get("token", ""), "success", {}]]
    try:
        if conn is not None:
            payload_hash = hash_payload(record)
            enqueue_values = {
                "event_key": f"governance:wallet_events:{tx_hash}:{event_type}",
                "source_table": (
                    "treasury_event"
                    if record.get("flow_direction") == "outflow"
                    else "governance_event"
                ),
                "source_id": tx_hash,
                "target_table": "wallet_events",
                "columns": columns,
                "rows": rows,
                "payload_hash": payload_hash,
            }
            if persistence is None:
                enqueue(conn, **enqueue_values)
            else:
                persistence.enqueue_projection(conn, **enqueue_values)
            return
        # No PostgreSQL transaction means this is an explicit demo/maintenance path.
        post_clickhouse_rows(
            "wallet_events",
            columns, rows,
        )
    except Exception as e:
        if conn is not None:
            raise
        logger.warning("ClickHouse insert failed (%s)", type(e).__name__)


DECODE_MAP = {
    "SubmitProposal": decode_submit_proposal,
    "VoteProposal": decode_vote_proposal,
    "ProcessProposal": decode_process_proposal,
    "Ragequit": decode_ragequit,
    "Trade": decode_trade,
    "UpdateDelegate": decode_update_delegate,
    "Withdraw": decode_withdraw,
}


def _update_indexer_status(
    db,
    chain: str,
    last_synced_block: int,
    status: str,
    error_message: str | None = None,
    metadata: dict | None = None,
    *,
    persistence=None,
) -> None:
    if persistence is None:
        update_indexer_status(
            chain,
            INDEXER_TYPE,
            last_synced_block,
            status,
            error_message,
            metadata=metadata,
            db=db,
        )
    else:
        persistence.update_status(
            db, last_synced_block, status, error_message, metadata or {}
        )


def run(
    from_block: Optional[int] = None,
    to_block: Optional[int] = None,
    *,
    database_factory=None,
    rpc_url: str | None = None,
    persistence=None,
):
    """Main ingestion entry point."""
    if from_block is not None and from_block < 0:
        raise ValueError("--from-block must be non-negative")
    if to_block is not None and to_block < 0:
        raise ValueError("--to-block must be non-negative")
    if from_block is not None and to_block is not None and to_block < from_block:
        raise ValueError("--to-block must be greater than or equal to --from-block")
    if (
        from_block is not None
        and to_block is not None
        and to_block - from_block + 1 > MAX_BLOCKS_PER_RUN
    ):
        raise ValueError(
            f"Gnosis block interval cannot exceed {MAX_BLOCKS_PER_RUN} blocks per run"
        )

    w3 = get_web3() if rpc_url is None else get_web3(rpc_url)
    db = (database_factory or get_db)()
    lock_acquired = False

    chain = KOKONUT_DAO_CHAIN
    try:
        if persistence is not None:
            persistence.acquire_lock(db)
            db.commit()
            lock_acquired = True
            row = persistence.read_cursor(db)
        else:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT last_synced_block, metadata FROM chain_indexer_status "
                    "WHERE chain = %s AND indexer_type = %s",
                    (chain, INDEXER_TYPE),
                )
                row = cur.fetchone()
        last_synced = row[0] if row else None
        cursor_metadata = (row[1] or {}) if row else {}
        cursor_review_required = (
            cursor_metadata.get("cursor_origin") == "legacy_shared_rpc"
            and not cursor_metadata.get("cursor_reviewed", False)
        )

        if cursor_review_required and from_block is None:
            raise RuntimeError(
                "Gnosis Moloch cursor was inherited from shared wallet RPC state; "
                "review the canonical checkpoint and pass --from-block explicitly"
            )

        try:
            latest_block = to_block if to_block is not None else w3.eth.block_number
        except Exception as exc:
            raise RuntimeError(
                f"Gnosis latest block lookup failed ({type(exc).__name__})"
            ) from None
        if from_block is not None:
            start_block = from_block
        elif last_synced is not None:
            start_block = last_synced + 1
        else:
            # First run — include at most the latest MAX_BLOCKS_PER_RUN blocks.
            start_block = max(0, latest_block - MAX_BLOCKS_PER_RUN + 1)
            logger.info("First run — starting from block %d", start_block)

        # Backlogs resume at the next checkpoint on later invocations. The
        # persisted cursor advances only through committed ranges, so this cap
        # bounds RPC/DB work without discarding any blocks.
        end_block = min(latest_block, start_block + MAX_BLOCKS_PER_RUN - 1)
        last_committed_block = (
            start_block - 1
            if from_block is not None
            else last_synced if last_synced is not None else start_block - 1
        )
        review_metadata = {"cursor_reviewed": True} if cursor_review_required else None
        if start_block > end_block:
            _update_indexer_status(
                db,
                chain,
                last_committed_block,
                "healthy",
                metadata=review_metadata,
                persistence=persistence,
            )
            db.commit()
            logger.info("Already synced to block %d", end_block)
            return

        logger.info(
            "Indexing blocks %d → %d (%d blocks)",
            start_block,
            end_block,
            end_block - start_block + 1,
        )

        moloch = get_moloch_contract(w3)
        get_treasury_contract(w3)  # Validate that the configured treasury ABI/address is usable.
        topic_list = list(EVENT_TOPICS.keys())
        total_events = 0

        for batch_start, batch_end in batch_ranges(start_block, end_block, BLOCK_BATCH):
            logger.info("  Scanning blocks %d → %d...", batch_start, batch_end)

            try:
                logs = w3.eth.get_logs({
                    "fromBlock": batch_start,
                    "toBlock": batch_end,
                    "address": Web3.to_checksum_address(
                        KOKONUT_MOLOCH_ADDRESSES["token_manager"]
                    ),
                    "topics": [topic_list],
                })

                for log_entry in logs:
                    topic_hash = log_entry["topics"][0].hex().lower()
                    event_name = EVENT_TOPICS.get(topic_hash)
                    if not event_name:
                        continue
                    decoder = DECODE_MAP.get(event_name)
                    if not decoder:
                        continue

                    if not claim_gnosis_event_log(
                        db, chain, log_entry, event_name, persistence=persistence
                    ):
                        continue

                    tx_hash = _normalize_hash(
                        log_entry.get("transactionHash"), "transaction hash"
                    )
                    block_number = int(log_entry["blockNumber"])

                    try:
                        decoded = moloch.events[event_name]().process_log(log_entry)
                        args = dict(decoded["args"])
                    except Exception:
                        # Fallback: raw topic decoding.
                        args = {}

                    block_timestamp = fetch_block_timestamp(w3, block_number)

                    if event_name in ("SubmitProposal", "VoteProposal"):
                        record = decoder(
                            args, tx_hash, block_number, block_timestamp, w3
                        )
                    elif event_name == "Withdraw":
                        record = decoder(args, tx_hash, block_number, block_timestamp)
                        insert_treasury_event(db, record, persistence=persistence)
                        insert_activity_clickhouse(record, db, persistence=persistence)
                        total_events += 1

                        dlego_location = None
                        if record.get("wallet_id"):
                            dlego_location = get_location_from_wallet(
                                db, record["wallet_id"], persistence=persistence
                            )
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
                        insert_dlego_usage(db, dlego_record, persistence=persistence)
                        insert_dlego_clickhouse(dlego_record, db, persistence=persistence)
                        continue
                    else:
                        record = decoder(args, tx_hash, block_number, block_timestamp)

                    proposer = (
                        record.get("metadata", {}).get("proposer", "")
                        or record.get("metadata", {}).get("member_address", "")
                        or record.get("metadata", {}).get("voter", "")
                    )
                    if proposer:
                        wallet_id = get_wallet_id(
                            db, proposer, chain, persistence=persistence
                        )
                        if wallet_id:
                            record["wallet_id"] = wallet_id

                    if persistence is None:
                        with db.cursor() as cur:
                            cur.execute(
                                "SELECT id FROM protocol "
                                "WHERE slug = 'kokonut-treasury' LIMIT 1"
                            )
                            row = cur.fetchone()
                            if row:
                                record["protocol_id"] = str(row[0])
                    else:
                        protocol_id = persistence.resolve_protocol(db)
                        if protocol_id:
                            record["protocol_id"] = protocol_id

                    insert_governance_event(db, record, persistence=persistence)
                    insert_activity_clickhouse(record, db, persistence=persistence)
                    total_events += 1

                    dlego_location = None
                    if record.get("wallet_id"):
                        dlego_location = get_location_from_wallet(
                            db, record["wallet_id"], persistence=persistence
                        )
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
                    insert_dlego_usage(db, dlego_record, persistence=persistence)
                    insert_dlego_clickhouse(dlego_record, db, persistence=persistence)

                checkpoint = max(last_committed_block, batch_end)
                _update_indexer_status(
                    db,
                    chain,
                    checkpoint,
                    "syncing",
                    metadata=review_metadata,
                    persistence=persistence,
                )
                db.commit()
                last_committed_block = checkpoint
            except Exception as exc:
                db.rollback()
                safe_error = _safe_indexer_failure(exc)
                try:
                    _update_indexer_status(
                        db,
                        chain,
                        last_committed_block,
                        "error",
                        safe_error,
                        persistence=persistence,
                    )
                    db.commit()
                except Exception as status_exc:
                    db.rollback()
                    logger.error(
                        "Could not persist Gnosis indexer error status (%s)",
                        type(status_exc).__name__,
                    )
                if isinstance(exc, GnosisEventReorgError):
                    raise GnosisEventReorgError(safe_error) from None
                if isinstance(exc, OutboxEnqueueError):
                    raise OutboxEnqueueError(safe_error) from None
                raise RuntimeError(
                    f"Gnosis block range {batch_start}-{batch_end} failed ({safe_error})"
                ) from None

        final_checkpoint = max(last_committed_block, end_block)
        _update_indexer_status(
            db,
            chain,
            final_checkpoint,
            "healthy",
            metadata=review_metadata,
            persistence=persistence,
        )
        db.commit()
    finally:
        if persistence is not None and lock_acquired:
            try:
                persistence.release_lock(db)
                db.commit()
            except Exception as lock_error:
                db.rollback()
                logger.warning(
                    "Could not release Gnosis indexer lock (%s)",
                    type(lock_error).__name__,
                )
        db.close()

    logger.info(
        "Done: %d events indexed from blocks %d → %d",
        total_events,
        start_block,
        end_block,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone and unified CLI parser."""
    parser = argparse.ArgumentParser(
        prog="gnosis_indexer.py",
        description="Gnosis Chain Moloch DAO event ingestion",
    )
    parser.add_argument("--from-block", type=int, help="Start block number")
    parser.add_argument("--to-block", type=int, help="End block number")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run Gnosis indexing for the selected block interval."""
    args = build_parser().parse_args(argv)
    run(from_block=args.from_block, to_block=args.to_block)


if __name__ == "__main__":
    main()
