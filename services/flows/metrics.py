"""Metrics computation flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="metrics-computation", retries=2, retry_delay_seconds=600)
def metrics_computation_flow():
    """Compute all governed metrics for all locations."""
    return run_job("metrics")
