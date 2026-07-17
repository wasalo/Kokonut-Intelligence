"""Database projection helpers for Guild protocol events."""

from __future__ import annotations

import json
from typing import Any


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
