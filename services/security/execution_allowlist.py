"""Allowlisted Python entry points for database-driven workers."""

from __future__ import annotations

ALLOWED_EVENT_HANDLERS = frozenset(
    {
        ("services.ingestion.anomaly_detector", "handle_sensor_reading"),
        ("services.events.handlers", "handle_stale_data"),
        ("services.cache.events", "handle_metric_computed"),
        ("services.cache.events", "handle_crisp_scored"),
        ("services.cache.events", "handle_sensor_reading"),
        ("services.cache.events", "handle_harvest_recorded"),
        ("services.events.handlers", "handle_alert_notification"),
    }
)

ALLOWED_SCHEDULED_MODULES = frozenset(
    {
        "services.analytics.carbon_credit_adjustment_check",
        "services.analytics.carbon_credit_adjustment_worker",
        # Preserve the legacy module for persisted tasks until schedule owners
        # reconcile them; new Kernel plans use the signed worker module.
        "services.ingestion.weather",
        "services.ingestion.weather_worker",
        # Keep the pre-isolation module available for persisted tasks until
        # active schedules have been reconciled. New Kernel plans use the
        # signed worker module below.
        "services.ingestion.weather_forecast",
        "services.ingestion.weather_forecast_worker",
        "services.ingestion.market_data",
        "services.ingestion.market_data_worker",
        "services.ingestion.eas_indexer",
        "services.ingestion.eas_worker",
        "services.ingestion.rpc_indexer",
        "services.ingestion.rpc_worker",
        "services.ingestion.sensor_ingester",
        "services.ingestion.sensor_worker",
        "services.ingestion.gnosis_indexer",
        "services.ingestion.gnosis_worker",
        "services.ingestion.baal_indexer",
        "services.ingestion.baal_worker",
        "services.ingestion.anomaly_detector",
        "services.metrics",
        "services.metrics.noi_snapshot_worker",
        "services.ingestion.data_freshness",
        "services.export.dataset_refresh",
        "services.ingestion.climate_data",
        # New Kernel schedules use a signed location-scoped worker. Keep the
        # interactive/shared-identity CLI contract for manual compatibility.
        "services.ingestion.climate_worker",
        "services.ingestion.remote_sensing_fetcher",
        "services.ingestion.remote_sensing_worker",
        "services.ingestion.clickhouse_outbox",
        "services.events",
    }
)


def validate_event_handler(module_path: str, function_name: str) -> None:
    if (module_path, function_name) not in ALLOWED_EVENT_HANDLERS:
        raise ValueError(f"Event handler is not allowlisted: {module_path}.{function_name}")


def validate_scheduled_module(module_path: str) -> None:
    if module_path not in ALLOWED_SCHEDULED_MODULES:
        raise ValueError(f"Scheduled module is not allowlisted: {module_path}")
