"""Allowlisted Python entry points for database-driven workers."""

from __future__ import annotations


ALLOWED_EVENT_HANDLERS = frozenset({
    ("services.ingestion.anomaly_detector", "handle_sensor_reading"),
    ("services.events.handlers", "handle_stale_data"),
    ("services.cache.events", "handle_metric_computed"),
    ("services.cache.events", "handle_crisp_scored"),
    ("services.events.handlers", "handle_alert_notification"),
})

ALLOWED_SCHEDULED_MODULES = frozenset({
    "services.ingestion.weather",
    "services.ingestion.market_data",
    "services.ingestion.eas_indexer",
    "services.ingestion.rpc_indexer",
    "services.ingestion.sensor_ingester",
    "services.ingestion.gnosis_indexer",
    "services.ingestion.anomaly_detector",
    "services.metrics",
    "services.ingestion.data_freshness",
    "services.export.dataset_refresh",
    "services.ingestion.climate_data",
    "services.events",
})


def validate_event_handler(module_path: str, function_name: str) -> None:
    if (module_path, function_name) not in ALLOWED_EVENT_HANDLERS:
        raise ValueError(f"Event handler is not allowlisted: {module_path}.{function_name}")


def validate_scheduled_module(module_path: str) -> None:
    if module_path not in ALLOWED_SCHEDULED_MODULES:
        raise ValueError(f"Scheduled module is not allowlisted: {module_path}")
