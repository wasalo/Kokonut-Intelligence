"""Federation node management — register, sync, heartbeat."""

from __future__ import annotations

import uuid

from services.common.errors import safe_exception_class
from services.common.logging import get_logger

logger = get_logger("federation.node")

MAX_NODE_PAGE_SIZE = 100
MAX_NODE_PAGE_OFFSET = 10_000


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
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to register federation node (%s)", safe_exception_class(exc))
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
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update heartbeat for %s (%s)", node_name, safe_exception_class(exc))
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
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update federation trust level (%s)", safe_exception_class(exc))
            return False

    def list_nodes(
        self,
        status: str | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """List all federation nodes."""
        self._validate_page(limit, offset)
        return self._read_nodes(status, limit=limit, offset=offset)

    def list_nodes_page(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Return one bounded node page with exact continuation metadata."""
        if limit is None:
            raise ValueError("limit is required for paginated federation reads")
        self._validate_page(limit, offset)
        rows = self._read_nodes(None, limit=limit + 1, offset=offset)
        has_more = len(rows) > limit
        can_continue = has_more and offset + limit <= MAX_NODE_PAGE_OFFSET
        return {
            "nodes": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
            "next_offset": offset + limit if can_continue else None,
            "continuation_capped": has_more and not can_continue,
        }

    @staticmethod
    def _validate_page(limit: int | None, offset: int) -> None:
        if limit is not None and (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_NODE_PAGE_SIZE
        ):
            raise ValueError(f"limit must be an integer between 1 and {MAX_NODE_PAGE_SIZE}")
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or not 0 <= offset <= MAX_NODE_PAGE_OFFSET
        ):
            raise ValueError(
                f"offset must be an integer between 0 and {MAX_NODE_PAGE_OFFSET}"
            )

    def _read_nodes(
        self,
        status: str | None,
        *,
        limit: int | None,
        offset: int,
    ) -> list[dict]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if status:
                    query = """
                        SELECT id, node_name, node_url, trust_level,
                               shared_capabilities, last_sync_at, status, created_at
                        FROM federation_node
                        WHERE status = %s
                        ORDER BY node_name
                    """
                    parameters: tuple[object, ...] = (status,)
                else:
                    query = """
                        SELECT id, node_name, node_url, trust_level,
                               shared_capabilities, last_sync_at, status, created_at
                        FROM federation_node
                        ORDER BY trust_level, node_name
                    """
                    parameters = ()
                if limit is not None:
                    query += " LIMIT %s OFFSET %s"
                    parameters += (limit, offset)
                elif offset:
                    query += " OFFSET %s"
                    parameters += (offset,)
                cur.execute(query, parameters)
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
        except Exception as exc:
            logger.error("Failed to list federation nodes (%s)", safe_exception_class(exc))
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
        except Exception as exc:
            logger.error("Failed to get federation node (%s)", safe_exception_class(exc))
            return None
