"""Main pipeline definitions with dependency chains.

Defines the orchestration DAG for all Kokonut Intelligence workflows.
"""

from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta


@flow(name="ingestion-pipeline", retries=1)
def ingestion_pipeline():
    """Run all ingestion tasks in parallel, then dependent tasks."""
    from .weather import weather_ingestion_flow
    from .sensors import sensor_ingestion_flow
    from .market_data import market_data_flow
    from .eas_indexer import eas_indexing_flow
    from .rpc_indexer import rpc_indexing_flow
    from .gnosis_indexer import gnosis_indexing_flow

    # Ingestion tasks run in parallel (no dependencies)
    weather_future = weather_ingestion_flow.submit()
    sensor_future = sensor_ingestion_flow.submit()
    market_future = market_data_flow.submit()
    eas_future = eas_indexing_flow.submit()
    rpc_future = rpc_indexing_flow.submit()
    gnosis_future = gnosis_indexing_flow.submit()

    # Wait for all ingestion
    weather_future.result()
    sensor_future.result()
    market_future.result()
    eas_future.result()
    rpc_future.result()
    gnosis_future.result()

    return {"status": "success", "ingestion": "complete"}


@flow(name="monitoring-pipeline", retries=1)
def monitoring_pipeline():
    """Run anomaly detection and data freshness checks."""
    from .anomaly_detection import anomaly_detection_flow
    from .freshness import freshness_check_flow

    anomaly_future = anomaly_detection_flow.submit()
    freshness_future = freshness_check_flow.submit()

    anomaly_future.result()
    freshness_future.result()

    return {"status": "success", "monitoring": "complete"}


@flow(name="analytics-pipeline", retries=1)
def analytics_pipeline():
    """Run metrics computation, then dashboard refresh."""
    from .metrics import metrics_computation_flow
    from .dashboards import dashboard_refresh_flow
    from .credit_adjustment import credit_adjustment_flow

    # Metrics first
    metrics_future = metrics_computation_flow.submit()
    metrics_future.result()

    # Then dashboards and credit adjustment (parallel)
    dashboard_future = dashboard_refresh_flow.submit()
    credit_future = credit_adjustment_flow.submit()

    dashboard_future.result()
    credit_future.result()

    return {"status": "success", "analytics": "complete"}


@flow(name="full-pipeline", retries=1)
def full_pipeline():
    """Full pipeline: ingestion -> monitoring -> analytics."""
    from .monitoring_pipeline import monitoring_pipeline
    from .analytics_pipeline import analytics_pipeline

    # Ingestion
    ingestion_pipeline()

    # Monitoring (after ingestion)
    monitoring_pipeline()

    # Analytics (after monitoring)
    analytics_pipeline()

    # Remote sensing (independent, longer-running)
    from .remote_sensing import remote_sensing_flow
    remote_sensing_flow()

    return {"status": "success", "pipeline": "complete"}


@flow(name="scheduled-hourly", retries=1)
def scheduled_hourly():
    """Hourly tasks: sensor ingestion, anomaly detection, freshness check."""
    from .sensors import sensor_ingestion_flow
    from .anomaly_detection import anomaly_detection_flow
    from .freshness import freshness_check_flow

    sensor_ingestion_flow()
    anomaly_detection_flow()
    freshness_check_flow()


@flow(name="scheduled-every-6h", retries=1)
def scheduled_every_6h():
    """Every 6 hours: weather, dashboard refresh, remote sensing."""
    from .weather import weather_ingestion_flow
    from .dashboards import dashboard_refresh_flow
    from .remote_sensing import remote_sensing_flow

    weather_ingestion_flow()
    dashboard_refresh_flow()
    remote_sensing_flow()


@flow(name="scheduled-daily", retries=1)
def scheduled_daily():
    """Daily tasks: market data, metrics computation, credit adjustment."""
    from .market_data import market_data_flow
    from .metrics import metrics_computation_flow
    from .credit_adjustment import credit_adjustment_flow

    market_data_flow()
    metrics_computation_flow()
    credit_adjustment_flow()


@flow(name="scheduled-weekly", retries=1)
def scheduled_weekly():
    """Weekly tasks: climate data refresh, ML model retraining."""
    from .climate_data import climate_data_flow
    climate_data_flow()
