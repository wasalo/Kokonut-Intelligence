"""Carbon credit adjustment flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job, run_job_for_kokonut_network_locations


@flow(name="credit-adjustment", retries=2, retry_delay_seconds=600)
def credit_adjustment_flow(location_id: str | None = None):
    """Check one location or fan out across Kokonut Network without writes."""
    if location_id is not None:
        return run_job("credit_adjustment", location_id=location_id)
    return run_job_for_kokonut_network_locations("credit_adjustment")
