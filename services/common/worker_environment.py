"""Build child environments with explicit worker-secret boundaries."""

from __future__ import annotations

import os
import re
from typing import Mapping, Sequence

_WORKER_SECRET_ENV = re.compile(
    r"^KOKONUT_([A-Z][A-Z0-9_]*)_(?:DATABASE_URL|WORKER_CREDENTIAL|OPENWEATHERMAP_API_KEY|GEE_SERVICE_ACCOUNT_KEY|COPERNICUS_EMAIL|COPERNICUS_PASSWORD|COPERNICUS_CLIENT_ID|COPERNICUS_CLIENT_SECRET)$"
)
_WORKER_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_ISOLATED_WORKER_KEY = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
ISOLATED_WORKER_KEY_ENV = "KOKONUT_ISOLATED_WORKER_KEY"
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
    "services.ingestion.eas_worker": "eas_indexer",
    "services.ingestion.sensor_worker": "sensor_ingestion",
    "services.ingestion.remote_sensing_worker": "remote_sensing",
}
# Keep the Kernel supervisor allowlist aligned with the scheduler dispatch map.
SCHEDULED_WORKER_KEYS = tuple(dict.fromkeys(_SCHEDULED_MODULE_WORKERS.values()))

_EVENT_HANDLER_WORKERS = {
    ("services.ingestion.anomaly_detector", "handle_sensor_reading"): ("sensor_anomaly",),
    ("services.cache.events", "handle_metric_computed"): ("cache_invalidation",),
    ("services.cache.events", "handle_crisp_scored"): ("cache_invalidation",),
    ("services.cache.events", "handle_sensor_reading"): ("cache_invalidation",),
    ("services.cache.events", "handle_harvest_recorded"): ("cache_invalidation",),
    ("services.events.handlers", "handle_stale_data"): ("notification_enqueue",),
    ("services.events.handlers", "handle_alert_notification"): ("notification_enqueue",),
}
EVENT_HANDLER_WORKERS = _EVENT_HANDLER_WORKERS
EVENT_HANDLER_WORKER_KEYS = tuple(
    dict.fromkeys(worker for worker_keys in EVENT_HANDLER_WORKERS.values() for worker in worker_keys)
)

_GLOBAL_PROVIDER_SECRETS = frozenset({
    "GEE_SERVICE_ACCOUNT_KEY",
    "COPERNICUS_EMAIL",
    "COPERNICUS_PASSWORD",
    "COPERNICUS_CLIENT_ID",
    "COPERNICUS_CLIENT_SECRET",
})

_EVENT_HANDLER_ISOLATION_FEATURES = {
    ("services.cache.events", "handle_metric_computed"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.cache.events", "handle_crisp_scored"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.cache.events", "handle_sensor_reading"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.cache.events", "handle_harvest_recorded"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.events.handlers", "handle_stale_data"): "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE",
    ("services.events.handlers", "handle_alert_notification"): "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE",
}


def scheduled_module_worker_key(module_path: str) -> str | None:
    """Return the one worker identity mapped to an exact scheduled module."""
    return _SCHEDULED_MODULE_WORKERS.get(module_path)


def event_handler_worker_policy(
    module_path: str,
    function_name: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[tuple[str, ...], bool]:
    """Return the exact worker identity and isolation mode for one handler.

    Feature-gated handlers retain their legacy application database path while
    isolated execution is disabled. Sensor anomaly handling always requires
    its dedicated worker identity.
    """
    key = (module_path, function_name)
    worker_keys = EVENT_HANDLER_WORKERS.get(key, ())
    if not worker_keys:
        return (), False
    source = os.environ if environ is None else environ
    feature_variable = _EVENT_HANDLER_ISOLATION_FEATURES.get(key)
    enabled = bool(feature_variable and source.get(feature_variable, "").lower() == "true")
    return (worker_keys, True) if feature_variable is None or enabled else ((), False)


def isolated_worker_key(environ: Mapping[str, str] | None = None) -> str | None:
    """Read and validate the internal marker used by isolated worker children."""
    source = os.environ if environ is None else environ
    value = source.get(ISOLATED_WORKER_KEY_ENV)
    if value is None:
        return None
    if not isinstance(value, str) or not _ISOLATED_WORKER_KEY.fullmatch(value):
        raise ValueError(f"{ISOLATED_WORKER_KEY_ENV} must be a lowercase worker identifier")
    return value


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
    Isolated worker commands require one exact worker key, remove all shared
    PostgreSQL connection settings, and receive an internal marker that lets
    import-time legacy helpers stay inert while the canonical shared connector
    fails closed.
    """
    if isinstance(allowed_worker_keys, (str, bytes)):
        raise ValueError("worker keys must be provided as a sequence")
    if not isinstance(isolated_database_credentials, bool):
        raise ValueError("isolated_database_credentials must be a boolean")
    allowed: set[str] = set()
    normalized_keys: list[str] = []
    for key in allowed_worker_keys:
        if not isinstance(key, str) or not _WORKER_KEY.fullmatch(key):
            raise ValueError("worker keys must be alphanumeric identifiers")
        allowed.add(key.upper())
        normalized_keys.append(key.lower())
    if isolated_database_credentials and len(set(normalized_keys)) != 1:
        raise ValueError("isolated database workers require exactly one allowed worker key")

    source = os.environ if environ is None else environ
    child_environment: dict[str, str] = {}
    for name, value in source.items():
        if name == ISOLATED_WORKER_KEY_ENV:
            continue
        if isolated_database_credentials and name in _SHARED_DATABASE_ENV:
            continue
        if isolated_database_credentials and name in _GLOBAL_PROVIDER_SECRETS:
            continue
        match = _WORKER_SECRET_ENV.fullmatch(name)
        if match is None or match.group(1) in allowed:
            child_environment[name] = value
    if isolated_database_credentials:
        child_environment[ISOLATED_WORKER_KEY_ENV] = normalized_keys[0]
    return child_environment
