"""Dedicated database connections for tenant-scoped worker execution.

Unlike :mod:`services.common.database`, this module deliberately does not
import the shared ``PG_*`` configuration or load dotenv files. A worker must
receive its own DSN from the deployment secret provider; missing configuration
never falls back to the application or control-plane database identity.
"""

from __future__ import annotations

import os
import re
from typing import Mapping

import psycopg2

_WORKER_KEY = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
_WORKER_LOGIN = "kokonut_worker_login"


class WorkerDatabaseConfigurationError(RuntimeError):
    """Raised when a dedicated worker connection is missing or unsafe."""


def get_worker_db(
    worker_key: str,
    *,
    connect_timeout: int = 8,
    environ: Mapping[str, str] | None = None,
):
    """Connect using ``KOKONUT_<WORKER>_DATABASE_URL`` and verify the login.

    For example, ``get_worker_db("sensor_anomaly")`` reads only
    ``KOKONUT_SENSOR_ANOMALY_DATABASE_URL``. It never consults ``PG_USER``,
    ``PG_PASSWORD``, ``POSTGRES_PASSWORD``, or the shared application's
    connection factory. The DSN value is not included in errors or logs.

    The returned psycopg2 connection remains in a non-autocommit transaction
    so signed tenant context and bounded worker operations can share one
    transaction. The caller owns commit/rollback and connection cleanup.
    """
    if not isinstance(worker_key, str) or not _WORKER_KEY.fullmatch(worker_key):
        raise ValueError("worker_key must be a lowercase identifier")
    if isinstance(connect_timeout, bool) or not isinstance(connect_timeout, int) or connect_timeout <= 0:
        raise ValueError("connect_timeout must be a positive integer")

    source = os.environ if environ is None else environ
    env_name = f"KOKONUT_{worker_key.upper()}_DATABASE_URL"
    dsn = source.get(env_name, "")
    if not isinstance(dsn, str) or not dsn.strip():
        raise WorkerDatabaseConfigurationError(
            f"{env_name} is required for isolated worker database access"
        )

    connection = psycopg2.connect(
        dsn,
        connect_timeout=connect_timeout,
        application_name=f"kokonut-worker-{worker_key}",
    )
    try:
        if connection.autocommit:
            raise WorkerDatabaseConfigurationError(
                "worker database connections must use transactions"
            )
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            row = cursor.fetchone()
        if row is None or row[0] != _WORKER_LOGIN:
            raise WorkerDatabaseConfigurationError(
                f"worker database login must be {_WORKER_LOGIN}"
            )
    except Exception:
        connection.close()
        raise
    return connection
