"""Feature flags — controls which optional services are enabled.

Feature flags are environment-variable driven. PostgreSQL is always enabled.
Directus remains critical when selected until native API parity is implemented.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from services.core.providers import ProviderSettings

_providers = ProviderSettings.from_environment()

FEATURES: dict[str, dict[str, Any]] = {
    # ── Core (always enabled) ──────────────────────────────────────
    "database": {
        "enabled": True,
        "critical": True,
        "category": "core",
        "health_check": "pg_isready",
        "description": "PostgreSQL database",
    },
    "directus": {
        "enabled": _providers.directus,
        "critical": _providers.directus,
        "category": "core",
        "health_check": "curl localhost:8055/server/ping",
        "description": "Directus API and admin UI",
    },
    "clickhouse": {
        "enabled": _providers.clickhouse,
        "critical": False,
        "category": "core",
        "health_check": "clickhouse-client query 'SELECT 1'",
        "description": "ClickHouse analytical store",
    },
    # ── Optional services ──────────────────────────────────────────
    "grpc": {
        "enabled": _providers.grpc,
        "critical": False,
        "category": "api",
        "port": 50051,
        "description": "gRPC API server",
    },
    "metabase": {
        "enabled": _providers.metabase,
        "critical": False,
        "category": "analytics",
        "port": 3000,
        "description": "Metabase analytics dashboards",
    },
    "mqtt": {
        "enabled": _providers.mqtt,
        "critical": False,
        "category": "iot",
        "port": 1883,
        "description": "MQTT broker for IoT sensors",
    },
    "prefect": {
        "enabled": _providers.prefect,
        "critical": False,
        "category": "orchestration",
        "description": "Prefect workflow orchestration",
    },
    "legacy_dataset_sql": {
        "enabled": _providers.legacy_dataset_sql,
        "critical": False,
        "category": "analytics",
        "description": "Legacy stored-SQL dashboard dataset refresh",
    },
    "agents": {
        "enabled": os.getenv("KOKONUT_FEATURE_AGENTS", "true").lower() == "true",
        "critical": False,
        "category": "intelligence",
        "description": "AI/LLM agent services",
    },
    "crisp": {
        "enabled": os.getenv("KOKONUT_FEATURE_CRISP", "true").lower() == "true",
        "critical": False,
        "category": "analytics",
        "description": "CRISP risk scoring engine",
    },
    "reports": {
        "enabled": os.getenv("KOKONUT_FEATURE_REPORTS", "true").lower() == "true",
        "critical": False,
        "category": "export",
        "description": "Report generation engine",
    },
    "scheduler": {
        "enabled": os.getenv("KOKONUT_FEATURE_SCHEDULER", "true").lower() == "true",
        "critical": False,
        "category": "core",
        "description": "Database-driven task scheduler",
    },
    "event_bus": {
        "enabled": os.getenv("KOKONUT_FEATURE_EVENT_BUS", "true").lower() == "true",
        "critical": False,
        "category": "core",
        "description": "Reactive event bus",
    },
    "notification_delivery": {
        "enabled": os.getenv(
            "KOKONUT_FEATURE_NOTIFICATION_DELIVERY",
            os.getenv("KOKONUT_FEATURE_EVENT_BUS", "true"),
        ).lower() == "true",
        "critical": False,
        "category": "communications",
        "description": "Durable outbox delivery through configured notification providers",
    },
    "isolated_notification_enqueue": {
        "enabled": os.getenv(
            "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE", "false"
        ).lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a dedicated database login and bounded function for event notification enqueue",
    },
    "event_retention_cleanup": {
        "enabled": os.getenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", "false").lower() == "true",
        "critical": False,
        "category": "governance",
        "description": "Destructive event cleanup; requires approved retention and implemented legal-hold enforcement",
    },
    "signed_cache_invalidation": {
        "enabled": os.getenv("KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION", "false").lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a dedicated worker login and signed location grant for EventBus cache invalidation",
    },
    "signed_noi_snapshot_worker": {
        "enabled": os.getenv("KOKONUT_FEATURE_SIGNED_NOI_SNAPSHOT_WORKER", "false").lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a worker-specific credential, signed location grant, and bounded function for NOI snapshot reconciliation",
    },
    "signed_weather_forecast_worker": {
        "enabled": os.getenv("KOKONUT_FEATURE_SIGNED_WEATHER_FORECAST_WORKER", "false").lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a worker-specific credential, signed location grant, and bounded functions for weather forecast ingestion",
    },
    "signed_weather_worker": {
        "enabled": os.getenv("KOKONUT_FEATURE_SIGNED_WEATHER_WORKER", "false").lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a worker-specific provider key, database credential, signed location grant, and bounded functions for current-weather ingestion",
    },
    "signed_climate_worker": {
        "enabled": os.getenv("KOKONUT_FEATURE_SIGNED_CLIMATE_WORKER", "false").lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a dedicated GEE key path, database credential, signed location grant, and bounded functions for climate ingestion",
    },
    "isolated_market_data_worker": {
        "enabled": os.getenv(
            "KOKONUT_FEATURE_ISOLATED_MARKET_DATA_WORKER", "false"
        ).lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a dedicated database login and bounded function for global World Bank price ingestion",
    },
    "signed_sensor_ingestion_worker": {
        "enabled": os.getenv("KOKONUT_FEATURE_SIGNED_SENSOR_INGESTION_WORKER", "false").lower() == "true",
        "critical": False,
        "category": "security",
        "description": "Use a dedicated database login, signed location grant, and bounded functions for scheduled CSV sensor ingestion",
    },
}


def is_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled."""
    feature = FEATURES.get(feature_name)
    if feature is None:
        return False
    return feature["enabled"]


def get_feature(feature_name: str) -> Optional[dict]:
    """Get full feature definition."""
    return FEATURES.get(feature_name)


def list_features(category: str | None = None) -> list[dict]:
    """List all features, optionally filtered by category."""
    features = []
    for name, config in FEATURES.items():
        if category and config.get("category") != category:
            continue
        features.append({"name": name, **config})
    return features


def require_feature(feature_name: str) -> None:
    """Raise RuntimeError if a feature is not enabled."""
    if not is_enabled(feature_name):
        raise RuntimeError(
            f"Required feature '{feature_name}' is not enabled. "
            f"Set KOKONUT_FEATURE_{feature_name.upper()}=true to enable it."
        )


def enabled_features() -> list[str]:
    """Return list of enabled feature names."""
    return [name for name, config in FEATURES.items() if config["enabled"]]


def critical_features() -> list[str]:
    """Return list of critical feature names."""
    return [name for name, config in FEATURES.items() if config["critical"]]
