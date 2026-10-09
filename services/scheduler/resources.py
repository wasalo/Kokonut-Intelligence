"""Resource pool manager for the task scheduler.

Tracks concurrent resource usage to prevent tasks from
overloading shared resources (DB connections, API quotas, etc.).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from services.common.logging import get_logger

logger = get_logger("scheduler.resources")


class ResourcePool:
    """Manages concurrent resource allocation for scheduled tasks."""

    def __init__(self, conn):
        self._conn = conn

    def acquire(self, resource_name: str, worker_id: str = "default") -> bool:
        """Try to acquire a resource slot. Returns True if acquired."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE task_resource
                SET current_running = current_running + 1
                WHERE resource_name = %s
                  AND current_running < max_concurrent
                RETURNING max_concurrent, current_running
                """,
                (resource_name,),
            )
            row = cur.fetchone()
            if row:
                self._conn.commit()
                logger.debug(
                    "Acquired resource %s (%d/%d)",
                    resource_name, row[1], row[0],
                )
                return True
            self._conn.rollback()
            return False

    def release(self, resource_name: str) -> None:
        """Release a resource slot."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE task_resource
                SET current_running = GREATEST(current_running - 1, 0)
                WHERE resource_name = %s
                """,
                (resource_name,),
            )
        self._conn.commit()

    def get_status(self) -> list[dict]:
        """Get current resource usage."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT resource_name, resource_type, max_concurrent,
                       current_running, max_wait_seconds
                FROM task_resource
                ORDER BY resource_name
                """
            )
            return [
                {
                    "name": row[0],
                    "type": row[1],
                    "max": row[2],
                    "running": row[3],
                    "max_wait": row[4],
                }
                for row in cur.fetchall()
            ]

    def wait_for_resource(
        self, resource_name: str, timeout: float = 30.0, worker_id: str = "default"
    ) -> bool:
        """Wait for a resource slot to become available."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.acquire(resource_name, worker_id):
                return True
            time.sleep(1.0)
        logger.warning("Timed out waiting for resource %s", resource_name)
        return False
