"""Database projection helpers for Guild protocol events."""

from __future__ import annotations

import json
from typing import Any


def _guild_uuid(cursor, onchain_guild_id: str):
    cursor.execute("SELECT id FROM kokonut_guild WHERE onchain_guild_id = %s", (onchain_guild_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def _domain_uuid(cursor, deployment_id: str, onchain_domain_id: int):
    cursor.execute(
        "SELECT id FROM guild_domain WHERE deployment_id = %s AND onchain_domain_id = %s",
        (deployment_id, onchain_domain_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _task_uuid(cursor, deployment_id: str, onchain_task_id: int):
    cursor.execute(
        "SELECT id FROM guild_task WHERE deployment_id = %s AND onchain_task_id = %s",
        (deployment_id, onchain_task_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def project_protocol_event(cursor, deployment_id: str, event: dict[str, Any]) -> bool:
    """Project a decoded protocol event, returning false when identity is unresolved."""
    name = event["event_name"]
    tx_hash = event["transaction_hash"]
    block_number = event["block_number"]
    if name == "GuildCreated":
        cursor.execute(
            """
            UPDATE kokonut_guild
            SET onchain_guild_id = %s, onchain_guild_key = %s, updated_at = NOW()
            WHERE onchain_guild_key = %s OR guild_key = %s
            """,
            (event["guild_id"], event["guild_key"], event["guild_key"], event.get("guild_key_name", "")),
        )
        return cursor.rowcount == 1

    guild_uuid = _guild_uuid(cursor, event.get("guild_id", ""))
    if name == "DomainCreated":
        if not guild_uuid:
            return False
        project_domain(cursor, {
            "guild_id": guild_uuid,
            "deployment_id": deployment_id,
            "onchain_domain_id": event["domain_id"],
            "parent_onchain_domain_id": event["parent_domain_id"] or None,
            "domain_key": str(event["domain_id"]),
            "name": event["name"],
            "metadata_uri": None,
            "status": "active",
            "lifecycle_status": "submitted",
        })
        return True
    if name in {"DomainMetadataUpdated", "DomainStatusUpdated"}:
        domain_uuid = _domain_uuid(cursor, deployment_id, event["domain_id"])
        if not domain_uuid:
            return False
        if name == "DomainMetadataUpdated":
            cursor.execute("UPDATE guild_domain SET metadata_uri = %s, updated_at = NOW() WHERE id = %s", (event["metadata_uri"], domain_uuid))
        else:
            cursor.execute("UPDATE guild_domain SET status = %s, updated_at = NOW() WHERE id = %s", (_status(event["status"], ("active", "paused", "deprecated")), domain_uuid))
        return True
    if name == "TaskCreated":
        domain_uuid = _domain_uuid(cursor, deployment_id, event["domain_id"])
        if not domain_uuid or not guild_uuid:
            return False
        project_task(cursor, {
            "guild_id": guild_uuid,
            "domain_id": domain_uuid,
            "deployment_id": deployment_id,
            "onchain_task_id": event["task_id"],
            "task_key": event["task_key"],
            "metadata": {},
            "transaction_hash": tx_hash,
            "block_number": block_number,
        })
        return True
    if name in {"TaskAssigned", "TaskEvidenceSubmitted", "TaskStatusUpdated"}:
        task_uuid = _task_uuid(cursor, deployment_id, event["task_id"])
        if not task_uuid:
            return False
        if name == "TaskAssigned":
            cursor.execute("UPDATE guild_task SET contributor_wallet = %s, task_status = 'assigned', updated_at = NOW() WHERE id = %s", (event["contributor_wallet"], task_uuid))
        elif name == "TaskEvidenceSubmitted":
            cursor.execute("UPDATE guild_task SET contributor_wallet = %s, submitted_evidence_hash = %s, task_status = 'submitted', updated_at = NOW() WHERE id = %s", (event["contributor_wallet"], event["evidence_hash"], task_uuid))
        else:
            cursor.execute("UPDATE guild_task SET task_status = %s, updated_at = NOW() WHERE id = %s", (_status(event["status"], ("open", "assigned", "submitted", "accepted", "rejected", "disputed", "cancelled", "paid")), task_uuid))
        return True
    if name in {"EvidenceReviewed", "EvidenceDisputed", "EvidenceDisputeResolved", "EvidenceRevoked"}:
        task_uuid = _task_uuid(cursor, deployment_id, event.get("task_id", 0)) if event.get("task_id") else None
        if name == "EvidenceReviewed":
            if not task_uuid:
                return False
            project_evidence_review(cursor, {
                "task_id": task_uuid,
                "deployment_id": deployment_id,
                "onchain_review_id": event["review_id"],
                "reviewer_wallet": event["reviewer_wallet"],
                "evidence_hash": event["evidence_hash"],
                "notes_hash": event["notes_hash"],
                "decision": "accepted" if event["decision"] == 0 else "rejected",
                "review_status": "accepted" if event["decision"] == 0 else "rejected",
                "lifecycle_status": "submitted",
                "transaction_hash": tx_hash,
                "block_number": block_number,
            })
            cursor.execute(
                """
                INSERT INTO guild_evidence_review_event
                    (task_id, deployment_id, event_type, onchain_event_id, reviewer_wallet,
                     evidence_hash, transaction_hash, block_number, log_index, payload)
                VALUES (%s, %s, 'reviewed', %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (deployment_id, transaction_hash, log_index) DO NOTHING
                """,
                (task_uuid, deployment_id, event["review_id"], event["reviewer_wallet"], event["evidence_hash"], tx_hash, block_number, event.get("log_index"), json.dumps(event)),
            )
            return True
        cursor.execute("SELECT id FROM guild_evidence_review WHERE onchain_review_id = %s", (event["review_id"],))
        row = cursor.fetchone()
        if not row:
            return False
        if name == "EvidenceDisputed":
            cursor.execute("UPDATE guild_evidence_review SET review_status = 'disputed', dispute_reason_hash = %s, updated_at = NOW() WHERE id = %s", (event["reason_hash"], row[0]))
            event_type = "disputed"
        elif name == "EvidenceDisputeResolved":
            cursor.execute("UPDATE guild_evidence_review SET review_status = %s, resolution_hash = %s, updated_at = NOW() WHERE id = %s", ("accepted" if event["accepted"] else "rejected", event["resolution_hash"], row[0]))
            event_type = "resolved"
        else:
            cursor.execute("UPDATE guild_evidence_review SET review_status = 'revoked', updated_at = NOW() WHERE id = %s", (row[0],))
            event_type = "revoked"
        cursor.execute(
            """
            INSERT INTO guild_evidence_review_event
                (review_id, task_id, deployment_id, event_type, onchain_event_id,
                 reason_hash, resolution_hash, transaction_hash, block_number, log_index, payload)
            SELECT id, task_id, %s, %s, %s, %s, %s, %s, %s, %s, %s
            FROM guild_evidence_review WHERE id = %s
            ON CONFLICT (deployment_id, transaction_hash, log_index) DO NOTHING
            """,
            (deployment_id, event_type, event["review_id"], event.get("reason_hash"), event.get("resolution_hash"), tx_hash, block_number, event.get("log_index"), json.dumps(event), row[0]),
        )
        return True
    if name == "MotionCreated":
        if not guild_uuid:
            return False
        cursor.execute(
            """
            INSERT INTO guild_motion
                (guild_id, deployment_id, onchain_motion_id, title, target_address,
                 data_hash, objection_deadline, motion_status, lifecycle_status,
                 transaction_hash, block_number)
            VALUES (%s, %s, %s, %s, %s, %s, TO_TIMESTAMP(%s), 'open', 'submitted', %s, %s)
            ON CONFLICT (deployment_id, onchain_motion_id) DO UPDATE SET
                target_address = EXCLUDED.target_address, data_hash = EXCLUDED.data_hash,
                objection_deadline = EXCLUDED.objection_deadline, updated_at = NOW()
            """,
            (guild_uuid, deployment_id, event["motion_id"], f"Guild motion {event['motion_id']}", event["target"], event["data_hash"], event["objection_deadline"], tx_hash, block_number),
        )
        return True
    if name in {"MotionObjected", "MotionFinalized", "MotionExecuted"}:
        cursor.execute("SELECT id FROM guild_motion WHERE deployment_id = %s AND onchain_motion_id = %s", (deployment_id, event["motion_id"]))
        row = cursor.fetchone()
        if not row:
            return False
        if name == "MotionObjected":
            cursor.execute("UPDATE guild_motion SET objection_count = objection_count + 1, updated_at = NOW() WHERE id = %s", (row[0],))
        elif name == "MotionFinalized":
            cursor.execute("UPDATE guild_motion SET motion_status = %s, updated_at = NOW() WHERE id = %s", (_status(event["status"], ("open", "passed", "rejected", "executed", "cancelled")), row[0]))
        else:
            cursor.execute("UPDATE guild_motion SET motion_status = 'executed', updated_at = NOW() WHERE id = %s", (row[0],))
        return True
    return False


def _status(value: int, values: tuple[str, ...]) -> str:
    if value < 0 or value >= len(values):
        raise ValueError(f"Unknown protocol status: {value}")
    return values[value]


def project_domain(cursor, record: dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO guild_domain
            (guild_id, deployment_id, onchain_domain_id, parent_onchain_domain_id,
             domain_key, name, purpose, metadata_uri, status, lifecycle_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (deployment_id, onchain_domain_id) DO UPDATE SET
            parent_onchain_domain_id = EXCLUDED.parent_onchain_domain_id,
            name = EXCLUDED.name, purpose = EXCLUDED.purpose,
            metadata_uri = EXCLUDED.metadata_uri, status = EXCLUDED.status,
            updated_at = NOW()
        """,
        (
            record["guild_id"], record.get("deployment_id"), record["onchain_domain_id"],
            record.get("parent_onchain_domain_id"), record["domain_key"], record["name"],
            record.get("purpose"), record.get("metadata_uri"), record.get("status", "active"),
            record.get("lifecycle_status", "draft"),
        ),
    )


def project_task(cursor, record: dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO guild_task
            (guild_id, domain_id, deployment_id, onchain_task_id, task_key, task_type,
             contributor_wallet, reward_amount, reward_token, deadline,
             evidence_requirement_hash, submitted_evidence_hash, metadata_uri,
             task_status, lifecycle_status, transaction_hash, block_number, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (deployment_id, onchain_task_id) DO UPDATE SET
            contributor_wallet = EXCLUDED.contributor_wallet,
            reward_amount = EXCLUDED.reward_amount, reward_token = EXCLUDED.reward_token,
            deadline = EXCLUDED.deadline, submitted_evidence_hash = EXCLUDED.submitted_evidence_hash,
            task_status = EXCLUDED.task_status, transaction_hash = EXCLUDED.transaction_hash,
            block_number = EXCLUDED.block_number, metadata = EXCLUDED.metadata, updated_at = NOW()
        """,
        (
            record["guild_id"], record["domain_id"], record.get("deployment_id"),
            record.get("onchain_task_id"), record["task_key"], record.get("task_type", "contribution"),
            record.get("contributor_wallet"), record.get("reward_amount", 0), record.get("reward_token"),
            record.get("deadline"), record.get("evidence_requirement_hash"), record.get("submitted_evidence_hash"),
            record.get("metadata_uri"), record.get("task_status", "open"), record.get("lifecycle_status", "draft"),
            record.get("transaction_hash"), record.get("block_number"), json.dumps(record.get("metadata", {})),
        ),
    )


def project_evidence_review(cursor, record: dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO guild_evidence_review
            (task_id, deployment_id, onchain_review_id, reviewer_wallet,
             evidence_hash, evidence_cid, notes_hash, decision, review_status,
             lifecycle_status, transaction_hash, block_number, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (task_id) DO UPDATE SET
            onchain_review_id = EXCLUDED.onchain_review_id,
            reviewer_wallet = EXCLUDED.reviewer_wallet,
            evidence_hash = EXCLUDED.evidence_hash, evidence_cid = EXCLUDED.evidence_cid,
            notes_hash = EXCLUDED.notes_hash, decision = EXCLUDED.decision,
            review_status = EXCLUDED.review_status, lifecycle_status = EXCLUDED.lifecycle_status,
            transaction_hash = EXCLUDED.transaction_hash, block_number = EXCLUDED.block_number,
            metadata = EXCLUDED.metadata, updated_at = NOW()
        """,
        (
            record["task_id"], record.get("deployment_id"), record.get("onchain_review_id"),
            record.get("reviewer_wallet"), record["evidence_hash"], record.get("evidence_cid"),
            record.get("notes_hash"), record["decision"], record.get("review_status", record["decision"]),
            record.get("lifecycle_status", "draft"), record.get("transaction_hash"), record.get("block_number"),
            json.dumps(record.get("metadata", {})),
        ),
    )


def link_task_to_reputation(cursor, task_id: str, event_id: str) -> None:
    cursor.execute(
        "UPDATE guild_reputation_event SET task_id = %s, updated_at = NOW() WHERE id = %s",
        (task_id, event_id),
    )
