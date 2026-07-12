"""Feature flags — controls which optional services are enabled.

Feature flags are environment-variable driven. Critical features
(database, directus) are always enabled. Optional features can be
toggled via KOKONUT_FEATURE_* env vars.
"""

from __future__ import annotations

import os
from typing import Any, Optional


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
        "enabled": True,
        "critical": True,
        "category": "core",
        "health_check": "curl localhost:8055/server/ping",
        "description": "Directus API and admin UI",
    },
    "clickhouse": {
        "enabled": True,
        "critical": False,
        "category": "core",
        "health_check": "clickhouse-client query 'SELECT 1'",
        "description": "ClickHouse analytical store",
    },

    # ── Optional services ──────────────────────────────────────────
    "grpc": {
        "enabled": os.getenv("KOKONUT_FEATURE_GRPC", "true").lower() == "true",
        "critical": False,
        "category": "api",
        "port": 50051,
        "description": "gRPC API server",
    },
    "metabase": {
        "enabled": os.getenv("KOKONUT_FEATURE_METABASE", "true").lower() == "true",
        "critical": False,
        "category": "analytics",
        "port": 3000,
        "description": "Metabase analytics dashboards",
    },
    "mqtt": {
        "enabled": os.getenv("KOKONUT_FEATURE_MQTT", "true").lower() == "true",
        "critical": False,
        "category": "iot",
        "port": 1883,
        "description": "MQTT broker for IoT sensors",
    },
    "prefect": {
        "enabled": os.getenv("KOKONUT_FEATURE_PREFECT", "false").lower() == "true",
        "critical": False,
        "category": "orchestration",
        "description": "Prefect workflow orchestration",
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
