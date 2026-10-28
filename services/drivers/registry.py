"""Driver registry — dynamic discovery, registration, and loading of data source drivers.

The registry maintains both an in-memory cache and the PostgreSQL driver_registry
table, enabling runtime plugin loading without modifying core code.
"""

from __future__ import annotations

import importlib
from importlib import metadata
from types import MappingProxyType
from typing import Any

from services.common.errors import safe_exception_class
from services.common.logging import get_logger

logger = get_logger("drivers.registry")

# Persisted driver_registry.module_path values are data, not executable policy.
# Built-in driver names resolve only to these source-controlled targets.
BUILTIN_DRIVER_TARGETS = MappingProxyType(
    {
        "blockchain_eas": (
            "services.ingestion.drivers.blockchain_eas",
            "Driver",
            "blockchain",
        ),
        "blockchain_gnosis": (
            "services.ingestion.drivers.blockchain_gnosis",
            "Driver",
            "blockchain",
        ),
        "blockchain_rpc": (
            "services.ingestion.drivers.blockchain_rpc",
            "Driver",
            "blockchain",
        ),
        "market_worldbank": (
            "services.ingestion.drivers.market_worldbank",
            "Driver",
            "market",
        ),
        "remote_sensing_copernicus": (
            "services.ingestion.drivers.remote_sensing_copernicus",
            "Driver",
            "remote_sensing",
        ),
        "remote_sensing_gee": (
            "services.ingestion.drivers.remote_sensing_gee",
            "Driver",
            "remote_sensing",
        ),
        "sensor_csv": (
            "services.ingestion.drivers.sensor_csv",
            "Driver",
            "sensor",
        ),
        "sensor_mqtt": (
            "services.ingestion.drivers.sensor_mqtt",
            "Driver",
            "sensor",
        ),
        "weather_openweathermap": (
            "services.ingestion.drivers.weather_openweathermap",
            "Driver",
            "weather",
        ),
    }
)

# Third-party adapters stay extensible through installed Python packages. The
# entry point resolves installed code; database rows only confirm its identity.
DRIVER_PLUGIN_ENTRY_POINT_GROUP = "kokonut.drivers"
PUBLIC_DRIVER_CATALOG_MAX_PAGE_SIZE = 50
PUBLIC_DRIVER_CATALOG_MAX_OFFSET = 5000

# Scheduled sensor pulls have a narrower code-controlled map. Adding another
# scheduled implementation requires a reviewed source change and tests.
SCHEDULED_SENSOR_DRIVER_TARGETS = MappingProxyType(
    {
        "sensor_csv": (
            "services.ingestion.drivers.sensor_csv",
            "Driver",
            "sensor",
        ),
    }
)


def _validate_driver_registration_target(
    driver_name: str,
    module_path: str,
    class_name: str,
    driver_type: str,
) -> None:
    """Reject registry metadata that has no matching code-owned target."""
    builtin_target = BUILTIN_DRIVER_TARGETS.get(driver_name)
    if builtin_target is not None:
        if builtin_target != (module_path, class_name, driver_type):
            raise ValueError("registered built-in driver identity does not match its source target")
        return

    candidates = metadata.entry_points(
        group=DRIVER_PLUGIN_ENTRY_POINT_GROUP,
        name=driver_name,
    )
    if len(candidates) != 1:
        raise ValueError("driver is not a unique installed kokonut.drivers entry point")
    entry_point = candidates[0]
    if (entry_point.module, entry_point.attr) != (module_path, class_name):
        raise ValueError("registered driver identity does not match its installed entry point")


