"""Federation sync engine — incremental data exchange between nodes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("federation.sync")


class SyncEngine:
    """Manages incremental data synchronization between federation nodes."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def get_nodes_due_for_sync(self) -> list[dict]:
        """Get nodes that are due for synchronization."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT node_name, node_url, sync_interval_seconds, last_sync_at
                    FROM federation_node
                    WHERE status = 'active'
                      AND (last_sync_at IS NULL
                           OR last_sync_at < NOW() - (sync_interval_seconds || ' seconds')::interval)
                    ORDER BY last_sync_at ASC NULLS FIRST
                    """
                )
                return [
                    {
                        "node_name": r[0],
                        "node_url": r[1],
                        "sync_interval": r[2],
                        "last_sync": r[3].isoformat() if r[3] else None,
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to get nodes due for sync")
            return []

    def record_sync(self, node_name: str, success: bool, records_synced: int = 0, error: str | None = None) -> None:
        """Record a sync attempt."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if success:
                    cur.execute(
                        """
                        UPDATE federation_node
                        SET last_sync_at = NOW(), updated_at = NOW()
                        WHERE node_name = %s
                        """,
                        (node_name,),
                    )
                else:
                    logger.warning("Sync failed for %s: %s", node_name, error)
            conn.commit()
            logger.info("Sync recorded for %s: success=%s records=%d", node_name, success, records_synced)
        except Exception:
            conn.rollback()
            logger.exception("Failed to record sync")

    def aggregate_regional(
        self,
        data_type: str,
        region_nodes: list[str],
        period_start: str,
        period_end: str,
    ) -> dict:
        """Aggregate data across multiple nodes for regional analysis."""
        from services.federation.protocol import FederationProtocol

        protocol = FederationProtocol(conn=self._get_conn())
        shares = []

        for node_name in region_nodes:
            node_shares = protocol.get_shares(data_type=data_type, source_node_name=node_name)
            for s in node_shares:
                if s.get("period_start") and s.get("period_end"):
                    shares.append(s)

        if not shares:
            return {"data_type": data_type, "node_count": len(region_nodes), "aggregated": {}}

        # Merge aggregate data from all shares
        merged = {}
        for share in shares:
            agg = share.get("aggregate_data", {})
            for key, value in agg.items():
                if key not in merged:
                    merged[key] = []
                if isinstance(value, list):
                    merged[key].extend(value)
                else:
                    merged[key].append(value)

        return {
            "data_type": data_type,
            "node_count": len(region_nodes),
            "share_count": len(shares),
            "period_start": period_start,
            "period_end": period_end,
            "aggregated": merged,
        }
