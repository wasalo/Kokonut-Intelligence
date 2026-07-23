"""Gateway audit — request logging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.common.logging import get_logger

logger = get_logger("gateway.audit")


class GatewayAudit:
    """Logs gateway requests for auditing."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def log(
        self,
        caller: str,
        path: str,
        method: str,
        status: str,
        ip: str = "",
        user_agent: str = "",
        duration_ms: int = 0,
        status_code: int = 200,
        reason: str = "",
    ) -> None:
        """Log a gateway request."""
        logger.info(
            "Gateway: %s %s %s [%s] caller=%s ip=%s duration=%dms",
            method, path, status, status_code, caller, ip, duration_ms,
        )

        # Write to access_audit_log if DB available
        try:
            from services.security.audit import AuditLogger
            audit = AuditLogger(conn=self._conn)
            audit.log_access(
                caller=caller,
                resource_type=f"gateway:{path}",
                action=method.lower(),
                status="allowed" if status == "allowed" else "denied",
                ip_address=ip,
                user_agent=user_agent,
                metadata={"duration_ms": duration_ms, "status_code": status_code, "reason": reason},
            )
        except Exception:
            pass  # Don't fail requests due to audit logging
