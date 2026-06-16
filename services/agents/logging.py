"""
Agent Action Logging

Logs agent actions to agent_action_log with high_risk flagging.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from ..ingestion.base import get_db

HIGH_RISK_ACTIONS = {
    "publish", "attest", "onchain_submit", "delete", "bulk_update",
    "financial_write", "status_change_to_published",
}


def log_agent_action(
    agent_id: str,
    task_id: Optional[str],
    action: str,
    collection: str,
    record_id: Optional[str] = None,
    payload_hash: Optional[str] = None,
    action_result: str = "success",
    error_message: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Log an agent action to agent_action_log.

    Returns the log entry ID.
    """
    is_high_risk = action in HIGH_RISK_ACTIONS
    log_id = str(uuid.uuid4())

    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO agent_action_log
                    (id, agent_id, task_id, action, collection, record_id,
                     payload_hash, action_result, error_message, metadata,
                     high_risk, requires_human_approval, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
            """, (
                log_id, agent_id, task_id, action, collection, record_id,
                payload_hash, action_result, error_message,
                __import__("json").dumps(metadata) if metadata else None,
                is_high_risk, is_high_risk,
            ))
        db.commit()
        db.close()
    except Exception as e:
        print(f"[Agent Logging] Failed to log action: {e}")

    return log_id


def get_agent_actions(
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    high_risk_only: bool = False,
    limit: int = 50,
) -> list:
    """Query agent action log entries."""
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        conditions = []
        params = []

        if agent_id:
            conditions.append("agent_id = %s")
            params.append(agent_id)
        if task_id:
            conditions.append("task_id = %s")
            params.append(task_id)
        if high_risk_only:
            conditions.append("high_risk = TRUE")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT id, agent_id, task_id, action, collection, record_id,
                   action_result, error_message, high_risk,
                   requires_human_approval, created_at
            FROM agent_action_log
            {where}
            ORDER BY created_at DESC
            LIMIT %s
        """, params + [limit])

        return [dict(r) for r in cur.fetchall()]
