"""Analysis environment — create, destroy, and run computations in isolated contexts."""

from __future__ import annotations

import json
import time
import uuid
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("sandbox.environment")


class AnalysisEnvironment:
    """Isolated computation context per farm."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def create(
        self,
        location_id: str,
        env_type: str = "sandbox",
        config: dict | None = None,
    ) -> str:
        """Create a new analysis environment. Returns environment ID."""
        env_id = str(uuid.uuid4())
        conn = self._get_conn()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_environment (id, location_id, env_type, config)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (env_id, location_id, env_type, json.dumps(config or {})),
                )

                # Create default sandbox rules
                cur.execute(
                    """
                    INSERT INTO analysis_sandbox (environment_id, allowed_tables, denied_tables)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        env_id,
                        ["location", "sensor_reading", "harvest_event", "metric_value"],
                        ["capability_token", "access_audit_log"],
                    ),
                )
            conn.commit()
            logger.info("Created analysis environment: %s (type=%s, location=%s)", env_id[:8], env_type, location_id[:8])
            return env_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to create analysis environment")
            raise

    def destroy(self, env_id: str) -> bool:
        """Destroy an analysis environment."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_environment
                    SET status = 'destroyed', destroyed_at = NOW()
                    WHERE id = %s AND status = 'active'
                    RETURNING id
                    """,
                    (env_id,),
                )
                result = cur.fetchone()
            conn.commit()
            if result:
                logger.info("Destroyed analysis environment: %s", env_id[:8])
            return result is not None
        except Exception:
            conn.rollback()
            logger.exception("Failed to destroy analysis environment")
            return False

    def run(
        self,
        env_id: str,
        module_path: str,
        input_params: dict | None = None,
        timeout_seconds: int = 300,
    ) -> dict:
        """Execute a computation in the sandbox. Returns run result."""
        run_id = str(uuid.uuid4())
        conn = self._get_conn()

        # Create run record
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_run (id, environment_id, module_path, input_params)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (run_id, env_id, module_path, json.dumps(input_params or {})),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Failed to create analysis run")
            return {"error": "Failed to create run record"}

        # Execute in subprocess
        start_time = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, "-m", module_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)

            status = "completed" if result.returncode == 0 else "failed"
            output = result.stdout[-5000:] if result.stdout else None
            error = result.stderr[-2000:] if result.returncode != 0 else None

            self._complete_run(run_id, status, output, error, duration_ms)

            return {
                "run_id": run_id,
                "status": status,
                "duration_ms": duration_ms,
                "output": output,
                "error": error,
            }

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._complete_run(run_id, "timeout", None, "Execution timed out", duration_ms)
            return {"run_id": run_id, "status": "timeout", "duration_ms": duration_ms, "error": "Timed out"}

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._complete_run(run_id, "failed", None, str(exc), duration_ms)
            return {"run_id": run_id, "status": "failed", "duration_ms": duration_ms, "error": str(exc)}

    def _complete_run(self, run_id: str, status: str, output: str | None, error: str | None, duration_ms: int) -> None:
        """Update run record with completion status."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_run
                    SET status = %s, completed_at = NOW(), duration_ms = %s,
                        output_result = %s, error_message = %s
                    WHERE id = %s
                    """,
                    (status, duration_ms, output, error, run_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Failed to complete analysis run")

    def list_environments(self, location_id: str | None = None, status: str | None = None) -> list[dict]:
        """List analysis environments."""
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if location_id:
                conditions.append("location_id = %s")
                params.append(location_id)
            if status:
                conditions.append("status = %s")
                params.append(status)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, location_id, env_type, status, created_at, destroyed_at
                    FROM analysis_environment
                    {where}
                    ORDER BY created_at DESC
                    """,
                    params,
                )
                return [
                    {
                        "env_id": str(r[0]),
                        "location_id": str(r[1]),
                        "env_type": r[2],
                        "status": r[3],
                        "created_at": r[4].isoformat(),
                        "destroyed_at": r[5].isoformat() if r[5] else None,
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to list environments")
            return []

    def list_runs(self, env_id: str | None = None, limit: int = 20) -> list[dict]:
        """List analysis runs."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if env_id:
                    cur.execute(
                        """
                        SELECT ar.id, ae.env_type, ar.module_path, ar.status,
                               ar.started_at, ar.completed_at, ar.duration_ms, ar.error_message
                        FROM analysis_run ar
                        JOIN analysis_environment ae ON ar.environment_id = ae.id
                        WHERE ar.environment_id = %s
                        ORDER BY ar.started_at DESC
                        LIMIT %s
                        """,
                        (env_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT ar.id, ae.env_type, ar.module_path, ar.status,
                               ar.started_at, ar.completed_at, ar.duration_ms, ar.error_message
                        FROM analysis_run ar
                        JOIN analysis_environment ae ON ar.environment_id = ae.id
                        ORDER BY ar.started_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                return [
                    {
                        "run_id": str(r[0]),
                        "env_type": r[1],
                        "module_path": r[2],
                        "status": r[3],
                        "started_at": r[4].isoformat(),
                        "completed_at": r[5].isoformat() if r[5] else None,
                        "duration_ms": r[6],
                        "error_message": r[7],
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to list runs")
            return []
