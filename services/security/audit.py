"""Audit logger — logs all access attempts to access_audit_log."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from services.common.logging import get_logger

logger = get_logger("security.audit")


class AuditLogger:
    """Logs access attempts for zero-trust auditing."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def log_access(
        self,
        caller: str,
        resource_type: str,
        action: str,
        status: str,
        capability_token_id: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
        event_id: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> str:
        """Log an access attempt. Returns the log entry ID."""
        log_id = str(uuid.uuid4()) if event_id is None else str(uuid.UUID(str(event_id)))
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at)
        if occurred_at is not None and occurred_at.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        created_at = occurred_at or datetime.now(timezone.utc)
        conn = self._get_conn()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO access_audit_log
                        (id, caller, capability_token_id, resource_type,
                         resource_id, action, status, ip_address, user_agent, metadata,
                         created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        log_id, caller, capability_token_id,
                        resource_type, resource_id, action, status,
                        ip_address, user_agent,
                        __import__("json").dumps(metadata) if metadata else None,
                        created_at,
                    ),
                )
            conn.commit()
            log_fn = logger.warning if status == "denied" else logger.debug
            log_fn("Access: %s %s %s on %s=%s [%s]", caller, action, status, resource_type, resource_id, log_id[:8])
            return log_id
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to log access (%s)", type(exc).__name__)
            raise

    def query_logs(
        self,
        caller: str | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query access audit logs with filters."""
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if caller:
                conditions.append("caller = %s")
                params.append(caller)
            if resource_type:
                conditions.append("resource_type = %s")
                params.append(resource_type)
            if action:
                conditions.append("action = %s")
                params.append(action)
            if status:
                conditions.append("status = %s")
                params.append(status)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, caller, capability_token_id, resource_type,
                           resource_id, action, status, ip_address, created_at
                    FROM access_audit_log
                    {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [
                    {
                        "log_id": str(r[0]),
                        "caller": r[1],
                        "token_id": str(r[2]) if r[2] else None,
                        "resource_type": r[3],
                        "resource_id": str(r[4]) if r[4] else None,
                        "action": r[5],
                        "status": r[6],
                        "ip_address": str(r[7]) if r[7] else None,
                        "created_at": r[8].isoformat(),
                    }
                    for r in cur.fetchall()
                ]
        except Exception as exc:
            logger.error("Failed to query audit logs (%s)", type(exc).__name__)
            return []

    def stats(self) -> dict:
        """Get audit log statistics."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        status,
                        COUNT(*),
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour'),
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours')
                    FROM access_audit_log
                    GROUP BY status
                    """
                )
                by_status = {r[0]: {"total": r[1], "last_hour": r[2], "last_24h": r[3]} for r in cur.fetchall()}

                cur.execute(
                    """
                    SELECT caller, COUNT(*) as cnt
                    FROM access_audit_log
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY caller
                    ORDER BY cnt DESC
                    LIMIT 10
                    """
                )
                top_callers = [{"caller": r[0], "count": r[1]} for r in cur.fetchall()]

            return {"by_status": by_status, "top_callers": top_callers}
        except Exception as exc:
            logger.error("Failed to get audit stats (%s)", type(exc).__name__)
            return {}
