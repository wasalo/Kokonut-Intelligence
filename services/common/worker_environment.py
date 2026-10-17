"""Build child environments with explicit worker-secret boundaries."""

from __future__ import annotations

import os
import re
from typing import Mapping, Sequence

_WORKER_SECRET_ENV = re.compile(
    r"^KOKONUT_([A-Z][A-Z0-9_]*)_(?:DATABASE_URL|WORKER_CREDENTIAL|OPENWEATHERMAP_API_KEY|GEE_SERVICE_ACCOUNT_KEY|COPERNICUS_EMAIL|COPERNICUS_PASSWORD|COPERNICUS_CLIENT_ID|COPERNICUS_CLIENT_SECRET)$"
)
_WORKER_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SHARED_DATABASE_ENV = frozenset({
    "DATABASE_URL",
    "PG_DB",
    "PG_HOST",
    "PG_PASSWORD",
    "PG_PORT",
    "PG_USER",
    "POSTGRES_PASSWORD",
    "KOKONUT_DB_ADMIN_PASSWORD",
    "KOKONUT_DB_ADMIN_USER",
    "KOKONUT_OPERATOR_AUTH_PASSWORD",
    "KOKONUT_OPERATOR_AUTH_USER",
    "KOKONUT_RUNTIME_PASSWORD",
    "KOKONUT_RUNTIME_USER",
})

# A scheduled operation receives worker credentials only when its exact
# allowlisted module has an explicit entry here. The scheduler process itself
# is separately configured to hold these operation secrets.
_SCHEDULED_MODULE_WORKERS = {
    "services.metrics.noi_snapshot_worker": "noi_snapshot",
    "services.ingestion.weather_worker": "weather",
    "services.ingestion.weather_forecast_worker": "weather_forecast",
    "services.ingestion.climate_worker": "climate",
    "services.ingestion.market_data_worker": "market_data",
    "services.ingestion.sensor_worker": "sensor_ingestion",
    "services.ingestion.remote_sensing_worker": "remote_sensing",
}
# Keep the Kernel supervisor allowlist aligned with the scheduler dispatch map.
SCHEDULED_WORKER_KEYS = tuple(dict.fromkeys(_SCHEDULED_MODULE_WORKERS.values()))

_GLOBAL_PROVIDER_SECRETS = frozenset({
    "GEE_SERVICE_ACCOUNT_KEY",
    "COPERNICUS_EMAIL",
    "COPERNICUS_PASSWORD",
    "COPERNICUS_CLIENT_ID",
    "COPERNICUS_CLIENT_SECRET",
})


def scheduled_module_worker_key(module_path: str) -> str | None:
    """Return the one worker identity mapped to an exact scheduled module."""
    return _SCHEDULED_MODULE_WORKERS.get(module_path)


def worker_subprocess_environment(
    *,
    allowed_worker_keys: Sequence[str] = (),
    isolated_database_credentials: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy the environment while allowing only explicitly named worker secrets.

    Standard application settings are preserved. Variables shaped like
    ``KOKONUT_<WORKER>_DATABASE_URL`` or
    ``KOKONUT_<WORKER>_WORKER_CREDENTIAL`` are removed unless that worker key
    is explicitly allowed for the child. An empty allowlist is appropriate for
    APIs, scheduled commands, event handlers, and other general subprocesses.
    Isolated worker commands can also remove all shared PostgreSQL connection
    settings so their dedicated DSN is the only database identity available.
    """
    if isinstance(allowed_worker_keys, (str, bytes)):
        raise ValueError("worker keys must be provided as a sequence")
    if not isinstance(isolated_database_credentials, bool):
        raise ValueError("isolated_database_credentials must be a boolean")
    allowed: set[str] = set()
    for key in allowed_worker_keys:
        if not isinstance(key, str) or not _WORKER_KEY.fullmatch(key):
            raise ValueError("worker keys must be alphanumeric identifiers")
        allowed.add(key.upper())

    source = os.environ if environ is None else environ
    child_environment: dict[str, str] = {}
    for name, value in source.items():
        if isolated_database_credentials and name in _SHARED_DATABASE_ENV:
            continue
        if isolated_database_credentials and name in _GLOBAL_PROVIDER_SECRETS:
            continue
        match = _WORKER_SECRET_ENV.fullmatch(name)
        if match is None or match.group(1) in allowed:
            child_environment[name] = value
    return child_environment
