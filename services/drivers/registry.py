"""Driver registry — dynamic discovery, registration, and loading of data source drivers.

The registry maintains both an in-memory cache and the PostgreSQL driver_registry
table, enabling runtime plugin loading without modifying core code.
"""

from __future__ import annotations

import importlib
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("drivers.registry")


class DriverRegistry:
    """Central registry for data source drivers."""

    def __init__(self, conn=None):
        self._conn = conn
        self._cache: dict[str, Any] = {}  # driver_name -> driver_class

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def register(
        self,
        driver_name: str,
        driver_version: str,
        driver_type: str,
        module_path: str,
        class_name: str = "Driver",
        config_schema: dict | None = None,
        author: str | None = None,
        description: str | None = None,
    ) -> str:
        """Register a new driver in the database. Returns the driver ID."""
        import json

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO driver_registry
                        (driver_name, driver_version, driver_type, module_path,
                         class_name, config_schema, author, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (driver_name) DO UPDATE SET
                        driver_version = EXCLUDED.driver_version,
                        module_path = EXCLUDED.module_path,
                        class_name = EXCLUDED.class_name,
                        config_schema = EXCLUDED.config_schema,
                        author = EXCLUDED.author,
                        description = EXCLUDED.description,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        driver_name,
                        driver_version,
                        driver_type,
                        module_path,
                        class_name,
                        json.dumps(config_schema) if config_schema else None,
                        author,
                        description,
                    ),
                )
                row = cur.fetchone()
                driver_id = str(row[0]) if row else None
            conn.commit()
            logger.info("Registered driver: %s (id=%s)", driver_name, driver_id)
            return driver_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to register driver: %s", driver_name)
            raise

    def load(self, driver_name: str) -> Any:
        """Load a driver class by name. Returns the instantiated driver class."""
        if driver_name in self._cache:
            return self._cache[driver_name]

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT module_path, class_name, driver_version, driver_type
                    FROM driver_registry
                    WHERE driver_name = %s AND is_enabled = TRUE
                    """,
                    (driver_name,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Driver not found or disabled: {driver_name}")

                module_path, class_name, version, driver_type = row
        except Exception:
            conn.rollback()
            raise

        # Dynamic import
        try:
            module = importlib.import_module(module_path)
            driver_class = getattr(module, class_name)
            self._cache[driver_name] = driver_class
            logger.info("Loaded driver: %s v%s (%s)", driver_name, version, module_path)
            return driver_class
        except (ImportError, AttributeError) as exc:
            logger.error("Failed to load driver %s: %s", driver_name, exc)
            raise

    def list_drivers(self, driver_type: str | None = None) -> list[dict]:
        """List all registered drivers, optionally filtered by type."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if driver_type:
                    cur.execute(
                        """
                        SELECT driver_name, driver_version, driver_type, module_path,
                               class_name, is_enabled, author, description, created_at
                        FROM driver_registry
                        WHERE driver_type = %s
                        ORDER BY driver_name
                        """,
                        (driver_type,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT driver_name, driver_version, driver_type, module_path,
                               class_name, is_enabled, author, description, created_at
                        FROM driver_registry
                        ORDER BY driver_type, driver_name
                        """
                    )
                return [
                    {
                        "driver_name": r[0],
                        "driver_version": r[1],
                        "driver_type": r[2],
                        "module_path": r[3],
                        "class_name": r[4],
                        "is_enabled": r[5],
                        "author": r[6],
                        "description": r[7],
                        "created_at": r[8].isoformat() if r[8] else None,
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to list drivers")
            return []

    def list_instances(self, driver_name: str | None = None, location_id: str | None = None) -> list[dict]:
        """List driver instances."""
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if driver_name:
                conditions.append("di.driver_id = (SELECT id FROM driver_registry WHERE driver_name = %s)")
                params.append(driver_name)
            if location_id:
                conditions.append("di.location_id = %s")
                params.append(location_id)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT di.id, di.instance_name, dr.driver_name, di.config,
                           di.location_id, di.is_enabled, di.last_run_at,
                           di.last_status, di.run_count, di.consecutive_failures
                    FROM driver_instance di
                    JOIN driver_registry dr ON di.driver_id = dr.id
                    {where}
                    ORDER BY di.instance_name
                    """,
                    params,
                )
                return [
                    {
                        "instance_id": str(r[0]),
                        "instance_name": r[1],
                        "driver_name": r[2],
                        "config": r[3],
                        "location_id": str(r[4]) if r[4] else None,
                        "is_enabled": r[5],
                        "last_run_at": r[6].isoformat() if r[6] else None,
                        "last_status": r[7],
                        "run_count": r[8],
                        "consecutive_failures": r[9],
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to list driver instances")
            return []

    def create_instance(
        self,
        driver_name: str,
        instance_name: str,
        config: dict,
        location_id: str | None = None,
    ) -> str:
        """Create a new driver instance. Returns the instance ID."""
        import json

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM driver_registry WHERE driver_name = %s",
                    (driver_name,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Driver not found: {driver_name}")
                driver_id = row[0]

                cur.execute(
                    """
                    INSERT INTO driver_instance (driver_id, instance_name, config, location_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (driver_id, instance_name, json.dumps(config), location_id),
                )
                inst_row = cur.fetchone()
                instance_id = str(inst_row[0]) if inst_row else None
            conn.commit()
            logger.info("Created instance: %s (driver=%s)", instance_name, driver_name)
            return instance_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to create instance: %s", instance_name)
            raise

    def update_instance_status(
        self,
        instance_id: str,
        status: str,
        records_fetched: int = 0,
        records_written: int = 0,
        duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update instance run status and log the execution."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # Log the run
                cur.execute(
                    """
                    INSERT INTO driver_instance_log
                        (instance_id, status, records_fetched, records_written,
                         duration_ms, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (instance_id, status, records_fetched, records_written, duration_ms, error_message),
                )

                # Update instance
                if status == "success":
                    cur.execute(
                        """
                        UPDATE driver_instance
                        SET last_run_at = NOW(), last_status = %s,
                            run_count = run_count + 1, consecutive_failures = 0,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (status, instance_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE driver_instance
                        SET last_run_at = NOW(), last_status = %s,
                            last_error = %s,
                            run_count = run_count + 1,
                            consecutive_failures = consecutive_failures + 1,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (status, error_message, instance_id),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Failed to update instance status: %s", instance_id)

    def test_driver(self, driver_name: str, config: dict | None = None) -> dict:
        """Test a driver by loading it and running a health check."""
        try:
            driver_class = self.load(driver_name)
            driver = driver_class(config=config or {})
            is_healthy = driver.health_check(config or {})
            return {
                "driver_name": driver_name,
                "healthy": is_healthy,
                "message": "Driver loaded and health check passed" if is_healthy else "Health check failed",
            }
        except Exception as exc:
            return {
                "driver_name": driver_name,
                "healthy": False,
                "message": f"Failed to load or test driver: {exc}",
            }
