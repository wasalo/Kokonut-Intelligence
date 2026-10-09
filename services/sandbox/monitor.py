"""Resource monitor — tracks CPU, memory, and DB usage for sandbox runs."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from services.common.logging import get_logger

logger = get_logger("sandbox.monitor")


class ResourceMonitor:
    """Tracks resource usage for sandboxed computations."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def record_usage(self, run_id: str, resource_usage: dict) -> None:
        """Record resource usage for a run."""
        conn = self._get_conn()
        try:
            import json
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_run
                    SET resource_usage = %s
                    WHERE id = %s
                    """,
                    (json.dumps(resource_usage), run_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Failed to record resource usage")

    def get_usage_summary(self, env_id: str | None = None) -> dict:
        """Get resource usage summary across runs."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if env_id:
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) as total_runs,
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed,
                            COUNT(*) FILTER (WHERE status = 'timeout') as timeouts,
                            COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                            COALESCE(MAX(duration_ms), 0) as max_duration_ms
                        FROM analysis_run
                        WHERE environment_id = %s
                        """,
                        (env_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) as total_runs,
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed,
                            COUNT(*) FILTER (WHERE status = 'timeout') as timeouts,
                            COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                            COALESCE(MAX(duration_ms), 0) as max_duration_ms
                        FROM analysis_run
                        """
                    )
                row = cur.fetchone()

            return {
                "total_runs": row[0],
                "completed": row[1],
                "failed": row[2],
                "timeouts": row[3],
                "avg_duration_ms": round(float(row[4]), 1),
                "max_duration_ms": row[5],
            }
        except Exception:
            logger.exception("Failed to get usage summary")
            return {}

    def check_limits(self, env_id: str) -> dict:
        """Check if an environment is within resource limits."""
        from services.sandbox.isolation import IsolationGuard

        guard = IsolationGuard(conn=self._conn)
        rules = guard.get_sandbox_rules(env_id)
        if not rules:
            return {"within_limits": False, "reason": "No sandbox rules"}

        summary = self.get_usage_summary(env_id)

        warnings = []
        if summary.get("timeouts", 0) > 3:
            warnings.append(f"Multiple timeouts: {summary['timeouts']}")
        if summary.get("max_duration_ms", 0) > rules.get("max_execution_seconds", 300) * 1000:
            warnings.append("Max duration exceeded sandbox limit")
        if summary.get("failed", 0) > summary.get("total_runs", 0) * 0.5:
            warnings.append("High failure rate")

        return {
            "within_limits": len(warnings) == 0,
            "warnings": warnings,
            "limits": {
                "max_query_rows": rules.get("max_query_rows"),
                "max_execution_seconds": rules.get("max_execution_seconds"),
                "network_access": rules.get("network_access"),
            },
            "usage": summary,
        }
