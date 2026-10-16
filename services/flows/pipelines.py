"""Main pipeline definitions with dependency chains.

Defines the orchestration DAG for all Kokonut Intelligence workflows.
"""

from services.core.adapters.prefect import flow, task
from services.core.jobs import JOBS, run_job, run_job_for_kokonut_network_locations


def _dispatch_catalog_job(job_id):
    """Fan out location-required jobs through the confirmed operating org."""
    if "location_id" in JOBS[job_id].required_inputs:
        return run_job_for_kokonut_network_locations(job_id)
    return run_job(job_id)


def _submit_job(job_id):
    """Submit a task with the legacy operation retry policy."""
    spec = JOBS[job_id]
    operation = task(
        name=job_id, retries=spec.retries,
        retry_delay_seconds=spec.retry_delay_seconds,
    )(_dispatch_catalog_job)
    return operation.submit(job_id)


@flow(name="ingestion-pipeline", retries=1)
def ingestion_pipeline():
    """Run all ingestion tasks in parallel, then dependent tasks."""

    # Ingestion tasks run in parallel (no dependencies)
    weather_future = _submit_job("weather")
    market_future = _submit_job("market_data")
    eas_future = _submit_job("eas")
    rpc_future = _submit_job("rpc")
    gnosis_future = _submit_job("gnosis")

    # Wait for all ingestion
    weather_future.result()
    market_future.result()
    eas_future.result()
    rpc_future.result()
    gnosis_future.result()

    return {"status": "success", "ingestion": "complete"}


@flow(name="monitoring-pipeline", retries=1)
def monitoring_pipeline():
    """Run anomaly detection and data freshness checks."""

    anomaly_future = _submit_job("anomaly")
    freshness_future = _submit_job("freshness")

    anomaly_future.result()
    freshness_future.result()

    return {"status": "success", "monitoring": "complete"}


@flow(name="analytics-pipeline", retries=1)
def analytics_pipeline():
    """Run metrics computation, then dashboard refresh."""

    # Metrics first
    metrics_future = _submit_job("metrics")
    metrics_future.result()

    # Then dashboards and credit adjustment (parallel)
    dashboard_future = _submit_job("dashboards")
    credit_future = _submit_job("credit_adjustment")

    dashboard_future.result()
    credit_future.result()

    return {"status": "success", "analytics": "complete"}


@flow(name="full-pipeline", retries=1)
def full_pipeline():
    """Full pipeline: ingestion -> monitoring -> analytics."""
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
    """Hourly tasks: anomaly detection and freshness check.

    Sensor data is push/manual input. The sensor CLI has no recurring source
    adapter, so it must not gate scheduled ingestion or monitoring workflows.
    """
    from .anomaly_detection import anomaly_detection_flow
    from .freshness import freshness_check_flow

    anomaly_detection_flow()
    freshness_check_flow()


@flow(name="scheduled-every-6h", retries=1)
def scheduled_every_6h():
    """Every 6 hours: weather, dashboard refresh, remote sensing."""
    from .dashboards import dashboard_refresh_flow
    from .remote_sensing import remote_sensing_flow
    from .weather import weather_ingestion_flow

    weather_ingestion_flow()
    dashboard_refresh_flow()
    remote_sensing_flow()


@flow(name="scheduled-daily", retries=1)
def scheduled_daily():
    """Daily tasks: market data, metrics computation, credit adjustment."""
    from .credit_adjustment import credit_adjustment_flow
    from .market_data import market_data_flow
    from .metrics import metrics_computation_flow

    market_data_flow()
    metrics_computation_flow()
    credit_adjustment_flow()


@flow(name="scheduled-weekly", retries=1)
def scheduled_weekly():
    """Weekly tasks: climate data refresh, ML model retraining."""
    from .climate_data import climate_data_flow
    climate_data_flow()
