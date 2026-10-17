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
_WORKER_LOGINS = {
    "notification_enqueue": "kokonut_notification_enqueue_login",
    "market_data": "kokonut_market_data_login",
}
_DEFAULT_WORKER_LOGIN = "kokonut_worker_login"
_WORKER_CREDENTIAL_MIN_BYTES = 32
_WORKER_CREDENTIAL_MAX_BYTES = 4096


class WorkerDatabaseConfigurationError(RuntimeError):
    """Raised when a dedicated worker connection is missing or unsafe."""


def _worker_key(worker_key: str) -> str:
    if not isinstance(worker_key, str) or not _WORKER_KEY.fullmatch(worker_key):
        raise ValueError("worker_key must be a lowercase identifier")
    return worker_key


def get_worker_credential(
    worker_key: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Read a high-entropy worker credential from its named secret variable.

    The value is opaque and is never normalized, logged, or included in
    configuration errors. Call this only inside the isolated worker process;
    do not add worker credentials to a shared dispatcher environment.
    """
    key = _worker_key(worker_key)
    source = os.environ if environ is None else environ
    env_name = f"KOKONUT_{key.upper()}_WORKER_CREDENTIAL"
    credential = source.get(env_name, "")
    if not isinstance(credential, str):
        credential = ""
    try:
        credential_bytes = credential.encode("utf-8")
    except UnicodeEncodeError:
        raise WorkerDatabaseConfigurationError(
            f"{env_name} must contain valid UTF-8 text"
        ) from None
    if not _WORKER_CREDENTIAL_MIN_BYTES <= len(credential_bytes) <= _WORKER_CREDENTIAL_MAX_BYTES:
        raise WorkerDatabaseConfigurationError(
            f"{env_name} must contain 32 to 4096 UTF-8 bytes"
        )
    return credential


def get_worker_db(
    worker_key: str,
    *,
    connect_timeout: int = 8,
    environ: Mapping[str, str] | None = None,
):
    """Connect using ``KOKONUT_<WORKER>_DATABASE_URL`` and verify the login.

    For example, ``get_worker_db("sensor_anomaly")`` reads only
    ``KOKONUT_SENSOR_ANOMALY_DATABASE_URL`` and verifies the shared tenant
    worker login. ``notification_enqueue`` verifies its separate login.
    Neither path consults ``PG_USER``, ``PG_PASSWORD``, ``POSTGRES_PASSWORD``,
    or the shared application's connection factory. The DSN value is not
    included in errors or logs.

    The returned psycopg2 connection remains in a non-autocommit transaction
    so signed tenant context and bounded worker operations can share one
    transaction. The caller owns commit/rollback and connection cleanup.
    """
    worker_key = _worker_key(worker_key)
    if isinstance(connect_timeout, bool) or not isinstance(connect_timeout, int) or connect_timeout <= 0:
        raise ValueError("connect_timeout must be a positive integer")

    source = os.environ if environ is None else environ
    env_name = f"KOKONUT_{worker_key.upper()}_DATABASE_URL"
    expected_login = _WORKER_LOGINS.get(worker_key, _DEFAULT_WORKER_LOGIN)
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
        if row is None or row[0] != expected_login:
            raise WorkerDatabaseConfigurationError(
                f"worker database login must be {expected_login}"
            )
    except Exception:
        connection.close()
        raise
    return connection
