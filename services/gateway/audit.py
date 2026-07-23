"""Gateway audit — request logging."""

from __future__ import annotations

import ipaddress
from uuid import UUID

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
        resource: str = "gateway",
        action: str = "read",
        location_id: str | None = None,
        capability_token_id: str | None = None,
    ) -> None:
        """Log a gateway request."""
        logger.info(
            "Gateway: %s %s %s [%s] caller=%s ip=%s duration=%dms",
            method, path, status, status_code, caller, ip, duration_ms,
        )

        action_map = {
            "GET": "read",
            "POST": "write",
            "PUT": "write",
            "PATCH": "write",
            "DELETE": "delete",
        }
        db_action = action_map.get(method.upper(), action if action in {
            "read", "write", "attest", "publish", "delete", "admin",
        } else "admin")
        try:
            safe_ip = str(ipaddress.ip_address(ip)) if ip else None
        except ValueError:
            safe_ip = None
        try:
            safe_resource_id = str(UUID(location_id)) if location_id else None
        except (ValueError, TypeError, AttributeError):
            safe_resource_id = None

        # Write to access_audit_log if DB available. The table accepts
        # semantic actions, not raw HTTP verbs.
        try:
            from services.security.audit import AuditLogger
            audit = AuditLogger(conn=self._conn)
            audit.log_access(
                caller=caller,
                resource_type=f"gateway:{resource}",
                action=db_action,
                status="allowed" if status == "allowed" else "denied",
                capability_token_id=capability_token_id,
                resource_id=safe_resource_id,
                ip_address=safe_ip,
                user_agent=user_agent,
                metadata={
                    "duration_ms": duration_ms,
                    "status_code": status_code,
                    "reason": reason,
                    "path": path,
                    "http_method": method.upper(),
                    "route_action": action,
                },
            )
        except Exception as exc:
            # Audit failure must not break the request, but it must be visible
            # to operators instead of being silently discarded.
            logger.exception("Durable gateway audit failed: %s", exc)
