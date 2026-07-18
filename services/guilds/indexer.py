"""Self-hosted KGP event indexer for Gnosis and Chiado."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from eth_abi import decode as abi_decode
from web3 import Web3

from ..common.logging import get_logger
from ..ingestion.base import get_db
from ..ingestion.config import GNOSIS_RPC_URL
from .kgp import insert_chain_event
from .projections import project_protocol_event

logger = get_logger("guilds.kgp_indexer")
CONFIRMATIONS = int(os.environ.get("KGP_CONFIRMATIONS", "12"))
BLOCK_BATCH = int(os.environ.get("KGP_BLOCK_BATCH", "500"))

EVENT_SIGNATURES = {
    "KGP_Awarded": "KGP_Awarded(bytes32,bytes32,address,uint256,uint256,uint256,bytes32,bytes32,bytes32)",
    "KGPClaimed": "KGPClaimed(bytes32,address,uint256)",
    "KGPReversed": "KGPReversed(bytes32,bytes32,bytes32,address,uint256,uint256,bytes32,bytes32,bytes32)",
    "GuildCreated": "GuildCreated(bytes32,bytes32,string,address)",
    "GuildMetadataUpdated": "GuildMetadataUpdated(bytes32,string)",
    "GuildStewardUpdated": "GuildStewardUpdated(bytes32,address)",
    "GuildStatusUpdated": "GuildStatusUpdated(bytes32,uint8)",
    "DomainCreated": "DomainCreated(uint256,bytes32,uint256,string,address)",
    "DomainMetadataUpdated": "DomainMetadataUpdated(uint256,string)",
    "DomainStatusUpdated": "DomainStatusUpdated(uint256,uint8)",
    "TaskCreated": "TaskCreated(uint256,bytes32,uint256,bytes32)",
    "TaskAssigned": "TaskAssigned(uint256,address)",
    "TaskEvidenceSubmitted": "TaskEvidenceSubmitted(uint256,address,bytes32)",
    "TaskStatusUpdated": "TaskStatusUpdated(uint256,uint8,bytes32)",
    "EvidenceReviewed": "EvidenceReviewed(bytes32,uint256,address,uint8,bytes32,bytes32)",
    "EvidenceDisputed": "EvidenceDisputed(bytes32,address,bytes32)",
    "EvidenceDisputeResolved": "EvidenceDisputeResolved(bytes32,bool,bytes32)",
    "EvidenceRevoked": "EvidenceRevoked(bytes32,bytes32)",
    "TargetPermissionUpdated": "TargetPermissionUpdated(address,bool)",
    "MotionCreated": "MotionCreated(uint256,bytes32,address,address,bytes32,uint64)",
    "MotionObjected": "MotionObjected(uint256,address,bytes32)",
    "MotionFinalized": "MotionFinalized(uint256,uint8)",
    "MotionExecuted": "MotionExecuted(uint256,bytes)",
}
EVENT_TOPICS = {"0x" + Web3.keccak(text=value).hex().removeprefix("0x"): name for name, value in EVENT_SIGNATURES.items()}
KGP_EVENT_NAMES = {"KGP_Awarded", "KGPClaimed", "KGPReversed"}
EVENT_DATA_TYPES = {
    "KGP_Awarded": (["uint256", "uint256", "uint256", "bytes32", "bytes32", "bytes32"], ["domain_id", "amount", "epoch", "evidence_hash", "ledger_record_hash", "calculation_version"]),
    "KGPClaimed": (["uint256"], ["nonce"]),
    "KGPReversed": (["address", "uint256", "uint256", "bytes32", "bytes32", "bytes32"], ["contributor_wallet", "domain_id", "amount", "reason_hash", "ledger_record_hash", "calculation_version"]),
    "GuildCreated": (["string"], ["name"]),
    "GuildMetadataUpdated": (["string"], ["metadata_uri"]),
    "GuildStewardUpdated": ([], []),
    "GuildStatusUpdated": (["uint8"], ["status"]),
    "DomainCreated": (["string", "address"], ["name", "creator"]),
    "DomainMetadataUpdated": (["string"], ["metadata_uri"]),
    "DomainStatusUpdated": (["uint8"], ["status"]),
    "TaskCreated": (["bytes32"], ["task_key"]),
    "TaskAssigned": ([], []),
    "TaskEvidenceSubmitted": (["bytes32"], ["evidence_hash"]),
    "TaskStatusUpdated": (["uint8", "bytes32"], ["status", "reference_hash"]),
    "EvidenceReviewed": (["uint8", "bytes32", "bytes32"], ["decision", "evidence_hash", "notes_hash"]),
    "EvidenceDisputed": (["bytes32"], ["reason_hash"]),
    "EvidenceDisputeResolved": (["bool", "bytes32"], ["accepted", "resolution_hash"]),
    "EvidenceRevoked": (["bytes32"], ["reason_hash"]),
    "TargetPermissionUpdated": (["bool"], ["allowed"]),
    "MotionCreated": (["address", "bytes32", "uint64"], ["target", "data_hash", "objection_deadline"]),
    "MotionObjected": (["bytes32"], ["reason_hash"]),
    "MotionFinalized": (["uint8"], ["status"]),
    "MotionExecuted": (["bytes"], ["return_data"]),
}


def _hex(value: Any) -> str:
    if isinstance(value, str):
        return value if value.startswith("0x") else "0x" + value
    if isinstance(value, bytes):
        return "0x" + value.hex()
    return Web3.to_hex(value)


def _topic_address(topic: Any) -> str:
    return Web3.to_checksum_address("0x" + _hex(topic)[-40:])


def _decode_data(event_name: str, data: Any) -> dict[str, Any]:
    types, names = EVENT_DATA_TYPES.get(event_name, ([], []))
    if not types:
        return {}
    values = abi_decode(types, bytes.fromhex(_hex(data)[2:]))
    decoded = {}
    for name, value in zip(names, values):
        if isinstance(value, bytes):
            decoded[name] = _hex(value)
        elif isinstance(value, str) and name in {"contributor_wallet", "creator", "target"}:
            decoded[name] = Web3.to_checksum_address(value)
        else:
            decoded[name] = value
    return decoded


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
    decoded.update(_decode_data(event_name, log["data"]))
    if event_name == "KGP_Awarded":
        decoded.update({"guild_id": _hex(topics[2]), "contributor_wallet": _topic_address(topics[3])})
    elif event_name == "KGPClaimed":
        decoded["contributor_wallet"] = _topic_address(topics[2])
    elif event_name == "KGPReversed":
        decoded.update(
            {
                "reversal_id": _hex(topics[1]),
                "award_id": _hex(topics[2]),
                "guild_id": _hex(topics[3]),
            }
        )
    elif event_name == "GuildCreated":
        decoded.update({"guild_id": _hex(topics[1]), "guild_key": _hex(topics[2]), "steward": _topic_address(topics[3]), "guild_key_name": ""})
    elif event_name in {"GuildMetadataUpdated", "GuildStewardUpdated", "GuildStatusUpdated"}:
        decoded["guild_id"] = _hex(topics[1])
        if event_name == "GuildStewardUpdated":
            decoded["steward"] = _topic_address(topics[2])
    elif event_name == "DomainCreated":
        decoded.update({"domain_id": int.from_bytes(bytes.fromhex(_hex(topics[1])[2:]), "big"), "guild_id": _hex(topics[2]), "parent_domain_id": int.from_bytes(bytes.fromhex(_hex(topics[3])[2:]), "big")})
    elif event_name in {"DomainMetadataUpdated", "DomainStatusUpdated"}:
        decoded["domain_id"] = int.from_bytes(bytes.fromhex(_hex(topics[1])[2:]), "big")
    elif event_name in {"TaskCreated", "TaskAssigned", "TaskEvidenceSubmitted", "TaskStatusUpdated"}:
        decoded["task_id"] = int.from_bytes(bytes.fromhex(_hex(topics[1])[2:]), "big")
        if event_name == "TaskCreated":
            decoded.update({"guild_id": _hex(topics[2]), "domain_id": int.from_bytes(bytes.fromhex(_hex(topics[3])[2:]), "big")})
        elif event_name in {"TaskAssigned", "TaskEvidenceSubmitted"}:
            decoded["contributor_wallet"] = _topic_address(topics[2])
    elif event_name == "EvidenceReviewed":
        decoded.update({"review_id": _hex(topics[1]), "task_id": int.from_bytes(bytes.fromhex(_hex(topics[2])[2:]), "big"), "reviewer_wallet": _topic_address(topics[3])})
    elif event_name in {"EvidenceDisputed", "EvidenceDisputeResolved", "EvidenceRevoked"}:
        decoded["review_id"] = _hex(topics[1])
        if event_name == "EvidenceDisputed":
            decoded["disputer"] = _topic_address(topics[2])
    elif event_name in {"TargetPermissionUpdated"}:
        decoded["target"] = _topic_address(topics[1])
    elif event_name in {"MotionCreated", "MotionObjected", "MotionFinalized", "MotionExecuted"}:
        decoded["motion_id"] = int.from_bytes(bytes.fromhex(_hex(topics[1])[2:]), "big")
        if event_name == "MotionCreated":
            decoded.update({"guild_id": _hex(topics[2]), "proposer": _topic_address(topics[3])})
        elif event_name == "MotionObjected":
            decoded["objector"] = _topic_address(topics[2])
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
              AND LOWER(contributor_wallet) = LOWER(%s)
              AND domain_id = %s AND amount = %s AND epoch = %s
              AND evidence_hash = %s AND ledger_record_hash = %s
              AND calculation_version = %s
            """,
            (
                deployment_id, tx_hash, block_number, log_index, decoded["award_id"],
                decoded["contributor_wallet"], decoded["domain_id"], decoded["amount"], decoded["epoch"],
                decoded["evidence_hash"], decoded["ledger_record_hash"], decoded["calculation_version"],
            ),
        )
    elif decoded["event_name"] == "KGPClaimed":
        cursor.execute(
            """
            UPDATE kgp_claim
            SET claim_status = 'claimed', transaction_hash = %s,
                block_number = %s, claimed_at = COALESCE(claimed_at, NOW()), updated_at = NOW()
            WHERE award_id = %s AND LOWER(contributor_wallet) = LOWER(%s) AND nonce = %s
            """,
            (tx_hash, block_number, decoded["award_id"], decoded["contributor_wallet"], decoded["nonce"]),
        )
    else:
        cursor.execute(
            """
            UPDATE guild_reputation_event
            SET settlement_status = 'reconciled', contract_deployment_id = %s,
                transaction_hash = %s, block_number = %s, log_index = %s,
                settled_at = COALESCE(settled_at, NOW()), updated_at = NOW()
            WHERE reversal_id = %s
              AND LOWER(contributor_wallet) = LOWER(%s)
              AND domain_id = %s AND amount = %s
              AND reason_hash = %s AND ledger_record_hash = %s
              AND calculation_version = %s
            """,
            (
                deployment_id, tx_hash, block_number, log_index, decoded["reversal_id"],
                decoded["contributor_wallet"], decoded["domain_id"], decoded["amount"],
                decoded["reason_hash"], decoded["ledger_record_hash"], decoded["calculation_version"],
            ),
        )
    return cursor.rowcount == 1


