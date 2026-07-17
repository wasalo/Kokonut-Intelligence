"""Self-hosted KGP event indexer for Gnosis and Chiado."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from web3 import Web3

from ..common.logging import get_logger
from ..ingestion.base import get_db
from ..ingestion.config import GNOSIS_RPC_URL
from .kgp import insert_chain_event

logger = get_logger("guilds.kgp_indexer")
CONFIRMATIONS = int(os.environ.get("KGP_CONFIRMATIONS", "12"))
BLOCK_BATCH = int(os.environ.get("KGP_BLOCK_BATCH", "500"))

EVENT_SIGNATURES = {
    "KGP_Awarded": "KGP_Awarded(bytes32,bytes32,address,uint256,uint256,uint256,bytes32,bytes32,bytes32)",
    "KGPClaimed": "KGPClaimed(bytes32,address,uint256)",
    "KGPReversed": "KGPReversed(bytes32,bytes32,bytes32,address,uint256,uint256,bytes32,bytes32,bytes32)",
}
EVENT_TOPICS = {"0x" + Web3.keccak(text=value).hex().removeprefix("0x"): name for name, value in EVENT_SIGNATURES.items()}


def _hex(value: Any) -> str:
    if isinstance(value, str):
        return value if value.startswith("0x") else "0x" + value
    if isinstance(value, bytes):
        return "0x" + value.hex()
    return Web3.to_hex(value)


def _topic_address(topic: Any) -> str:
    return Web3.to_checksum_address("0x" + _hex(topic)[-40:])


def decode_log(log: dict[str, Any]) -> dict[str, Any]:
    """Decode the indexed fields and preserve the raw payload for audit."""
    topics = log["topics"]
    signature = _hex(topics[0]).lower()
    event_name = EVENT_TOPICS.get(signature)
    if event_name is None:
        raise ValueError(f"Unsupported KGP event topic: {signature}")

    decoded: dict[str, Any] = {
        "event_name": event_name,
        "event_signature": signature,
        "award_id": _hex(topics[1]) if event_name != "KGPReversed" else None,
        "raw_topics": [_hex(topic) for topic in topics],
        "raw_data": _hex(log["data"]),
    }
    if event_name == "KGP_Awarded":
        decoded.update({"guild_id": _hex(topics[2]), "contributor_wallet": _topic_address(topics[3])})
    elif event_name == "KGPClaimed":
        decoded["contributor_wallet"] = _topic_address(topics[2])
    else:
        decoded.update(
            {
                "reversal_id": _hex(topics[1]),
                "award_id": _hex(topics[2]),
                "guild_id": _hex(topics[3]),
            }
        )
    return decoded


def _mark_processed(cursor, deployment_id: str, transaction_hash: str, log_index: int) -> None:
    cursor.execute(
        """
        UPDATE kgp_chain_event
        SET processing_status = 'processed', processed_at = NOW(), processing_error = NULL
        WHERE deployment_id = %s AND transaction_hash = %s AND log_index = %s
        """,
        (deployment_id, transaction_hash, log_index),
    )


def _project_event(cursor, deployment_id: str, log: dict[str, Any], decoded: dict[str, Any]) -> bool:
    tx_hash = _hex(log["transactionHash"])
    block_number = int(log["blockNumber"])
    log_index = int(log["logIndex"])
    if decoded["event_name"] == "KGP_Awarded":
        cursor.execute(
            """
            UPDATE guild_reputation_event
            SET settlement_status = 'reconciled', contract_deployment_id = %s,
                transaction_hash = %s, block_number = %s, log_index = %s,
                settled_at = COALESCE(settled_at, NOW()), updated_at = NOW()
            WHERE award_id = %s
            """,
            (deployment_id, tx_hash, block_number, log_index, decoded["award_id"]),
        )
    elif decoded["event_name"] == "KGPClaimed":
        cursor.execute(
            """
            UPDATE kgp_claim
            SET claim_status = 'claimed', transaction_hash = %s,
                block_number = %s, claimed_at = COALESCE(claimed_at, NOW()), updated_at = NOW()
            WHERE award_id = %s
            """,
            (tx_hash, block_number, decoded["award_id"]),
        )
    else:
        cursor.execute(
            """
            UPDATE guild_reputation_event
            SET settlement_status = 'reconciled', contract_deployment_id = %s,
                transaction_hash = %s, block_number = %s, log_index = %s,
                settled_at = COALESCE(settled_at, NOW()), updated_at = NOW()
            WHERE reversal_id = %s
            """,
            (deployment_id, tx_hash, block_number, log_index, decoded["reversal_id"]),
        )
    return cursor.rowcount == 1


class KGPIndexer:
    """Index confirmed KGP events and reconcile them to canonical ledger rows."""

    def __init__(self, w3: Web3, db, deployment_id: str, contract_address: str, chain_id: int):
        self.w3 = w3
        self.db = db
        self.deployment_id = deployment_id
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.chain_id = chain_id

    def scan_once(self) -> int:
        with self.db.cursor() as cursor:
            cursor.execute(
                "SELECT next_block FROM kgp_indexer_cursor WHERE deployment_id = %s FOR UPDATE",
                (self.deployment_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("KGP indexer cursor is not initialized")

            latest = self.w3.eth.block_number
            confirmed = max(0, latest - CONFIRMATIONS)
            start = int(row[0])
            if start > confirmed:
                return 0
            end = min(start + BLOCK_BATCH - 1, confirmed)
            logs = self.w3.eth.get_logs(
                {
                    "address": self.contract_address,
                    "fromBlock": start,
                    "toBlock": end,
                    "topics": [list(EVENT_TOPICS)],
                }
            )
            processed = 0
            for raw_log in logs:
                log = dict(raw_log)
                decoded = decode_log(log)
                event = {
                    "deployment_id": self.deployment_id,
                    "chain_id": self.chain_id,
                    "block_number": int(log["blockNumber"]),
                    "block_hash": _hex(log["blockHash"]),
                    "transaction_hash": _hex(log["transactionHash"]),
                    "log_index": int(log["logIndex"]),
                    "contract_address": self.contract_address,
                    "event_signature": decoded["event_signature"],
                    "event_name": decoded["event_name"],
                    "payload": decoded,
                }
                if insert_chain_event(cursor, event):
                    projected = _project_event(cursor, self.deployment_id, log, decoded)
                    if projected:
                        _mark_processed(cursor, self.deployment_id, event["transaction_hash"], event["log_index"])
                    else:
                        cursor.execute(
                            """
                            UPDATE kgp_chain_event
                            SET processing_status = 'dead_letter',
                                processing_error = 'No canonical PostgreSQL ledger record matched the chain event'
                            WHERE deployment_id = %s AND transaction_hash = %s AND log_index = %s
                            """,
                            (self.deployment_id, event["transaction_hash"], event["log_index"]),
                        )
                    processed += 1

            block_hash = _hex(self.w3.eth.get_block(end).hash)
            cursor.execute(
                """
                UPDATE kgp_indexer_cursor
                SET next_block = %s, confirmed_block = %s, last_block_hash = %s,
                    status = 'active', retry_count = 0, last_error = NULL, updated_at = NOW()
                WHERE deployment_id = %s
                """,
                (end + 1, end, block_hash, self.deployment_id),
            )
            self.db.commit()
            return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Kokonut Guild Points events")
    parser.add_argument("--once", action="store_true", help="scan one confirmed block range")
    parser.add_argument("--rpc-url", default=GNOSIS_RPC_URL)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--contract-address", required=True)
    parser.add_argument("--chain-id", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        parser.error("--once is required until the durable worker loop is enabled")

    db = get_db()
    try:
        count = KGPIndexer(
            Web3(Web3.HTTPProvider(args.rpc_url)),
            db,
            args.deployment_id,
            args.contract_address,
            args.chain_id,
        ).scan_once()
        print(json.dumps({"processed": count}))
    finally:
        db.close()


if __name__ == "__main__":
    main()
