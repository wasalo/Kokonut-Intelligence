"""Build child environments with explicit worker-secret boundaries."""

from __future__ import annotations

import os
import re
from typing import Mapping, Sequence

_WORKER_SECRET_ENV = re.compile(
    r"^KOKONUT_([A-Z][A-Z0-9_]*)_(?:DATABASE_URL|WORKER_CREDENTIAL|RPC_ENDPOINTS?|OPENWEATHERMAP_API_KEY|GEE_SERVICE_ACCOUNT_KEY|COPERNICUS_EMAIL|COPERNICUS_PASSWORD|COPERNICUS_CLIENT_ID|COPERNICUS_CLIENT_SECRET)$"
)
_WORKER_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_ISOLATED_WORKER_KEY = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
ISOLATED_WORKER_KEY_ENV = "KOKONUT_ISOLATED_WORKER_KEY"
DENY_SHARED_DATABASE_ENV = "KOKONUT_DENY_SHARED_DATABASE"
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
    "services.analytics.carbon_credit_adjustment_worker": "credit_adjustment",
    "services.ingestion.weather_worker": "weather",
    "services.ingestion.weather_forecast_worker": "weather_forecast",
    "services.ingestion.climate_worker": "climate",
    "services.ingestion.market_data_worker": "market_data",
    # Existing persisted tasks still use this compatibility entrypoint. It
    # now delegates all writes to the same bounded market-data operations.
    "services.ingestion.market_data": "market_data",
    "services.ingestion.eas_worker": "eas_indexer",
    "services.ingestion.rpc_worker": "rpc_indexer",
    "services.ingestion.gnosis_worker": "gnosis_indexer",
    "services.ingestion.baal_worker": "baal_indexer",
    "services.ingestion.freshness_worker": "freshness",
    # Legacy CLI invocations now delegate --check to the bounded worker. Keep
    # old persisted schedules operational without exposing the worker secret to
    # any other module.
    "services.ingestion.data_freshness": "freshness",
    "services.ingestion.clickhouse_outbox": "clickhouse_outbox",
    "services.ingestion.sensor_anomaly_scan_worker": "sensor_anomaly",
    "services.ingestion.clickhouse_outbox_worker": "clickhouse_outbox",
    "services.ingestion.sensor_worker": "sensor_ingestion",
    "services.ingestion.remote_sensing_worker": "remote_sensing",
    # Persisted climate_data tasks remain supported as a safe dispatcher. The
    # compatibility entrypoint no longer opens the shared DB and forwards only
    # the climate worker identity to its signed child.
    "services.ingestion.climate_data": "climate",
}
# Keep the Kernel supervisor allowlist aligned with the scheduler dispatch map.
# `services.events --notification-process` selects its identity by operation,
# so it cannot be represented as a static module-to-worker entry above.
SCHEDULED_WORKER_KEYS = tuple(dict.fromkeys((
    *_SCHEDULED_MODULE_WORKERS.values(),
    "notification_delivery",
)))

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
    "CLICKHOUSE_PASSWORD",
    "ETH_RPC_URL",
    "OPTIMISM_RPC_URL",
    "BASE_RPC_URL",
    "ARBITRUM_RPC_URL",
    "CELO_RPC_URL",
    "CELO_ALFAJORES_RPC_URL",
    "GNOSIS_RPC_URL",
})
_ISOLATED_WORKER_PROVIDER_SECRETS = {
    # The outbox worker is the only isolated child that writes to ClickHouse.
    "clickhouse_outbox": frozenset({"CLICKHOUSE_PASSWORD"}),
}
_NOTIFICATION_PROVIDER_SECRETS = frozenset({
    "ALERT_WEBHOOK_URL",
    "DIRECTUS_ADMIN_TOKEN",
    "ALERT_SMTP_HOST",
    "ALERT_SMTP_PORT",
    "ALERT_SMTP_TLS_MODE",
    "ALERT_SMTP_USER",
    "ALERT_SMTP_PASSWORD",
    "ALERT_EMAIL_FROM",
    "ALERT_EMAIL_TO",
})

