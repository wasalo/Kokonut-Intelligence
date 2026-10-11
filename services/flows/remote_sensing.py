"""Remote sensing fetch flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="remote-sensing-fetch", retries=2, retry_delay_seconds=600)
def remote_sensing_flow():
    """Run all due remote sensing fetch jobs."""
    return run_job("remote_sensing")
