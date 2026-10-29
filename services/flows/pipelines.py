"""Main pipeline definitions with dependency chains.

Defines the orchestration DAG for all Kokonut Intelligence workflows.
"""

from services.core.adapters.prefect import flow, task
from services.core.features import is_enabled
from services.core.jobs import (
    JOBS,
    run_job,
    run_job_for_eas_chains,
    run_job_for_kokonut_network_locations,
    run_job_for_rpc_chains,
)


def _dashboard_refresh_skip_result():
    """Describe the default-off legacy dashboard stage in composite flows."""
    return {
        "status": "skipped",
        "reason": "legacy_dataset_sql_disabled",
    }


def _weather_ingestion_skip_result():
    """Describe the default-off signed weather stage in composite flows."""
    return {
        "status": "skipped",
        "reason": "signed_weather_worker_disabled",
    }


def _dispatch_catalog_job(job_id):
    """Fan out scoped jobs only through their explicit catalog adapters."""
    # This dispatcher is used by the Prefect composite task path. Keep direct
    # weather flow/job/worker calls fail-closed while allowing independent
    # ingestion jobs in the composite to continue until signed credentials are
    # provisioned.
    if job_id == "weather" and not is_enabled("signed_weather_worker"):
        return _weather_ingestion_skip_result()
    if job_id == "market_data":
        from .market_data import dispatch_market_data_job

        return dispatch_market_data_job()
    if "location_id" in JOBS[job_id].required_inputs:
        return run_job_for_kokonut_network_locations(job_id)
    if job_id == "eas":
        return run_job_for_eas_chains()
    if job_id == "rpc":
        return run_job_for_rpc_chains()
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
    """Run metrics and credit work; legacy dashboard refresh is opt-in."""

    # Metrics first
    metrics_future = _submit_job("metrics")
    metrics_future.result()

    # The stored-SQL dashboard refresher is retained for compatibility, but it
    # is disabled in the Kernel profile. Do not let that optional legacy job
    # prevent credit adjustment or the rest of the full pipeline from running.
    dashboard_future = (
        _submit_job("dashboards")
        if is_enabled("legacy_dataset_sql")
        else None
    )
    credit_future = _submit_job("credit_adjustment")

    dashboard_result = (
        dashboard_future.result()
        if dashboard_future is not None
        else _dashboard_refresh_skip_result()
    )
    credit_future.result()

    return {
        "status": "success",
        "analytics": "complete",
        "dashboard_refresh": dashboard_result,
    }


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

    A source-controlled scheduled sensor adapter exists, but requires an
    explicit location and registered driver instance. Keep it out of this
    composite until an owner-reviewed source mapping is configured.
    """
    from .anomaly_detection import anomaly_detection_flow
    from .freshness import freshness_check_flow

    anomaly_detection_flow()
    freshness_check_flow()


@flow(name="scheduled-every-6h", retries=1)
def scheduled_every_6h():
    """Every 6 hours: weather, optional legacy dashboard, remote sensing."""
    from .dashboards import dashboard_refresh_flow
    from .remote_sensing import remote_sensing_flow
    from .weather import weather_ingestion_flow

    weather_result = (
        weather_ingestion_flow()
        if is_enabled("signed_weather_worker")
        else _weather_ingestion_skip_result()
    )
    dashboard_result = (
        dashboard_refresh_flow()
        if is_enabled("legacy_dataset_sql")
        else _dashboard_refresh_skip_result()
    )
    remote_sensing_result = remote_sensing_flow()
    return {
        "status": "success",
        "weather": weather_result,
        "dashboard_refresh": dashboard_result,
        "remote_sensing": remote_sensing_result,
    }


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
    """Refresh climate datasets weekly; ML model retraining is not scheduled."""
    from .climate_data import climate_data_flow
    climate_data_flow()