_EVENT_HANDLER_ISOLATION_FEATURES = {
    ("services.cache.events", "handle_metric_computed"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.cache.events", "handle_crisp_scored"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.cache.events", "handle_sensor_reading"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.cache.events", "handle_harvest_recorded"): "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION",
    ("services.events.handlers", "handle_stale_data"): "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE",
    ("services.events.handlers", "handle_alert_notification"): "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE",
}


def scheduled_module_worker_key(
    module_path: str, command_args: Sequence[str] | None = None
) -> str | None:
    """Return the one worker identity mapped to an exact scheduled module."""
    if module_path == "services.events" and command_args is not None:
        # Route notification delivery through its dedicated identity while
        # preserving the independent event-dispatch operation policy.
        if "--notification-process" in command_args:
            return "notification_delivery"
    return _SCHEDULED_MODULE_WORKERS.get(module_path)


def scheduled_module_worker_environment(
    module_path: str,
    command_args: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the least-privilege environment for one validated scheduled operation."""
    arguments = tuple(command_args or ())
    if module_path == "services.events":
        if "--process" in arguments:
            # The dispatcher needs its own database identity and the exact
            # handler identities that its source-controlled registry may spawn.
            return worker_subprocess_environment(
                allowed_worker_keys=event_dispatch_worker_keys(environ=environ),
                isolated_worker_key="event_dispatch",
                environ=environ,
            )
        if "--notification-process" in arguments:
            return worker_subprocess_environment(
                allowed_worker_keys=("notification_delivery",),
                isolated_worker_key="notification_delivery",
                environ=environ,
            )

    worker_key = scheduled_module_worker_key(module_path, arguments)
    return worker_subprocess_environment(
        allowed_worker_keys=(worker_key,) if worker_key is not None else (),
        isolated_database_credentials=worker_key is not None,
        environ=environ,
    )


def event_handler_worker_policy(
    module_path: str,
    function_name: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[tuple[str, ...], bool]:
    """Return the exact worker identity and isolation mode for one handler.

    Every registered worker-aware handler runs without the shared database
    identity. Feature-gated handlers receive their dedicated worker secret
    only after their corresponding feature is enabled; otherwise their
    isolated child can perform only its non-database behavior or fail closed.
    """
    key = (module_path, function_name)
    worker_keys = EVENT_HANDLER_WORKERS.get(key, ())
    if not worker_keys:
        # Event handler registrations are data, not an authority source. An
        # unregistered function gets no database identity and never inherits
        # the shared application connection.
        return (), True
    source = os.environ if environ is None else environ
    feature_variable = _EVENT_HANDLER_ISOLATION_FEATURES.get(key)
    enabled = bool(feature_variable and source.get(feature_variable, "").lower() == "true")
    return (worker_keys if feature_variable is None or enabled else (), True)


def event_dispatch_worker_keys(
    *, environ: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """Return dispatcher plus only the handler credentials enabled in this process."""
    source = os.environ if environ is None else environ
    keys = ["event_dispatch"]
    for module_path, function_name in EVENT_HANDLER_WORKERS:
        worker_keys, _isolated = event_handler_worker_policy(
            module_path, function_name, environ=source
        )
        keys.extend(worker_keys)
    return tuple(dict.fromkeys(keys))


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
    strip_shared_database_credentials: bool = False,
    isolated_worker_key: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy the environment while allowing only explicitly named worker secrets.

    Standard application settings are preserved. Variables shaped like
    ``KOKONUT_<WORKER>_DATABASE_URL`` or
    ``KOKONUT_<WORKER>_WORKER_CREDENTIAL`` are removed unless that worker key
    is explicitly allowed for the child. An empty allowlist is appropriate for
    APIs, scheduled commands, event handlers, and other general subprocesses.
    Isolated worker commands remove all shared PostgreSQL connection settings
    and receive an internal marker that lets import-time legacy helpers stay
    inert while the canonical shared connector fails closed. Supervisors may
    also set ``strip_shared_database_credentials`` for a child that must remain
    idle until its dedicated identity is provisioned. A dispatcher may carry
    its own key plus exact child-handler keys; the marker identifies its single
    database identity.
    """
    if isinstance(allowed_worker_keys, (str, bytes)):
        raise ValueError("worker keys must be provided as a sequence")
    if not isinstance(isolated_database_credentials, bool):
        raise ValueError("isolated_database_credentials must be a boolean")
    if not isinstance(strip_shared_database_credentials, bool):
        raise ValueError("strip_shared_database_credentials must be a boolean")
    allowed: set[str] = set()
    normalized_keys: list[str] = []
    for key in allowed_worker_keys:
        if not isinstance(key, str) or not _WORKER_KEY.fullmatch(key):
            raise ValueError("worker keys must be alphanumeric identifiers")
        allowed.add(key.upper())
        normalized_keys.append(key.lower())
    if isolated_database_credentials and len(set(normalized_keys)) != 1:
        raise ValueError("isolated database workers require exactly one allowed worker key")
    if isolated_worker_key is not None:
        if not isinstance(isolated_worker_key, str) or not _ISOLATED_WORKER_KEY.fullmatch(
            isolated_worker_key
        ):
            raise ValueError("isolated_worker_key must be a lowercase worker identifier")
        if isolated_database_credentials:
            raise ValueError("use either isolated_database_credentials or isolated_worker_key")
        if isolated_worker_key not in normalized_keys:
            raise ValueError("isolated worker key must be present in the allowed worker keys")

    isolated = (
        isolated_database_credentials
        or strip_shared_database_credentials
        or isolated_worker_key is not None
    )
    marker = isolated_worker_key
    if isolated_database_credentials:
        marker = normalized_keys[0]
    allowed_provider_secrets = frozenset(
        name
        for worker_key in normalized_keys
        for name in _ISOLATED_WORKER_PROVIDER_SECRETS.get(worker_key, ())
    )

    source = os.environ if environ is None else environ
    enqueue_only = "event_dispatch" in allowed or "notification_enqueue" in allowed
    child_environment: dict[str, str] = {}
    for name, value in source.items():
        if name in {
            ISOLATED_WORKER_KEY_ENV,
            DENY_SHARED_DATABASE_ENV,
            "KOKONUT_WORKER_PROGRESS_NAME",
        }:
            continue
        if enqueue_only and name in _NOTIFICATION_PROVIDER_SECRETS:
            continue
        if isolated and name in _SHARED_DATABASE_ENV:
            continue
        if (
            isolated
            and name in _GLOBAL_PROVIDER_SECRETS
            and name not in allowed_provider_secrets
        ):
            continue
        if name in {"KOKONUT_OPERATOR_AUTH_USER", "KOKONUT_OPERATOR_AUTH_PASSWORD"}:
            if not isolated and "OPERATOR_AUTH" in allowed:
                child_environment[name] = value
            continue
        if name == "KOKONUT_CLICKHOUSE_OUTBOX_OPERATOR_PASSWORD":
            if not isolated and "CLICKHOUSE_OUTBOX_OPERATOR" in allowed:
                child_environment[name] = value
            continue
        match = _WORKER_SECRET_ENV.fullmatch(name)
        if match is None or match.group(1) in allowed:
            child_environment[name] = value
    if enqueue_only:
        webhook = bool(source.get("ALERT_WEBHOOK_URL", "").strip()) or (
            source.get("KOKONUT_NOTIFICATION_WEBHOOK_CONFIGURED", "").strip().lower()
            == "true"
        )
        directus_enabled = source.get("KOKONUT_FEATURE_DIRECTUS", "true").strip().lower() == "true"
        directus_token = bool(source.get("DIRECTUS_ADMIN_TOKEN", "").strip()) or (
            source.get("KOKONUT_NOTIFICATION_DIRECTUS_CONFIGURED", "").strip().lower()
            == "true"
        )
        email_configured = bool(
            source.get("ALERT_SMTP_HOST", "").strip()
            and source.get("ALERT_EMAIL_TO", "").strip()
        ) or (
            source.get("KOKONUT_NOTIFICATION_EMAIL_CONFIGURED", "").strip().lower()
            == "true"
        )
        child_environment.update({
            "KOKONUT_NOTIFICATION_WEBHOOK_CONFIGURED": str(webhook).lower(),
            "KOKONUT_NOTIFICATION_DIRECTUS_CONFIGURED": str(
                directus_enabled and bool(directus_token)
            ).lower(),
            "KOKONUT_NOTIFICATION_EMAIL_CONFIGURED": str(email_configured).lower(),
        })
    if isolated and marker is not None:
        child_environment[ISOLATED_WORKER_KEY_ENV] = marker
    if isolated:
        # Stripping inherited PG variables is insufficient: legacy modules may
        # reload them from a repository .env during import. This independent
        # deny marker keeps the shared connector inert even when no worker
        # identity is allowed (for example, an unknown or disabled handler).
        child_environment[DENY_SHARED_DATABASE_ENV] = "true"
    return child_environment