def _load_driver_class(
    driver_name: str,
    module_path: str,
    class_name: str,
    driver_type: str,
) -> Any:
    """Resolve built-in or installed entry-point code without data imports."""
    builtin_target = BUILTIN_DRIVER_TARGETS.get(driver_name)
    if builtin_target is not None:
        if builtin_target != (module_path, class_name, driver_type):
            raise ValueError("registered built-in driver identity does not match its source target")
        module = importlib.import_module(builtin_target[0])
        driver_class = getattr(module, builtin_target[1], None)
    else:
        candidates = metadata.entry_points(
            group=DRIVER_PLUGIN_ENTRY_POINT_GROUP,
            name=driver_name,
        )
        if len(candidates) != 1:
            raise ValueError("driver is not a unique installed kokonut.drivers entry point")
        entry_point = candidates[0]
        if (entry_point.module, entry_point.attr) != (module_path, class_name):
            raise ValueError("registered driver identity does not match its installed entry point")
        driver_class = entry_point.load()

    required_methods = (
        "validate_config", "discover", "fetch", "transform", "health_check",
    )
    if (
        not isinstance(driver_class, type)
        or getattr(driver_class, "name", None) != driver_name
        or getattr(driver_class, "driver_type", None) != driver_type
        or any(not callable(getattr(driver_class, name, None)) for name in required_methods)
    ):
        raise ValueError("driver implementation does not satisfy the registered adapter contract")
    return driver_class


