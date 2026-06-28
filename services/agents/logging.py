"""
Agent Action Logging

Logs agent actions to agent_action_log with high_risk flagging.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger
from services.ingestion.base import get_db

logger = get_logger("services.agents.logging")


def _get_high_risk_actions():
    """Lazy import to avoid circular dependency with safety.py."""
    from services.agents.safety import HIGH_RISK_ACTIONS
    return HIGH_RISK_ACTIONS


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
    is_high_risk = action in _get_high_risk_actions()
    log_id = str(uuid.uuid4())

    db = None
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
                json.dumps(metadata) if metadata else None,
                is_high_risk, is_high_risk,
            ))
        db.commit()
    except Exception as e:
        logger.error("Failed to log agent action: %s", e)
    finally:
        if db is not None:
            db.close()

    return log_id


def get_agent_actions(
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    high_risk_only: bool = False,
    limit: int = 50,
) -> list:
    """Query agent action log entries."""
    db = None
    try:
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
    finally:
        if db is not None:
            db.close()
