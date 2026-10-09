"""Federation protocol — share data and query across farm nodes."""

from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("federation.protocol")


class FederationProtocol:
    """Handles inter-farm data sharing and querying."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def share(
        self,
        source_node_name: str,
        data_type: str,
        aggregate_data: dict,
        period_start: str | None = None,
        period_end: str | None = None,
        consent_level: str = "aggregate",
    ) -> str:
        """Share aggregated data from a node. Returns share ID."""
        conn = self._get_conn()
        share_id = str(uuid.uuid4())

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM federation_node WHERE node_name = %s",
                    (source_node_name,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Federation node not found: {source_node_name}")
                source_node_id = row[0]

                cur.execute(
                    """
                    INSERT INTO federation_share
                        (id, source_node_id, data_type, aggregate_data,
                         period_start, period_end, consent_level)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        share_id, source_node_id, data_type,
                        json.dumps(aggregate_data),
                        period_start, period_end, consent_level,
                    ),
                )
            conn.commit()
            logger.info("Shared %s data from %s (id=%s)", data_type, source_node_name, share_id[:8])
            return share_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to share data")
            raise

    def query(
        self,
        query_type: str,
        parameters: dict | None = None,
        requesting_node_name: str | None = None,
    ) -> str:
        """Submit a federation query. Returns query ID."""
        conn = self._get_conn()
        query_id = str(uuid.uuid4())

        try:
            with conn.cursor() as cur:
                requesting_node_id = None
                if requesting_node_name:
                    cur.execute(
                        "SELECT id FROM federation_node WHERE node_name = %s",
                        (requesting_node_name,),
                    )
                    row = cur.fetchone()
                    if row:
                        requesting_node_id = row[0]

                cur.execute(
                    """
                    INSERT INTO federation_query
                        (id, query_type, parameters, requesting_node_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (query_id, query_type, json.dumps(parameters or {}), requesting_node_id),
                )
            conn.commit()
            logger.info("Federation query submitted: %s (id=%s)", query_type, query_id[:8])
            return query_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to submit federation query")
            raise

    def complete_query(self, query_id: str, result: dict, status: str = "completed") -> bool:
        """Mark a federation query as complete with results."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE federation_query
                    SET result = %s, status = %s, completed_at = NOW()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (json.dumps(result), status, query_id),
                )
                row = cur.fetchone()
            conn.commit()
            return row is not None
        except Exception:
            conn.rollback()
            logger.exception("Failed to complete federation query")
            return False

    def get_shares(
        self,
        data_type: str | None = None,
        source_node_name: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get federation shares."""
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if data_type:
                conditions.append("fs.data_type = %s")
                params.append(data_type)
            if source_node_name:
                conditions.append("fn.node_name = %s")
                params.append(source_node_name)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT fs.id, fn.node_name, fs.data_type, fs.aggregate_data,
                           fs.period_start, fs.period_end, fs.consent_level,
                           fs.shared_at, fs.verified
                    FROM federation_share fs
                    JOIN federation_node fn ON fs.source_node_id = fn.id
                    {where}
                    ORDER BY fs.shared_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [
                    {
                        "share_id": str(r[0]),
                        "source_node": r[1],
                        "data_type": r[2],
                        "aggregate_data": r[3],
                        "period_start": r[4].isoformat() if r[4] else None,
                        "period_end": r[5].isoformat() if r[5] else None,
                        "consent_level": r[6],
                        "shared_at": r[7].isoformat(),
                        "verified": r[8],
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to get federation shares")
            return []

    def get_queries(self, status: str | None = None, limit: int = 20) -> list[dict]:
        """Get federation queries."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT fq.id, fq.query_type, fq.parameters, fq.status,
                               fq.result, fq.created_at, fq.completed_at
                        FROM federation_query fq
                        WHERE fq.status = %s
                        ORDER BY fq.created_at DESC
                        LIMIT %s
                        """,
                        (status, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT fq.id, fq.query_type, fq.parameters, fq.status,
                               fq.result, fq.created_at, fq.completed_at
                        FROM federation_query fq
                        ORDER BY fq.created_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                return [
                    {
                        "query_id": str(r[0]),
                        "query_type": r[1],
                        "parameters": r[2],
                        "status": r[3],
                        "result": r[4],
                        "created_at": r[5].isoformat(),
                        "completed_at": r[6].isoformat() if r[6] else None,
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to get federation queries")
            return []