class DriverRegistry:
    """Central registry for data source drivers."""

    def __init__(self, conn=None):
        self._conn = conn
        self._cache: dict[str, Any] = {}  # driver_name -> driver_class

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
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

        _validate_driver_registration_target(
            driver_name, module_path, class_name, driver_type,
        )
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
            self._cache.pop(driver_name, None)
            logger.info("Registered driver: %s (id=%s)", driver_name, driver_id)
            return driver_id
        except Exception as exc:
            conn.rollback()
            logger.error(
                "Failed to register driver %s (%s)",
                driver_name,
                safe_exception_class(exc),
            )
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
            # Finish the metadata read before loading third-party Python code.
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        # Database rows select an installed driver name, never an import path.
        try:
            driver_class = _load_driver_class(
                driver_name, module_path, class_name, driver_type,
            )
            self._cache[driver_name] = driver_class
            logger.info("Loaded driver: %s v%s", driver_name, version)
            return driver_class
        except (ImportError, AttributeError, ValueError) as exc:
            logger.error(
                "Failed to load driver %s (%s)",
                driver_name,
                safe_exception_class(exc),
            )
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
        except Exception as exc:
            logger.error("Failed to list drivers (%s)", safe_exception_class(exc))
            return []

    def list_public_drivers_page(
        self,
        *,
        limit: int = PUBLIC_DRIVER_CATALOG_MAX_PAGE_SIZE,
        offset: int = 0,
    ) -> dict:
        """Return a bounded page of enabled catalog metadata only."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= PUBLIC_DRIVER_CATALOG_MAX_PAGE_SIZE
        ):
            raise ValueError("public driver page limit is outside the allowed range")
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or not 0 <= offset <= PUBLIC_DRIVER_CATALOG_MAX_OFFSET
        ):
            raise ValueError("public driver page offset is outside the allowed range")

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT driver_name, driver_version, driver_type
                    FROM driver_registry
                    WHERE is_enabled = TRUE
                    ORDER BY driver_type, driver_name
                    LIMIT %s OFFSET %s
                    """,
                    (limit + 1, offset),
                )
                rows = cur.fetchall()
            return {
                "drivers": [
                    {
                        "driver_name": row[0],
                        "driver_version": row[1],
                        "driver_type": row[2],
                    }
                    for row in rows[:limit]
                ],
                "limit": limit,
                "offset": offset,
                "has_more": (
                    len(rows) > limit
                    and offset + limit <= PUBLIC_DRIVER_CATALOG_MAX_OFFSET
                ),
            }
        except Exception as exc:
            logger.error("Failed to list public drivers (%s)", safe_exception_class(exc))
            return {"drivers": [], "limit": limit, "offset": offset, "has_more": False}

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
        except Exception as exc:
            logger.error(
                "Failed to list driver instances (%s)", safe_exception_class(exc)
            )
            return []

    def get_schedulable_instance(
        self, instance_id: str, location_id: str,
    ) -> dict | None:
        """Load one enabled, code-allowlisted sensor pull for the exact location."""
        import json

        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT di.id, di.instance_name, dr.driver_name, dr.module_path,
                       dr.class_name, dr.driver_type, di.config, di.location_id
                FROM driver_instance di
                JOIN driver_registry dr ON dr.id = di.driver_id
                WHERE di.id = %s
                  AND di.location_id = %s
                  AND di.is_enabled = TRUE
                  AND dr.is_enabled = TRUE
                  AND dr.driver_type = 'sensor'
                """,
                (instance_id, location_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        driver_name = str(row[2])
        registered_target = (str(row[3]), str(row[4]), str(row[5]))
        allowed_target = SCHEDULED_SENSOR_DRIVER_TARGETS.get(driver_name)
        if allowed_target is None:
            raise ValueError("sensor driver is not allowlisted for scheduled execution")
        if registered_target != allowed_target:
            raise ValueError(
                "scheduled sensor driver registry identity does not match the code allowlist"
            )
        config = row[6]
        if isinstance(config, str):
            config = json.loads(config)
        if not isinstance(config, dict):
            raise ValueError("sensor driver instance config must be a JSON object")
        return {
            "instance_id": str(row[0]),
            "instance_name": row[1],
            "driver_name": driver_name,
            # Use the static target after checking the registry copy. Never
            # import a module path sourced from PostgreSQL.
            "module_path": allowed_target[0],
            "class_name": allowed_target[1],
            "driver_type": allowed_target[2],
            "config": config,
            "location_id": str(row[7]),
        }

    @staticmethod
    def load_schedulable_sensor_driver(instance: dict) -> Any:
        """Load only a source-allowlisted scheduled sensor driver class."""
        driver_name = instance.get("driver_name")
        target = SCHEDULED_SENSOR_DRIVER_TARGETS.get(driver_name)
        if target is None or (
            instance.get("module_path"),
            instance.get("class_name"),
            instance.get("driver_type"),
        ) != target:
            raise ValueError("scheduled sensor driver identity is not code-allowlisted")

        module_path, class_name, driver_type = target
        module = importlib.import_module(module_path)
        driver_class = getattr(module, class_name, None)
        if (
            driver_class is None
            or getattr(driver_class, "name", None) != driver_name
            or getattr(driver_class, "driver_type", None) != driver_type
            or getattr(driver_class, "supports_scheduled_pull", False) is not True
            or not callable(getattr(driver_class, "fetch_scheduled", None))
        ):
            raise ValueError("code-allowlisted sensor driver does not satisfy its contract")
        return driver_class

    def create_instance(
        self,
        driver_name: str,
        instance_name: str,
        config: dict,
        location_id: str | None = None,
    ) -> str:
        """Create a new driver instance. Returns the instance ID."""
        import json

        if not isinstance(config, dict):
            raise ValueError("driver config must be a JSON object")
        try:
            config_json = json.dumps(config, allow_nan=False)
            if json.loads(config_json) != config:
                raise ValueError("driver config is not a JSON-native object")
        except (TypeError, ValueError):
            raise ValueError("driver config must contain only JSON values") from None

        # Validate before opening the persistence transaction. Loading resolves
        # only a source-owned built-in or the exact installed entry point.
        driver_class = self.load(driver_name)
        try:
            driver = driver_class(config=config)
            if driver.validate_config(config) is not True:
                raise ValueError("driver config validation returned false")
        except Exception as exc:
            logger.warning(
                "Rejected driver config for %s (%s)",
                driver_name,
                safe_exception_class(exc),
            )
            raise ValueError("driver config is invalid") from None

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM driver_registry
                    WHERE driver_name = %s AND is_enabled = TRUE
                    FOR SHARE
                    """,
                    (driver_name,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Driver not found or disabled: {driver_name}")
                driver_id = row[0]

                cur.execute(
                    """
                    INSERT INTO driver_instance (driver_id, instance_name, config, location_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (driver_id, instance_name, config_json, location_id),
                )
                inst_row = cur.fetchone()
                instance_id = str(inst_row[0]) if inst_row else None
            conn.commit()
            logger.info("Created instance: %s (driver=%s)", instance_name, driver_name)
            return instance_id
        except Exception as exc:
            conn.rollback()
            logger.error(
                "Failed to create driver instance %s (%s)",
                instance_name,
                safe_exception_class(exc),
            )
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
        except Exception as exc:
            conn.rollback()
            logger.error(
                "Failed to update driver instance status %s (%s)",
                instance_id,
                safe_exception_class(exc),
            )

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
                "message": (
                    "Failed to load or test driver "
                    f"({safe_exception_class(exc)})"
                ),
            }
