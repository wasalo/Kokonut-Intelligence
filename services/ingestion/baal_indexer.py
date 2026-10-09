"""Indexer for the Kokonut DAO (Moloch v3 / Baal) on Gnosis Chain.

Decodes Baal contract events into the existing ``governance_event`` /
``treasury_event`` tables (which already accept arbitrary ``event_type``
strings). Reuses the shared ingestion helpers from ``services/ingestion/base.py``
and the read client from ``services/governance/baal.py``.

Run:
    python3 -m services.ingestion.baal_indexer [--from-block N] [--to-block N]

Note: the Kokonut Baal clone (KOKONUT_BAAL_ADDRESSES["baal"]) emits proposal
events from block ~29_810_566 (proposal 1). A full history backfill must start
well before the clone's first *recent* activity (block ~41_112_294, proposal 15);
use --from-block 29000000 to capture proposals 1-14. Idempotent: re-running
over the same range is safe (unique index on governance_event).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from web3 import Web3

from ..common.logging import get_logger
from ..governance.baal import BaalReadClient
from .base import (
    batch_ranges,
    get_db,
    get_last_synced_block,
    update_indexer_status,
)
from .config import GNOSIS_RPC_URL, KOKONUT_DAO_CHAIN

logger = get_logger("ingestion.baal")

INDEXER_TYPE = "baal"
BLOCK_BATCH = 200_000

# Baal event signature -> decoder key
EVENT_DECODERS = {
    "SubmitProposal": "proposal_created",
    "SponsorProposal": "proposal_sponsored",
    "SubmitVote": "vote_cast",
    "ProcessProposal": "proposal_processed",
    "CancelProposal": "proposal_cancelled",
    "Ragequit": "ragequit",
    "GovernanceConfigSet": "governance_config_set",
    "ShamanSet": "shaman_set",
}

VOTE_CHOICES = {True: "yes", False: "no"}


def _get_protocol_id(db) -> str | None:
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM protocol WHERE slug = %s", ("kokonut-treasury",)
        )
        row = cur.fetchone()
    return str(row[0]) if row else None


def _wallet_id(db, address: str) -> str | None:
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM wallet_profile WHERE LOWER(address) = LOWER(%s) AND chain = %s",
            (address, KOKONUT_DAO_CHAIN),
        )
        row = cur.fetchone()
    return str(row[0]) if row else None


def insert_governance_event(db, record: dict) -> None:
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO governance_event
                (wallet_id, protocol_id, chain, event_type, proposal_id,
                 proposal_title, vote_choice, amount, token, tx_hash,
                 block_number, block_timestamp, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chain, event_type, tx_hash) DO NOTHING
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


def _decode_event(event, w3: Web3, protocol_id: str | None) -> dict | None:
    name = event["event"]
    args = dict(event["args"])
    tx_hash = event["transactionHash"].hex()
    block_number = event["blockNumber"]
    block_timestamp = datetime.fromtimestamp(
        w3.eth.get_block(block_number)["timestamp"], tz=timezone.utc
    )
    wallet = None
    if "member" in args:
        wallet = _checksum(args["member"])
    elif "delegator" in args:
        wallet = _checksum(args["delegator"])
    record = {
        "chain": KOKONUT_DAO_CHAIN,
        "event_type": EVENT_DECODERS.get(name, name.lower()),
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "protocol_id": protocol_id,
        "metadata": {k: str(v) for k, v in args.items()},
    }
    if wallet:
        record["wallet_id"] = wallet  # resolved lazily in caller
    if name == "SubmitProposal":
        record["proposal_id"] = str(args.get("proposal", ""))
        # `details` is a JSON string carrying title/description/contentURI.
        details_raw = args.get("details") or ""
        try:
            details_json = json.loads(details_raw) if isinstance(details_raw, str) else {}
        except (ValueError, TypeError):
            details_json = {}
        record["proposal_title"] = (details_json.get("title") or details_raw)[:500]
        record["metadata"]["title"] = details_json.get("title")
        record["metadata"]["description"] = details_json.get("description")
        record["metadata"]["content_uri"] = details_json.get("contentURI")
        record["metadata"]["proposal_type"] = details_json.get("proposalType")
        record["metadata"]["voting_period"] = str(args.get("votingPeriod"))
        record["metadata"]["self_sponsor"] = str(args.get("selfSponsor"))
        record["metadata"]["timestamp"] = str(args.get("timestamp"))
    elif name == "SponsorProposal":
        record["proposal_id"] = str(args.get("proposal", ""))
        record["metadata"]["voting_start"] = str(args.get("votingStart"))
    elif name == "SubmitVote":
        record["proposal_id"] = str(args.get("proposal", ""))
        record["vote_choice"] = VOTE_CHOICES.get(bool(args.get("approved")), "unknown")
        record["metadata"]["balance"] = str(args.get("balance"))
    elif name == "ProcessProposal":
        record["proposal_id"] = str(args.get("proposal", ""))
        record["metadata"]["passed"] = str(args.get("passed"))
        record["metadata"]["action_failed"] = str(args.get("actionFailed"))
    elif name == "CancelProposal":
        record["proposal_id"] = str(args.get("proposal", ""))
    elif name == "Ragequit":
        record["proposal_id"] = None
        record["metadata"]["shares_to_burn"] = str(args.get("sharesToBurn"))
        record["metadata"]["loot_to_burn"] = str(args.get("lootToBurn"))
    elif name == "GovernanceConfigSet":
        record["metadata"] = {
            "voting": str(args.get("voting")),
            "grace": str(args.get("grace")),
            "new_offering": str(args.get("newOffering")),
            "quorum": str(args.get("quorum")),
            "sponsor": str(args.get("sponsor")),
            "min_retention": str(args.get("minRetention")),
        }
    elif name == "ShamanSet":
        record["metadata"] = {
            "shaman": _checksum(args.get("shaman")),
            "permission": str(args.get("permission")),
        }
    return record


def _checksum(addr: str) -> str:
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        return addr


def run(from_block: int | None = None, to_block: int | None = None) -> int:
    w3 = Web3(Web3.HTTPProvider(GNOSIS_RPC_URL))
    client = BaalReadClient(w3=w3)
    baal = client._baal

    start = from_block or (get_last_synced_block(KOKONUT_DAO_CHAIN, INDEXER_TYPE) or 0)
    end = to_block or w3.eth.block_number
    if start > end:
        logger.info("Baal indexer: start %s >= end %s, nothing to do", start, end)
        return 0

    db = get_db()
    protocol_id = _get_protocol_id(db)
    processed = 0
    try:
        for cur_block, batch_end in batch_ranges(start, end, BLOCK_BATCH):
            for event_name in EVENT_DECODERS:
                try:
                    logs = baal.events[event_name]().get_logs(
                        from_block=cur_block, to_block=batch_end
                    )
                except Exception as exc:  # pragma: no cover - network dependent
                    logger.warning("Baal event %s fetch failed: %s", event_name, exc)
                    continue
                for ev in logs:
                    record = _decode_event(ev, w3, protocol_id)
                    if not record:
                        continue
                    wallet = record.pop("wallet_id", None)
                    if wallet:
                        record["wallet_id"] = _wallet_id(db, wallet)
                    insert_governance_event(db, record)
                    processed += 1
            db.commit()
            update_indexer_status(
                KOKONUT_DAO_CHAIN, INDEXER_TYPE, batch_end, "syncing"
            )
            logger.info("Baal indexed through block %s (%s events)", batch_end, processed)
        update_indexer_status(KOKONUT_DAO_CHAIN, INDEXER_TYPE, end, "healthy")
    except Exception as exc:
        db.rollback()
        update_indexer_status(KOKONUT_DAO_CHAIN, INDEXER_TYPE, None, "failed", str(exc))
        logger.error("Baal indexer failed: %s", exc)
        raise
    finally:
        db.close()
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Kokonut Baal (Moloch v3) DAO events")
    parser.add_argument("--from-block", type=int, default=None)
    parser.add_argument("--to-block", type=int, default=None)
    args = parser.parse_args()
    count = run(from_block=args.from_block, to_block=args.to_block)
    logger.info("Baal indexer complete: %s events ingested", count)


if __name__ == "__main__":
    main()
