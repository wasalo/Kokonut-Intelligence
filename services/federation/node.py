"""Federation node management — register, sync, heartbeat."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("federation.node")


class FederationNode:
    """Manages federation nodes — remote farms that share data."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def register(
        self,
        node_name: str,
        node_url: str,
        node_public_key: str | None = None,
        trust_level: str = "untrusted",
        shared_capabilities: list[dict] | None = None,
    ) -> str:
        """Register a new federation node. Returns node ID."""
        import json

        node_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO federation_node
                        (id, node_name, node_url, node_public_key,
                         trust_level, shared_capabilities)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (node_name) DO UPDATE SET
                        node_url = EXCLUDED.node_url,
                        node_public_key = EXCLUDED.node_public_key,
                        trust_level = EXCLUDED.trust_level,
                        shared_capabilities = EXCLUDED.shared_capabilities,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        node_id, node_name, node_url, node_public_key,
                        trust_level,
                        json.dumps(shared_capabilities) if shared_capabilities else "[]",
                    ),
                )
                row = cur.fetchone()
                result_id = str(row[0]) if row else node_id
            conn.commit()
            logger.info("Registered federation node: %s (id=%s, trust=%s)", node_name, result_id, trust_level)
            return result_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to register federation node")
            raise

    def update_heartbeat(self, node_name: str) -> bool:
        """Update last sync time for a node (heartbeat)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE federation_node
                    SET last_sync_at = NOW(), updated_at = NOW()
                    WHERE node_name = %s AND status = 'active'
                    RETURNING id
                    """,
                    (node_name,),
                )
                result = cur.fetchone()
            conn.commit()
            return result is not None
        except Exception:
            conn.rollback()
            logger.exception("Failed to update heartbeat for %s", node_name)
            return False

    def set_trust_level(self, node_name: str, trust_level: str) -> bool:
        """Update trust level for a node."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE federation_node
                    SET trust_level = %s, updated_at = NOW()
                    WHERE node_name = %s
                    RETURNING id
                    """,
                    (trust_level, node_name),
                )
                result = cur.fetchone()
            conn.commit()
            if result:
                logger.info("Updated trust level for %s to %s", node_name, trust_level)
            return result is not None
        except Exception:
            conn.rollback()
            logger.exception("Failed to update trust level")
            return False

    def list_nodes(self, status: str | None = None) -> list[dict]:
        """List all federation nodes."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id, node_name, node_url, trust_level,
                               shared_capabilities, last_sync_at, status, created_at
                        FROM federation_node
                        WHERE status = %s
                        ORDER BY node_name
                        """,
                        (status,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, node_name, node_url, trust_level,
                               shared_capabilities, last_sync_at, status, created_at
                        FROM federation_node
                        ORDER BY trust_level, node_name
                        """
                    )
                return [
                    {
                        "node_id": str(r[0]),
                        "node_name": r[1],
                        "node_url": r[2],
                        "trust_level": r[3],
                        "shared_capabilities": r[4],
                        "last_sync_at": r[5].isoformat() if r[5] else None,
                        "status": r[6],
                        "created_at": r[7].isoformat(),
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to list federation nodes")
            return []

    def get_node(self, node_name: str) -> dict | None:
        """Get a single federation node."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, node_name, node_url, trust_level,
                           shared_capabilities, last_sync_at, status, created_at
                    FROM federation_node
                    WHERE node_name = %s
                    """,
                    (node_name,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "node_id": str(row[0]),
                    "node_name": row[1],
                    "node_url": row[2],
                    "trust_level": row[3],
                    "shared_capabilities": row[4],
                    "last_sync_at": row[5].isoformat() if row[5] else None,
                    "status": row[6],
                    "created_at": row[7].isoformat(),
                }
        except Exception:
            logger.exception("Failed to get federation node")
            return None
