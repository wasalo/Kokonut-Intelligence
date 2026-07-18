"""Analysis environment — create, destroy, and run computations in isolated contexts."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("sandbox.environment")

# Whitelist of modules allowed to run inside the sandbox.
# Only registered modules may execute; arbitrary paths are rejected.
_ALLOWED_MODULES: set[str] = {
    "services.analytics.yield_monitoring",
    "services.analytics.evapotranspiration",
    "services.analytics.crop_phenology",
    "services.analytics.precision_irrigation",
    "services.analytics.pest_management",
    "services.analytics.digital_twin",
    "services.analytics.carbon_credits",
    "services.analytics.advisor",
    "services.analytics.equipment",
    "services.analytics.marketplace",
    "services.analytics.traceability",
    "services.analytics.portfolio",
    "services.crisp",
    "services.metrics.engine",
}

# Pattern that module paths must match (dotted Python names only).
_MODULE_PATH_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")

# Environment variables removed from the child process to prevent leakage.
_SANITISED_ENV_KEYS = frozenset({
    "KOKONUT_DB_URL", "KOKONUT_CLICKHOUSE_URL", "KOKONUT_DIRECTUS_TOKEN",
    "KOKONUT_EAS_PRIVATE_KEY", "KOKONUT_JWT_SECRET", "POSTGRES_PASSWORD",
    "REDIS_PASSWORD", "KOKONUT_API_KEY", "EAS_PRIVATE_KEY",
})


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
        """Execute a computation in the sandbox. Returns run result.

        The module_path must be a dotted Python module name registered in the
        sandbox whitelist.  Arbitrary filesystem paths and imports outside the
        allowlist are rejected.
        """
        if not _MODULE_PATH_RE.match(module_path):
            logger.warning("Rejected invalid module path: %s", module_path)
            return {"error": "Invalid module path format"}

        if module_path not in _ALLOWED_MODULES:
            logger.warning("Rejected unregistered module: %s", module_path)
            return {"error": f"Module not allowed: {module_path}"}

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

        # Build a sanitised environment for the child process.
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k not in _SANITISED_ENV_KEYS
        }

        # Execute in subprocess
        start_time = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, "-m", module_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=clean_env,
                cwd="/tmp",
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