class KGPIndexer:
    """Index confirmed Guild protocol events and reconcile canonical projections."""

    def __init__(self, w3: Web3, db, deployment_id: str, contract_addresses: dict[str, str] | str, chain_id: int):
        self.w3 = w3
        self.db = db
        self.deployment_id = deployment_id
        if isinstance(contract_addresses, str):
            contract_addresses = {"kgp": contract_addresses}
        self.contract_addresses = {
            name: Web3.to_checksum_address(address) for name, address in contract_addresses.items()
        }
        self.chain_id = chain_id

    def scan_once(self) -> int:
        with self.db.cursor() as cursor:
            cursor.execute(
                "SELECT next_block, last_block_number, last_block_hash FROM kgp_indexer_cursor WHERE deployment_id = %s FOR UPDATE",
                (self.deployment_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("KGP indexer cursor is not initialized")

            if self._reorg_detected(row):
                self._rewind_after_reorg(cursor, int(row[1]))
                self.db.commit()
                return 0

            latest = self.w3.eth.block_number
            confirmed = max(0, latest - CONFIRMATIONS)
            start = int(row[0])
            if start > confirmed:
                return 0
            end = min(start + BLOCK_BATCH - 1, confirmed)
            logs = []
            for contract_address in self.contract_addresses.values():
                logs.extend(self.w3.eth.get_logs({
                    "address": contract_address,
                    "fromBlock": start,
                    "toBlock": end,
                    "topics": [list(EVENT_TOPICS)],
                }))
            logs.sort(key=lambda item: (int(item["blockNumber"]), int(item["transactionIndex"]), int(item["logIndex"])))
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
                    "contract_address": Web3.to_checksum_address(log["address"]),
                    "event_signature": decoded["event_signature"],
                    "event_name": decoded["event_name"],
                    "payload": decoded,
                }
                if insert_chain_event(cursor, event):
                    if decoded["event_name"] not in KGP_EVENT_NAMES:
                        projected = project_protocol_event(cursor, self.deployment_id, {
                            **decoded,
                            "transaction_hash": event["transaction_hash"],
                            "block_number": event["block_number"],
                            "log_index": event["log_index"],
                        })
                        if projected:
                            _mark_processed(cursor, self.deployment_id, event["transaction_hash"], event["log_index"])
                        else:
                            self._dead_letter(cursor, event)
                    else:
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
                SET next_block = %s, confirmed_block = %s, last_block_number = %s, last_block_hash = %s,
                    status = 'active', retry_count = 0, last_error = NULL, updated_at = NOW()
                WHERE deployment_id = %s
                """,
                (end + 1, end, end, block_hash, self.deployment_id),
            )
            self.db.commit()
            return processed

    def _reorg_detected(self, row) -> bool:
        if row[1] is None or row[2] is None:
            return False
        return _hex(self.w3.eth.get_block(int(row[1])).hash).lower() != str(row[2]).lower()

    def _rewind_after_reorg(self, cursor, last_block_number: int) -> None:
        rewind = max(0, last_block_number - CONFIRMATIONS)
        cursor.execute(
            """
            UPDATE kgp_chain_event
            SET is_canonical = FALSE, processing_status = 'rejected', orphaned_at = NOW(),
                processing_error = 'Reorg rewind; event requires canonical replay'
            WHERE deployment_id = %s AND block_number >= %s AND is_canonical = TRUE
            """,
            (self.deployment_id, rewind),
        )
        cursor.execute(
            """
            UPDATE kgp_claim
            SET claim_status = 'submitted', transaction_hash = NULL,
                block_number = NULL, claimed_at = NULL, updated_at = NOW()
            WHERE transaction_hash IN (
                SELECT transaction_hash FROM kgp_chain_event
                WHERE deployment_id = %s AND block_number >= %s AND is_canonical = FALSE
            )
            """,
            (self.deployment_id, rewind),
        )
        cursor.execute(
            """
            UPDATE guild_reputation_event
            SET settlement_status = 'submitted', contract_deployment_id = NULL,
                transaction_hash = NULL, block_number = NULL, log_index = NULL,
                settled_at = NULL, updated_at = NOW()
            WHERE contract_deployment_id = %s AND block_number >= %s
            """,
            (self.deployment_id, rewind),
        )
        cursor.execute(
            """
            UPDATE kgp_indexer_cursor
            SET next_block = %s, confirmed_block = %s, last_block_number = NULL,
                last_block_hash = NULL, status = 'reorg', updated_at = NOW()
            WHERE deployment_id = %s
            """,
            (rewind, max(0, rewind - 1), self.deployment_id),
        )

    @staticmethod
    def _dead_letter(cursor, event: dict[str, Any]) -> None:
        cursor.execute(
            """
            UPDATE kgp_chain_event
            SET processing_status = 'dead_letter',
                processing_error = 'No canonical PostgreSQL projection matched the protocol event'
            WHERE deployment_id = %s AND transaction_hash = %s AND log_index = %s
            """,
            (event["deployment_id"], event["transaction_hash"], event["log_index"]),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Kokonut Guild Points events")
    parser.add_argument("--once", action="store_true", help="scan one confirmed block range")
    parser.add_argument("--rpc-url", default=GNOSIS_RPC_URL)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--contract-address")
    parser.add_argument("--addresses-json", help='JSON map such as {"kgp":"0x...","tasks":"0x..."}')
    parser.add_argument("--chain-id", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        parser.error("--once is required until the durable worker loop is enabled")

    if not args.contract_address and not args.addresses_json:
        parser.error("one of --contract-address or --addresses-json is required")
    addresses = json.loads(args.addresses_json) if args.addresses_json else args.contract_address
    db = get_db()
    try:
        count = KGPIndexer(
            Web3(Web3.HTTPProvider(args.rpc_url)),
            db,
            args.deployment_id,
            addresses,
            args.chain_id,
        ).scan_once()
        print(json.dumps({"processed": count}))
    finally:
        db.close()


if __name__ == "__main__":
    main()
