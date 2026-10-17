"""Remote sensing fetch flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job_for_kokonut_network_locations


@flow(name="remote-sensing-fetch", retries=2, retry_delay_seconds=600)
def remote_sensing_flow():
    """Run due remote sensing jobs for active Kokonut Network locations."""
    return run_job_for_kokonut_network_locations("remote_sensing")
