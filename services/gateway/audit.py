"""Gateway audit — request logging."""

from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from uuid import UUID, uuid4

from services.common.errors import safe_exception_class
from services.common.logging import get_logger
from services.gateway.audit_spool import GatewayAuditSpool

logger = get_logger("gateway.audit")


class GatewayAudit:
    """Logs gateway requests for auditing."""

    def __init__(self, conn=None):
        self._conn = conn
        self._spool = None
        self._spool_seen = False
        self._reported_capture_state = "ok"

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            return get_db(connect_timeout=3)
        return self._conn

    def _get_spool(self) -> GatewayAuditSpool:
        if self._spool is None:
            self._spool = GatewayAuditSpool()
        return self._spool

    def _report_capture_state(self, state: str, capacity: dict | None = None, reason: str = "") -> None:
        if state == self._reported_capture_state:
            return
        if state == "degraded":
            logger.error(
                "Gateway audit journal capacity reached its alert threshold; pending=%d reservations=%d threshold=%d max=%d; mutation requests are restricted",
                capacity["pending_events"],
                capacity.get("active_mutation_reservations", 0),
                capacity["alert_threshold_events"],
                capacity["max_pending_events"],
            )
        elif state == "unavailable":
            logger.error("Gateway audit journal storage is unavailable (%s); mutation requests are restricted", reason)
        elif self._reported_capture_state != "ok":
            logger.info("Gateway audit journal capture returned to a healthy state")
        self._reported_capture_state = state

    def capture_status(self) -> str:
        """Return an event-free health indicator for the public health route."""
        try:
            spool = self._get_spool()
            if spool.path.exists():
                self._spool_seen = True
            elif self._spool_seen:
                self._report_capture_state("unavailable", reason="journal_file_missing")
                return "unavailable"
            capacity = spool.capacity_status(
                ensure_storage=self._reported_capture_state == "unavailable"
            )
        except Exception as exc:
            self._report_capture_state("unavailable", reason=type(exc).__name__)
            return "unavailable"
        if spool.path.exists():
            self._spool_seen = True
        state = "degraded" if capacity["write_restricted"] else "ok"
        self._report_capture_state(state, capacity=capacity)
        return state

    def allow_mutation(self) -> bool:
        """Fail closed before a mutation when journal storage is unavailable or near full."""
        try:
            spool = self._get_spool()
            if spool.path.exists():
                self._spool_seen = True
            elif self._spool_seen:
                self._report_capture_state("unavailable", reason="journal_file_missing")
                return False
            spool.prune_stale_reservations()
            capacity = spool.capacity_status(ensure_storage=True)
            self._spool_seen = True
            if capacity["pending_events"]:
                try:
                    replayed = self.replay_pending()
                except Exception as exc:
                    logger.warning(
                        "Gateway audit replay deferred during write preflight (%s)",
                        type(exc).__name__,
                    )
                    capacity = spool.capacity_status(ensure_storage=True)
                else:
                    if replayed:
                        capacity = spool.capacity_status(ensure_storage=True)
        except Exception as exc:
            self._report_capture_state("unavailable", reason=type(exc).__name__)
            return False
        state = "degraded" if capacity["write_restricted"] else "ok"
        self._report_capture_state(state, capacity=capacity)
        return not capacity["write_restricted"]

    def reserve_mutation(self) -> str | None:
        """Reserve threshold headroom for one in-flight mutation across workers.

        The gateway writes an audit record after its handler returns. Without an
        atomic journal reservation, concurrent requests could all observe the
        same free headroom and collectively cross the threshold before their
        audit events are queued.
        """
        if not self.allow_mutation():
            return None
        try:
            spool = self._get_spool()
            token = spool.reserve_mutation()
            if token is None:
                capacity = spool.capacity_status()
                state = "degraded" if capacity["write_restricted"] else "ok"
                self._report_capture_state(state, capacity=capacity)
            return token
        except Exception as exc:
            self._report_capture_state("unavailable", reason=type(exc).__name__)
            return None

    def release_mutation(self, token: str) -> None:
        """Release a request's journal headroom reservation."""
        try:
            self._get_spool().release_mutation(token)
        except Exception as exc:
            logger.error("Gateway audit mutation reservation release failed (%s)", type(exc).__name__)

    def _write_record(self, event: dict) -> None:
        owns_conn = self._conn is None
        conn = None
        try:
            conn = self._get_conn()
            from services.security.audit import AuditLogger

            AuditLogger(conn=conn).log_access(**event)
        finally:
            if owns_conn and conn is not None:
                conn.close()

    def replay_pending(self, limit: int = 100) -> int:
        """Replay the oldest bounded journal batch, acknowledging committed IDs."""
        spool = self._get_spool()
        if spool.path.exists():
            self._spool_seen = True
        pending = spool.pending(limit=limit)
        if not pending:
            return 0

        owns_conn = self._conn is None
        conn = None
        replayed = 0
        try:
            conn = self._get_conn()
            from services.security.audit import AuditLogger

            audit = AuditLogger(conn=conn)
            for event in pending:
                audit.log_access(**event)
                spool.acknowledge(event["event_id"])
                replayed += 1
        finally:
            if owns_conn and conn is not None:
                conn.close()
        if replayed:
            logger.info("Replayed %d gateway audit journal events", replayed)
            capacity = spool.capacity_status()
            state = "degraded" if capacity["alert_active"] else "ok"
            self._report_capture_state(state, capacity=capacity)
        return replayed

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
        scope_checked: str | None = None,
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

        # The table accepts semantic actions, not raw HTTP verbs. The event ID
        # and occurrence time remain stable if a committed write must be retried.
        outcome = "allowed" if status == "allowed" else "error" if status == "error" else "denied"
        event = {
            "event_id": str(uuid4()),
            "caller": caller[:100],
            "resource_type": f"gateway:{resource}"[:100],
            "action": db_action,
            "status": "allowed" if status == "allowed" else "denied",
            "capability_token_id": capability_token_id,
            "resource_id": safe_resource_id,
            "ip_address": safe_ip,
            "user_agent": (user_agent or "")[:1024],
            "metadata": {
                "outcome": outcome,
                "duration_ms": duration_ms,
                "status_code": status_code,
                "reason": (reason or "")[:256],
                "path": (path or "")[:2048],
                "http_method": method.upper()[:16],
                "route_action": (action or "")[:64],
                "scope_checked": (scope_checked or "")[:256] or None,
            },
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.replay_pending()
        except Exception as exc:
            # A journal read/replay problem must not suppress a direct write
            # when PostgreSQL itself is healthy.
            logger.warning("Gateway audit replay deferred (%s)", type(exc).__name__)
        try:
            self._write_record(event)
        except Exception as exc:
            # Preserve the event locally so a later request or replay worker can
            # deliver it after PostgreSQL returns. The journal is bounded and
            # reports failures rather than silently dropping overflow.
            logger.error(
                "Gateway audit database write failed (%s)",
                safe_exception_class(exc),
            )
            try:
                pending_count = self._get_spool().enqueue(event)
                spool = self._get_spool()
                self._spool_seen = True
                capacity = {
                    "pending_events": pending_count,
                    "alert_threshold_events": spool.alert_threshold,
                    "max_pending_events": spool.max_pending,
                    "alert_active": pending_count >= spool.alert_threshold,
                    "write_restricted": pending_count >= spool.alert_threshold,
                }
                state = "degraded" if capacity["alert_active"] else "ok"
                self._report_capture_state(state, capacity=capacity)
                logger.warning("Gateway audit event retained in local journal; pending=%d", pending_count)
            except Exception as exc:
                logger.error(
                    "Gateway audit local journal could not retain an event (%s)",
                    safe_exception_class(exc),
                )
