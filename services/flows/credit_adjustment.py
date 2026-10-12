"""Carbon credit adjustment flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="credit-adjustment", retries=2, retry_delay_seconds=600)
def credit_adjustment_flow():
    """Check carbon credit adjustments without confirming retirement."""
    return run_job("credit_adjustment")
