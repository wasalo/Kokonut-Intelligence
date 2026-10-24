"""Metrics computation flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job, run_job_for_kokonut_network_locations


@flow(name="metrics-computation", retries=2, retry_delay_seconds=600)
def metrics_computation_flow(location_id: str | None = None):
    """Compute metrics for one location or fan out across Kokonut Network."""
    if location_id is not None:
        return run_job("metrics", location_id=location_id)
    return run_job_for_kokonut_network_locations("metrics")
